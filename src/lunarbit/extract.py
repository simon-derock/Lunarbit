from __future__ import annotations

import json
import mailbox
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from subprocess import run
from typing import Any

from lunarbit.models import (
    DocumentRole,
    OrderCategory,
    OrderCountSummary,
    OrderEvidence,
    OrderEvidenceKind,
    OrderIdCandidate,
    OrderIdSource,
    Platform,
    SourceDocument,
    SourceInventory,
    SourceInventorySummary,
    SourceMessage,
)


class IngestionError(Exception):
    """Base exception for deterministic source ingestion."""


class SourceIntegrityError(IngestionError):
    """Raised when source bytes disagree with acquisition metadata."""


class PdfExtractionError(IngestionError):
    """Raised when native PDF inspection fails."""


_ZOMATO_ORDER_PATTERNS = (
    re.compile(r"\bOrder\s*ID\s*:?\s*(\d{10})\b", re.IGNORECASE),
    re.compile(r"\bOrder\s*(?:number|no\.?)\s*[:#-]?\s*(\d{10})\b", re.IGNORECASE),
)
_SWIGGY_ORDER_PATTERNS = (
    re.compile(r"\bOrder\s*ID\s*:?\s*(\d{15})\b", re.IGNORECASE),
    re.compile(r"\bOrder\s*(?:number|no\.?)\s*[:#-]?\s*(\d{15})\b", re.IGNORECASE),
    re.compile(r"\bfor\s+Order\s*\(\s*(\d{15})\s*\)", re.IGNORECASE),
    re.compile(
        r"\bagainst\s+Order\s+[Ii]d\s*\(?\s*(\d{15})\s*\)?",
        re.IGNORECASE,
    ),
)
_HISTORY_ROW_PATTERN = re.compile(r"(?m)^\s*\d{2}-\d{2}-\d{4}\s+(\d{13,16})\s+")


def _sha256(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def document_id_from_bytes(payload: bytes) -> str:
    return f"doc_{_sha256(payload)[:16]}"


def message_id_from_bytes(payload: bytes) -> str:
    return f"msg_{_sha256(payload)[:16]}"


def _evidence_id(message_id: str, kind: OrderEvidenceKind, order_id: str | None) -> str:
    identity = f"{message_id}|{kind.value}|{order_id or 'provisional'}".encode()
    return f"ev_{_sha256(identity)[:16]}"


def classify_platform(sender: str, subject: str) -> Platform | None:
    sender_address = parseaddr(sender)[1].casefold()
    sender_domain = sender_address.rpartition("@")[2]
    lowered_subject = subject.casefold()
    if sender_domain == "swiggy.in" or sender_domain.endswith(".swiggy.in"):
        return Platform.SWIGGY
    if sender_domain == "instamart.in" or sender_domain.endswith(".instamart.in"):
        return Platform.SWIGGY
    if sender_domain == "zomato.com" or sender_domain.endswith(".zomato.com"):
        return Platform.ZOMATO
    subject_match = re.search(
        r"\b(?:your\s+)?(swiggy|instamart|zomato)\s+(?:food\s+)?(?:order|invoice)\b",
        lowered_subject,
    )
    if subject_match:
        return Platform.ZOMATO if subject_match.group(1) == "zomato" else Platform.SWIGGY
    return None


def classify_document_role(
    *,
    platform: Platform,
    category: OrderCategory,
    filename: str,
    text: str,
) -> DocumentRole:
    lowered_name = filename.casefold()
    lowered_text = text.casefold()

    if platform is Platform.ZOMATO:
        if "user_charge_invoice" in lowered_name:
            return DocumentRole.ZOMATO_PLATFORM_FEE_INVOICE
        if "order_invoice" in lowered_name:
            return DocumentRole.ZOMATO_MERCHANT_INVOICE
        if "order_id_" in lowered_name or "summary and receipt" in lowered_text:
            return DocumentRole.ZOMATO_ORDER_SUMMARY
        if "local delivery service" in lowered_text or "delivery partner name" in lowered_text:
            return DocumentRole.ZOMATO_DELIVERY_SERVICE_INVOICE
        return DocumentRole.UNKNOWN

    if "number of orders" in lowered_text and "order details" in lowered_text:
        return DocumentRole.SWIGGY_ORDER_HISTORY_REPORT
    if category is OrderCategory.INSTAMART:
        return DocumentRole.SWIGGY_INSTAMART_SELLER_INVOICE
    if "platform fee" in lowered_text and (
        "invoice from" in lowered_text or "swiggy limited" in lowered_text
    ):
        return DocumentRole.SWIGGY_PLATFORM_FEE_INVOICE
    if "tax invoice" in lowered_text:
        return DocumentRole.SWIGGY_RESTAURANT_INVOICE
    return DocumentRole.UNKNOWN


def extract_order_id_candidates(
    platform: Platform,
    text: str,
    *,
    source: OrderIdSource,
) -> tuple[OrderIdCandidate, ...]:
    patterns = _ZOMATO_ORDER_PATTERNS if platform is Platform.ZOMATO else _SWIGGY_ORDER_PATTERNS
    values = sorted({value for pattern in patterns for value in pattern.findall(text)})
    confidence = {
        OrderIdSource.PDF_LABEL: Decimal("1.00"),
        OrderIdSource.EMAIL_FIELD: Decimal("0.95"),
        OrderIdSource.HISTORY_ROW: Decimal("1.00"),
        OrderIdSource.ATTACHMENT_FILENAME: Decimal("0.60"),
        OrderIdSource.MANIFEST_HINT: Decimal("0.50"),
    }[source]
    return tuple(
        OrderIdCandidate(value_private=value, source=source, confidence=confidence)
        for value in values
    )


def extract_history_order_ids(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(_HISTORY_ROW_PATTERN.findall(text))))


def count_orders(evidence: Sequence[OrderEvidence]) -> OrderCountSummary:
    ordinary_resolved = {
        (item.platform, item.order_id_private)
        for item in evidence
        if item.kind is not OrderEvidenceKind.HISTORY_ROW and item.order_id_private is not None
    }
    history_resolved = {
        (item.platform, item.order_id_private)
        for item in evidence
        if item.kind is OrderEvidenceKind.HISTORY_ROW and item.order_id_private is not None
    }
    all_resolved = ordinary_resolved | history_resolved
    provisional_messages = {
        (item.platform, item.message_id)
        for item in evidence
        if item.kind is not OrderEvidenceKind.HISTORY_ROW and item.order_id_private is None
    }
    return OrderCountSummary(
        resolved_orders=len(all_resolved),
        provisional_orders=len(provisional_messages),
        total_orders=len(all_resolved) + len(provisional_messages),
        history_duplicates=len(history_resolved & ordinary_resolved),
    )


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"head", "script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"head", "script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(value)
    return " ".join(parser.parts)


def extract_pdf_text(payload: bytes) -> str:
    result = run(
        ["pdftotext", "-layout", "-", "-"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise PdfExtractionError("native text extraction failed for a private PDF")
    return result.stdout.decode("utf-8", errors="replace")


def pdf_page_count(payload: bytes) -> int:
    result = run(
        ["pdfinfo", "-"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise PdfExtractionError("page inspection failed for a private PDF")
    output = result.stdout.decode("utf-8", errors="replace")
    match = re.search(r"^Pages:\s+(\d+)$", output, re.MULTILINE)
    if match is None or int(match.group(1)) < 1:
        raise PdfExtractionError("private PDF has no valid page count")
    return int(match.group(1))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    rendered = str(value).strip()
    if not rendered:
        return None
    if rendered.isdigit():
        timestamp = int(rendered)
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    try:
        parsed = datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(rendered)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _category(value: str) -> OrderCategory:
    return OrderCategory.INSTAMART if value.casefold() == "instamart" else OrderCategory.FOOD


def _safe_bundle_path(bundle: Path, relative: str) -> Path:
    bundle_root = bundle.resolve()
    candidate = (bundle / relative).resolve()
    try:
        candidate.relative_to(bundle_root)
    except ValueError as exc:
        raise SourceIntegrityError("acquisition artifact escapes its private bundle") from exc
    return candidate


def _validated_attachment(bundle: Path, metadata: dict[str, Any]) -> tuple[Path, bytes]:
    path = _safe_bundle_path(bundle, str(metadata["path"]))
    if not path.is_file():
        raise SourceIntegrityError("acquisition manifest references a missing attachment")
    payload = path.read_bytes()
    if len(payload) != int(metadata["bytes"]):
        raise SourceIntegrityError("attachment byte count disagrees with acquisition metadata")
    if _sha256(payload) != str(metadata["sha256"]):
        raise SourceIntegrityError("attachment hash disagrees with acquisition metadata")
    if not payload.startswith(b"%PDF-") or not bool(metadata.get("validPdfSignature")):
        raise SourceIntegrityError("attachment does not have a validated PDF signature")
    return path, payload


def _decoded_filename(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def _decoded_payload_bytes(part: Message) -> bytes:
    payload: object = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode(part.get_content_charset() or "utf-8", errors="replace")
    return b""


def _message_body(message: Message) -> tuple[str, str]:
    private_parts: list[str] = []
    raw_parts: list[bytes] = []
    parts: Iterable[Message] = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        content_type = part.get_content_type().casefold()
        if content_type not in {"text/html", "text/plain"}:
            continue
        payload = _decoded_payload_bytes(part)
        raw_parts.append(payload)
        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="replace")
        except LookupError:
            decoded = payload.decode("utf-8", errors="replace")
        private_parts.append(html_to_text(decoded) if content_type == "text/html" else decoded)
    raw_body = b"\n".join(raw_parts)
    return " ".join(private_parts), _sha256(raw_body)


def _source_document(
    *,
    message_id: str,
    platform: Platform,
    category: OrderCategory,
    filename: str,
    source_locator: str,
    mime_type: str,
    payload: bytes,
) -> tuple[SourceDocument, str]:
    text = extract_pdf_text(payload)
    candidates = extract_order_id_candidates(
        platform,
        text,
        source=OrderIdSource.PDF_LABEL,
    )
    role = classify_document_role(
        platform=platform,
        category=category,
        filename=filename,
        text=text,
    )
    document = SourceDocument(
        document_id=document_id_from_bytes(payload),
        sha256=_sha256(payload),
        message_id=message_id,
        platform=platform,
        category=category,
        role=role,
        source_filename_private=filename,
        source_locator_private=source_locator,
        mime_type=mime_type,
        byte_count=len(payload),
        page_count=pdf_page_count(payload),
        native_text_available=bool(text.strip()),
        order_candidates=candidates,
    )
    return document, text


def _strong_candidate_value(candidates: Iterable[OrderIdCandidate]) -> str | None:
    values = {
        candidate.value_private
        for candidate in candidates
        if candidate.source
        in {OrderIdSource.PDF_LABEL, OrderIdSource.EMAIL_FIELD, OrderIdSource.HISTORY_ROW}
    }
    return next(iter(values)) if len(values) == 1 else None


class _InventoryBuilder:
    def __init__(
        self,
        document_handler: Callable[[SourceDocument, bytes], None] | None = None,
    ) -> None:
        self.messages: dict[str, SourceMessage] = {}
        self.documents: dict[str, SourceDocument] = {}
        self.evidence: dict[str, OrderEvidence] = {}
        self.document_handler = document_handler
        self.excluded_messages = 0
        self.duplicate_pdf_documents = 0
        self.pdf_backed_order_messages: set[str] = set()
        self.mail_only_order_messages: set[str] = set()

    def add_document(self, document: SourceDocument, payload: bytes) -> None:
        if document.document_id in self.documents:
            self.duplicate_pdf_documents += 1
            return
        self.documents[document.document_id] = document
        if self.document_handler is not None:
            self.document_handler(document, payload)

    def add_evidence(
        self,
        *,
        message_id: str,
        platform: Platform,
        kind: OrderEvidenceKind,
        order_id: str | None,
    ) -> None:
        evidence = OrderEvidence(
            evidence_id=_evidence_id(message_id, kind, order_id),
            message_id=message_id,
            platform=platform,
            kind=kind,
            order_id_private=order_id,
        )
        self.evidence[evidence.evidence_id] = evidence

    def finish(self) -> SourceInventory:
        messages = tuple(sorted(self.messages.values(), key=lambda item: item.message_id))
        documents = tuple(sorted(self.documents.values(), key=lambda item: item.document_id))
        evidence = tuple(sorted(self.evidence.values(), key=lambda item: item.evidence_id))
        orders = count_orders(evidence)
        return SourceInventory(
            messages=messages,
            documents=documents,
            order_evidence=evidence,
            summary=SourceInventorySummary(
                relevant_messages=len(messages),
                excluded_messages=self.excluded_messages,
                unique_pdf_documents=len(documents),
                pdf_pages=sum(document.page_count for document in documents),
                pdf_backed_order_messages=len(self.pdf_backed_order_messages),
                mail_only_order_messages=len(self.mail_only_order_messages),
                history_report_documents=sum(
                    document.role is DocumentRole.SWIGGY_ORDER_HISTORY_REPORT
                    for document in documents
                ),
                duplicate_pdf_documents=self.duplicate_pdf_documents,
                orders=orders,
            ),
        )


def _ingest_bundle_manifest(
    manifest_path: Path,
    builder: _InventoryBuilder,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle = manifest_path.parent
    platform = Platform(str(manifest["vendor"]).casefold())
    category = _category(str(manifest["category"]))
    email_metadata = manifest.get("email", {})
    email_path = bundle / "email.eml"
    raw_message = email_path.read_bytes() if email_path.is_file() else manifest_path.read_bytes()
    message_id = message_id_from_bytes(raw_message)
    if message_id in builder.messages:
        return

    body_path = bundle / "body.html"
    raw_body = body_path.read_bytes() if body_path.is_file() else b""
    body_text = html_to_text(raw_body.decode("utf-8", errors="replace"))
    email_candidates = extract_order_id_candidates(
        platform,
        body_text,
        source=OrderIdSource.EMAIL_FIELD,
    )
    manifest_hint = str(manifest.get("orderId", ""))
    hint_candidates: tuple[OrderIdCandidate, ...] = ()
    if manifest_hint.isdigit():
        hint_candidates = (
            OrderIdCandidate(
                value_private=manifest_hint,
                source=OrderIdSource.MANIFEST_HINT,
                confidence=Decimal("0.50"),
            ),
        )

    documents: list[SourceDocument] = []
    history_rows: set[str] = set()
    pdf_candidates: list[OrderIdCandidate] = []
    for metadata in manifest.get("attachments", []):
        path, payload = _validated_attachment(bundle, metadata)
        document, text = _source_document(
            message_id=message_id,
            platform=platform,
            category=category,
            filename=str(metadata["filename"]),
            source_locator=str(path),
            mime_type=str(metadata.get("mimeType", "application/pdf")),
            payload=payload,
        )
        builder.add_document(document, payload)
        documents.append(document)
        pdf_candidates.extend(document.order_candidates)
        if document.role is DocumentRole.SWIGGY_ORDER_HISTORY_REPORT:
            history_rows.update(extract_history_order_ids(text))

    combined_candidates = tuple(email_candidates) + tuple(pdf_candidates) + hint_candidates
    message = SourceMessage(
        message_id=message_id,
        raw_sha256=_sha256(raw_message),
        platform=platform,
        category=category,
        occurred_at=_parse_datetime(email_metadata.get("internalDate")),
        subject_private=str(email_metadata.get("subject", "")),
        sender_private=str(email_metadata.get("from", "")),
        source_locator_private=str(email_path if email_path.is_file() else manifest_path),
        provider_message_id_private=str(email_metadata.get("messageIdHeader") or "") or None,
        body_sha256=_sha256(raw_body),
        attachment_document_ids=tuple(document.document_id for document in documents),
        order_candidates=combined_candidates,
    )
    builder.messages[message_id] = message

    if history_rows:
        for order_id in history_rows:
            builder.add_evidence(
                message_id=message_id,
                platform=platform,
                kind=OrderEvidenceKind.HISTORY_ROW,
                order_id=order_id,
            )
        return

    if documents:
        builder.pdf_backed_order_messages.add(message_id)
        builder.add_evidence(
            message_id=message_id,
            platform=platform,
            kind=OrderEvidenceKind.PDF_BUNDLE,
            order_id=_strong_candidate_value(combined_candidates),
        )
    else:
        builder.mail_only_order_messages.add(message_id)
        builder.add_evidence(
            message_id=message_id,
            platform=platform,
            kind=OrderEvidenceKind.EMAIL_ONLY,
            order_id=_strong_candidate_value(combined_candidates),
        )


def _ingest_mbox(mbox_path: Path, builder: _InventoryBuilder) -> None:
    box = mailbox.mbox(mbox_path, create=False)
    try:
        for index, email_message in enumerate(box):
            sender = str(email_message.get("From", ""))
            subject = str(email_message.get("Subject", ""))
            platform = classify_platform(sender, subject)
            if platform is None:
                builder.excluded_messages += 1
                continue
            category = (
                OrderCategory.INSTAMART
                if "instamart" in f"{sender} {subject}".casefold()
                else OrderCategory.FOOD
            )
            raw_message = email_message.as_bytes(policy=policy.default)
            message_id = message_id_from_bytes(raw_message)
            if message_id in builder.messages:
                continue
            body_text, body_sha256 = _message_body(email_message)
            email_candidates = extract_order_id_candidates(
                platform,
                f"{subject} {body_text}",
                source=OrderIdSource.EMAIL_FIELD,
            )

            documents: list[SourceDocument] = []
            pdf_candidates: list[OrderIdCandidate] = []
            history_rows: set[str] = set()
            parts: Iterable[Message] = (
                email_message.walk() if email_message.is_multipart() else (email_message,)
            )
            for attachment_index, part in enumerate(parts):
                filename = _decoded_filename(part.get_filename())
                payload = _decoded_payload_bytes(part)
                is_pdf = (
                    part.get_content_type().casefold() == "application/pdf"
                    or Path(filename).suffix.casefold() == ".pdf"
                    or payload.startswith(b"%PDF-")
                )
                if not is_pdf:
                    continue
                filename = filename or "attachment.pdf"
                document, text = _source_document(
                    message_id=message_id,
                    platform=platform,
                    category=category,
                    filename=filename,
                    source_locator=f"{mbox_path}#message-{index}:attachment-{attachment_index}",
                    mime_type=part.get_content_type(),
                    payload=payload,
                )
                builder.add_document(document, payload)
                documents.append(document)
                pdf_candidates.extend(document.order_candidates)
                if document.role is DocumentRole.SWIGGY_ORDER_HISTORY_REPORT:
                    history_rows.update(extract_history_order_ids(text))

            combined_candidates = tuple(email_candidates) + tuple(pdf_candidates)
            message = SourceMessage(
                message_id=message_id,
                raw_sha256=_sha256(raw_message),
                platform=platform,
                category=category,
                occurred_at=_parse_datetime(email_message.get("Date")),
                subject_private=subject,
                sender_private=sender,
                source_locator_private=f"{mbox_path}#message-{index}",
                provider_message_id_private=str(email_message.get("Message-ID") or "") or None,
                body_sha256=body_sha256,
                attachment_document_ids=tuple(document.document_id for document in documents),
                order_candidates=combined_candidates,
            )
            builder.messages[message_id] = message

            if history_rows:
                for order_id in history_rows:
                    builder.add_evidence(
                        message_id=message_id,
                        platform=platform,
                        kind=OrderEvidenceKind.HISTORY_ROW,
                        order_id=order_id,
                    )
            elif documents:
                builder.pdf_backed_order_messages.add(message_id)
                builder.add_evidence(
                    message_id=message_id,
                    platform=platform,
                    kind=OrderEvidenceKind.PDF_BUNDLE,
                    order_id=_strong_candidate_value(combined_candidates),
                )
            else:
                builder.mail_only_order_messages.add(message_id)
                builder.add_evidence(
                    message_id=message_id,
                    platform=platform,
                    kind=OrderEvidenceKind.EMAIL_ONLY,
                    order_id=_strong_candidate_value(combined_candidates),
                )
    finally:
        box.close()


def build_source_inventory(
    input_root: Path,
    *,
    document_handler: Callable[[SourceDocument, bytes], None] | None = None,
) -> SourceInventory:
    root = input_root.resolve()
    builder = _InventoryBuilder(document_handler=document_handler)
    for platform in (Platform.SWIGGY, Platform.ZOMATO):
        for manifest_path in sorted((root / platform.value).glob("*/manifest.json")):
            _ingest_bundle_manifest(manifest_path, builder)
    for mbox_path in sorted(root.glob("*/Takeout/Mail/*.mbox")):
        _ingest_mbox(mbox_path, builder)
    return builder.finish()


def _atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_source_inventory(inventory: SourceInventory, output_root: Path) -> Path:
    inventory_root = output_root / "_inventory"
    _atomic_private_write(
        inventory_root / "source_messages.jsonl",
        "".join(f"{item.model_dump_json()}\n" for item in inventory.messages),
    )
    _atomic_private_write(
        inventory_root / "documents.jsonl",
        "".join(f"{item.model_dump_json()}\n" for item in inventory.documents),
    )
    _atomic_private_write(
        inventory_root / "order_evidence.jsonl",
        "".join(f"{item.model_dump_json()}\n" for item in inventory.order_evidence),
    )
    summary_path = inventory_root / "summary.json"
    _atomic_private_write(summary_path, f"{inventory.summary.model_dump_json(indent=2)}\n")
    return summary_path
