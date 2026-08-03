from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from lunarbit.models import (
    BoundingBox,
    CandidateAssertion,
    CandidateFactType,
    CandidateMoneyComponent,
    CandidateMoneyType,
    ChunkArchiveSummary,
    ChunkBenchmarkSummary,
    ChunkingResult,
    ChunkStrategy,
    ChunkType,
    DocumentManifest,
    DocumentRecord,
    DocumentRole,
    EntityMention,
    EntityType,
    EvidenceChunk,
    EvidenceSourceKind,
    ExtractionMethod,
    FinancialRole,
    GraphCandidate,
    PageRecord,
    PrivacyStatus,
    ProcessedDocument,
    ProcessingStatus,
    QueryFamily,
    SemanticRole,
    SourceDocument,
    SourceMessage,
    TableCell,
    TableRecord,
    ValidationStatus,
)

CHUNK_SCHEMA_VERSION = "1.0.0"

_ORDER_ID_PATTERN = re.compile(
    r"\bOrder\s*(?:(?:ID|number|no\.?)\s*)?[:#-]?\s*#?\s*(\d{10,16})\b",
    re.IGNORECASE,
)
_ORDER_DATE_PATTERN = re.compile(
    r"\b(?:Order\s+date|Ordered\s+on)\s*[:-]?\s*([^\n|]{6,40})",
    re.IGNORECASE,
)
_MERCHANT_PATTERN = re.compile(
    r"\b(?:Restaurant(?:\s+Name)?|Merchant|Seller|Sold\s+By)\s*[:-]\s*([^\n|]{2,80})",
    re.IGNORECASE,
)
_ORDER_FROM_PATTERN = re.compile(
    r"\bOrder(?:ed)?\s+from\s*[:-]?\s*"
    r"([^\n|.!?]{2,80}?)(?=\s+(?:has|is|was|will)\b|[\n|.!?]|$)",
    re.IGNORECASE,
)
_LEGAL_ENTITY_PATTERN = re.compile(
    r"\b(?:Invoice\s+From|Legal\s+Name|Supplier)\s*[:-]\s*([^\n|]{2,100})",
    re.IGNORECASE,
)
_DELIVERY_PARTNER_PATTERN = re.compile(
    r"\bDelivery\s+(?:Partner|Executive|Person)(?:\s+Name)?\s*[:-]\s*([^\n|]{2,80})",
    re.IGNORECASE,
)
_INVOICE_NUMBER_PATTERN = re.compile(
    r"\bInvoice\s*(?:Number|No\.?)\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/_-]{2,40})",
    re.IGNORECASE,
)
_PAYMENT_METHOD_PATTERN = re.compile(
    r"\b(?:Payment\s+(?:method|mode)|Paid\s+via)\s*[:-]\s*([^\n|]{2,60})",
    re.IGNORECASE,
)

_MONEY_PATTERNS = (
    (
        CandidateMoneyType.SUBTOTAL,
        re.compile(
            r"\bSub\s*total\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.DISCOUNT,
        re.compile(
            r"\b(?:Discount|Coupon)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.PACKING_CHARGE,
        re.compile(
            r"\bPack(?:ing|aging)\s+(?:charge|fee)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.HANDLING_FEE,
        re.compile(
            r"\bHandling\s+(?:charge|fee)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.DELIVERY_CHARGE,
        re.compile(
            r"\bDelivery\s+(?:charge|fee)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.PLATFORM_FEE,
        re.compile(
            r"\bPlatform\s+(?:charge|fee)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.TAX,
        re.compile(
            r"\b(?:Tax|CGST|SGST|IGST|GST)\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.REFUND,
        re.compile(
            r"\bRefund\s*[:-]?\s*(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateMoneyType.INVOICE_TOTAL,
        re.compile(
            r"\b(?:Grand\s+total|Invoice\s+total|Total(?:\s+amount)?)\s*[:-]?\s*"
            r"(?:₹|INR|Rs\.?)?\s*(?P<amount>-?\d[\d,]*(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
)

_DOCUMENT_STRATEGIES = {
    DocumentRole.ZOMATO_ORDER_SUMMARY: ChunkStrategy.ORDER_COMPONENT,
    DocumentRole.ZOMATO_MERCHANT_INVOICE: ChunkStrategy.TABLE_PRESERVING_INVOICE,
    DocumentRole.ZOMATO_DELIVERY_SERVICE_INVOICE: ChunkStrategy.TABLE_PRESERVING_INVOICE,
    DocumentRole.SWIGGY_RESTAURANT_INVOICE: ChunkStrategy.TABLE_PRESERVING_INVOICE,
    DocumentRole.SWIGGY_INSTAMART_SELLER_INVOICE: ChunkStrategy.TABLE_PRESERVING_INVOICE,
    DocumentRole.ZOMATO_PLATFORM_FEE_INVOICE: ChunkStrategy.FEE_AND_TAX,
    DocumentRole.SWIGGY_PLATFORM_FEE_INVOICE: ChunkStrategy.FEE_AND_TAX,
    DocumentRole.SWIGGY_ORDER_HISTORY_REPORT: ChunkStrategy.HISTORY_TABLE,
    DocumentRole.UNKNOWN: ChunkStrategy.UNKNOWN_LAYOUT,
}


@dataclass(frozen=True)
class _Region:
    raw_text: str
    chunk_type: ChunkType
    bbox: BoundingBox
    source_region_ids: tuple[str, ...]
    sort_key: tuple[float, float, int, int]
    table_id: str | None = None
    row_index: int | None = None
    column_headers: tuple[str, ...] = ()
    parent_region_id: str | None = None
    table_amount: tuple[str, int, int] | None = None


def _hash(value: str | bytes) -> str:
    payload = value.encode() if isinstance(value, str) else value
    return sha256(payload).hexdigest()


def _stable_uuid(*parts: object) -> UUID:
    return uuid5(NAMESPACE_URL, "lunarbit:" + "|".join(str(part) for part in parts))


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def route_document_strategy(role: DocumentRole) -> ChunkStrategy:
    return _DOCUMENT_STRATEGIES[role]


def _fact_matches(raw_text: str) -> tuple[tuple[CandidateFactType, re.Match[str]], ...]:
    patterns = (
        (CandidateFactType.ORDER_ID, _ORDER_ID_PATTERN),
        (CandidateFactType.ORDER_DATE, _ORDER_DATE_PATTERN),
        (CandidateFactType.MERCHANT_NAME, _MERCHANT_PATTERN),
        (CandidateFactType.MERCHANT_NAME, _ORDER_FROM_PATTERN),
        (CandidateFactType.LEGAL_ENTITY_NAME, _LEGAL_ENTITY_PATTERN),
        (CandidateFactType.DELIVERY_PARTNER_NAME, _DELIVERY_PARTNER_PATTERN),
        (CandidateFactType.INVOICE_NUMBER, _INVOICE_NUMBER_PATTERN),
        (CandidateFactType.PAYMENT_METHOD, _PAYMENT_METHOD_PATTERN),
    )
    return tuple(
        (fact_type, match)
        for fact_type, pattern in patterns
        for match in pattern.finditer(raw_text)
    )


def _candidate_assertions(raw_text: str, chunk_id: UUID) -> tuple[CandidateAssertion, ...]:
    candidates: list[CandidateAssertion] = []
    seen: set[tuple[CandidateFactType, int, int]] = set()
    for fact_type, match in _fact_matches(raw_text):
        start, end = match.span(1)
        identity = (fact_type, start, end)
        if identity in seen:
            continue
        seen.add(identity)
        raw_value = match.group(1).strip()
        leading_space = len(match.group(1)) - len(match.group(1).lstrip())
        trailing_space = len(match.group(1)) - len(match.group(1).rstrip())
        start += leading_space
        end -= trailing_space
        candidates.append(
            CandidateAssertion(
                assertion_id=_stable_uuid(chunk_id, "assertion", fact_type.value, start, end),
                fact_type=fact_type,
                raw_value_private=raw_value,
                normalized_value_private=_normalize(raw_value),
                source_span_start=start,
                source_span_end=end,
                confidence=Decimal("0.95"),
            )
        )
    return tuple(candidates)


def _entity_mentions(raw_text: str, chunk_id: UUID) -> tuple[EntityMention, ...]:
    mapping = {
        CandidateFactType.MERCHANT_NAME: EntityType.MERCHANT,
        CandidateFactType.LEGAL_ENTITY_NAME: EntityType.LEGAL_ENTITY,
        CandidateFactType.DELIVERY_PARTNER_NAME: EntityType.DELIVERY_PARTNER,
    }
    mentions: list[EntityMention] = []
    for fact_type, match in _fact_matches(raw_text):
        entity_type = mapping.get(fact_type)
        if entity_type is None:
            continue
        start, end = match.span(1)
        raw_group = match.group(1)
        leading_space = len(raw_group) - len(raw_group.lstrip())
        trailing_space = len(raw_group) - len(raw_group.rstrip())
        start += leading_space
        end -= trailing_space
        raw_value = raw_text[start:end]
        mentions.append(
            EntityMention(
                mention_id=_stable_uuid(
                    chunk_id, "mention", entity_type.value, start, end, raw_value
                ),
                entity_type=entity_type,
                raw_value_private=raw_value,
                normalized_value_private=_normalize(raw_value),
                source_span_start=start,
                source_span_end=end,
                confidence=Decimal("0.90"),
            )
        )
    return tuple(mentions)


def _source_precision(value: str) -> int:
    rendered = value.replace(",", "")
    return len(rendered.rpartition(".")[2]) if "." in rendered else 0


def _money_candidate(
    *,
    chunk_id: UUID,
    component_type: CandidateMoneyType,
    raw_text: str,
    start: int,
    end: int,
    confidence: Decimal,
) -> CandidateMoneyComponent | None:
    source_value = raw_text[start:end]
    try:
        amount = Decimal(source_value.replace(",", ""))
    except InvalidOperation:
        return None
    return CandidateMoneyComponent(
        component_id=_stable_uuid(chunk_id, "money", component_type.value, start, end),
        component_type=component_type,
        amount=amount,
        source_amount_string_private=source_value,
        source_precision=_source_precision(source_value),
        source_span_start=start,
        source_span_end=end,
        confidence=confidence,
    )


def _money_candidates(
    raw_text: str,
    chunk_id: UUID,
    table_amount: tuple[str, int, int] | None,
) -> tuple[CandidateMoneyComponent, ...]:
    candidates: list[CandidateMoneyComponent] = []
    seen: set[tuple[CandidateMoneyType, int, int]] = set()
    if table_amount is not None:
        _, start, end = table_amount
        candidate = _money_candidate(
            chunk_id=chunk_id,
            component_type=CandidateMoneyType.ITEM_AMOUNT,
            raw_text=raw_text,
            start=start,
            end=end,
            confidence=Decimal("0.90"),
        )
        if candidate is not None:
            candidates.append(candidate)
            seen.add((candidate.component_type, start, end))

    for component_type, pattern in _MONEY_PATTERNS:
        for match in pattern.finditer(raw_text):
            start, end = match.span("amount")
            identity = (component_type, start, end)
            if identity in seen:
                continue
            candidate = _money_candidate(
                chunk_id=chunk_id,
                component_type=component_type,
                raw_text=raw_text,
                start=start,
                end=end,
                confidence=Decimal("0.92"),
            )
            if candidate is not None:
                seen.add(identity)
                candidates.append(candidate)
    return tuple(candidates)


def _classify_chunk(raw_text: str) -> ChunkType:
    lowered = raw_text.casefold()
    if _ORDER_ID_PATTERN.search(raw_text):
        return ChunkType.ORDER_HEADER
    if "delivery partner" in lowered or "delivery executive" in lowered:
        return ChunkType.DELIVERY_MENTION
    if "refund" in lowered:
        return ChunkType.REFUND_BLOCK
    if "discount" in lowered or "coupon" in lowered:
        return ChunkType.DISCOUNT_BLOCK
    if "membership" in lowered or "swiggy one" in lowered or "zomato gold" in lowered:
        return ChunkType.MEMBERSHIP_BENEFIT
    if "packing" in lowered or "packaging" in lowered:
        return ChunkType.PACKING_CHARGE
    if "handling fee" in lowered or "handling charge" in lowered:
        return ChunkType.HANDLING_FEE
    if "delivery fee" in lowered or "delivery charge" in lowered:
        return ChunkType.DELIVERY_CHARGE
    if "platform fee" in lowered or "platform charge" in lowered:
        return ChunkType.PLATFORM_FEE
    if re.search(r"\b(?:cgst|sgst|igst|gst|tax)\b", lowered):
        return ChunkType.TAX_BLOCK
    if "subtotal" in lowered or "sub total" in lowered:
        return ChunkType.SUBTOTAL
    if "payment" in lowered or "paid via" in lowered or "settled" in lowered:
        return ChunkType.PAYMENT_ASSERTION
    if _LEGAL_ENTITY_PATTERN.search(raw_text):
        return ChunkType.LEGAL_ENTITY_BLOCK
    if re.search(r"\b(?:gstin|hsn|sac|fssai)\b", lowered):
        return ChunkType.REGULATORY_BLOCK
    if _MERCHANT_PATTERN.search(raw_text):
        return ChunkType.ORDER_PARTIES
    if "terms and conditions" in lowered:
        return ChunkType.TERMS_BLOCK
    return ChunkType.OTHER_EVIDENCE


def _roles(chunk_type: ChunkType) -> tuple[SemanticRole, FinancialRole]:
    mapping = {
        ChunkType.ORDER_HEADER: (SemanticRole.ORDER_IDENTITY, FinancialRole.NONE),
        ChunkType.ORDER_PARTIES: (SemanticRole.PARTY_IDENTITY, FinancialRole.NONE),
        ChunkType.DELIVERY_MENTION: (SemanticRole.DELIVERY_EVIDENCE, FinancialRole.NONE),
        ChunkType.ITEM_TABLE: (SemanticRole.ITEM_DETAIL, FinancialRole.ITEM),
        ChunkType.ITEM_ROW: (SemanticRole.ITEM_DETAIL, FinancialRole.ITEM),
        ChunkType.SUBTOTAL: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.TOTAL),
        ChunkType.DISCOUNT_BLOCK: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.DISCOUNT),
        ChunkType.MEMBERSHIP_BENEFIT: (
            SemanticRole.FINANCIAL_DETAIL,
            FinancialRole.DISCOUNT,
        ),
        ChunkType.PACKING_CHARGE: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.CHARGE),
        ChunkType.HANDLING_FEE: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.CHARGE),
        ChunkType.DELIVERY_CHARGE: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.CHARGE),
        ChunkType.PLATFORM_FEE: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.CHARGE),
        ChunkType.TAX_BLOCK: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.TAX),
        ChunkType.PAYMENT_ASSERTION: (SemanticRole.PAYMENT_EVIDENCE, FinancialRole.PAYMENT),
        ChunkType.REFUND_BLOCK: (SemanticRole.FINANCIAL_DETAIL, FinancialRole.REFUND),
        ChunkType.LEGAL_ENTITY_BLOCK: (SemanticRole.LEGAL_DETAIL, FinancialRole.NONE),
        ChunkType.REGULATORY_BLOCK: (SemanticRole.REGULATORY_DETAIL, FinancialRole.NONE),
        ChunkType.TERMS_BLOCK: (SemanticRole.GENERAL_EVIDENCE, FinancialRole.NONE),
        ChunkType.OTHER_EVIDENCE: (SemanticRole.GENERAL_EVIDENCE, FinancialRole.NONE),
    }
    return mapping[chunk_type]


def _query_families(
    chunk_type: ChunkType,
    assertions: tuple[CandidateAssertion, ...],
    mentions: tuple[EntityMention, ...],
    money: tuple[CandidateMoneyComponent, ...],
) -> tuple[QueryFamily, ...]:
    families = {QueryFamily.EVIDENCE_REPLAY}
    if any(candidate.fact_type is CandidateFactType.ORDER_ID for candidate in assertions):
        families.add(QueryFamily.ORDER_LOOKUP)
    if chunk_type in {ChunkType.ITEM_TABLE, ChunkType.ITEM_ROW}:
        families.add(QueryFamily.ITEM_SEARCH)
    if money:
        families.add(QueryFamily.FINANCIAL_BREAKDOWN)
    if any(mention.entity_type is EntityType.MERCHANT for mention in mentions):
        families.add(QueryFamily.MERCHANT_ANALYSIS)
    if any(mention.entity_type is EntityType.DELIVERY_PARTNER for mention in mentions):
        families.add(QueryFamily.DELIVERY_ANALYSIS)
    if chunk_type is ChunkType.TAX_BLOCK:
        families.add(QueryFamily.TAX_ANALYSIS)
    if chunk_type is ChunkType.PAYMENT_ASSERTION:
        families.add(QueryFamily.PAYMENT_ANALYSIS)
    return tuple(sorted(families, key=lambda family: family.value))


def _graph_candidates(
    chunk_id: UUID,
    assertions: tuple[CandidateAssertion, ...],
    mentions: tuple[EntityMention, ...],
    money: tuple[CandidateMoneyComponent, ...],
) -> tuple[GraphCandidate, ...]:
    candidates: list[GraphCandidate] = []
    for assertion in assertions:
        candidates.append(
            GraphCandidate(
                candidate_id=_stable_uuid(chunk_id, "graph", assertion.assertion_id),
                candidate_type=f"asserts_{assertion.fact_type.value}",
                source_candidate_ids=(assertion.assertion_id,),
            )
        )
    for mention in mentions:
        candidates.append(
            GraphCandidate(
                candidate_id=_stable_uuid(chunk_id, "graph", mention.mention_id),
                candidate_type=f"mentions_{mention.entity_type.value}",
                source_candidate_ids=(mention.mention_id,),
            )
        )
    for component in money:
        candidates.append(
            GraphCandidate(
                candidate_id=_stable_uuid(chunk_id, "graph", component.component_id),
                candidate_type=f"proposes_{component.component_type.value}",
                source_candidate_ids=(component.component_id,),
            )
        )
    return tuple(candidates)


def _build_chunk(
    *,
    source_kind: EvidenceSourceKind,
    source_id: str,
    raw_text: str,
    chunk_type: ChunkType,
    context: str,
    reading_order: int,
    source_region_ids: tuple[str, ...],
    extraction_method: ExtractionMethod,
    bounding_box: BoundingBox | None = None,
    page_number: int | None = None,
    table_id: str | None = None,
    row_index: int | None = None,
    column_headers: tuple[str, ...] = (),
    parent_region_id: str | None = None,
    table_amount: tuple[str, int, int] | None = None,
) -> EvidenceChunk:
    normalized_text = _normalize(raw_text)
    chunk_id = _stable_uuid(
        "chunk",
        source_id,
        page_number or 0,
        chunk_type.value,
        reading_order,
        _hash(normalized_text),
    )
    assertions = _candidate_assertions(raw_text, chunk_id)
    mentions = _entity_mentions(raw_text, chunk_id)
    money = _money_candidates(raw_text, chunk_id, table_amount)
    semantic_role, financial_role = _roles(chunk_type)
    return EvidenceChunk(
        chunk_id=chunk_id,
        source_kind=source_kind,
        source_id=source_id,
        document_id=source_id if source_kind is EvidenceSourceKind.DOCUMENT else None,
        message_id=source_id if source_kind is EvidenceSourceKind.MESSAGE else None,
        page_number=page_number,
        chunk_type=chunk_type,
        semantic_role=semantic_role,
        financial_role=financial_role,
        raw_text_private=raw_text,
        normalized_text_private=normalized_text,
        semantic_summary_private=f"{chunk_type.value.replace('_', ' ').title()}: {normalized_text}",
        embedding_text_private=f"{context} | {chunk_type.value} | {normalized_text}",
        bounding_box=bounding_box,
        reading_order=reading_order,
        table_id=table_id,
        row_index=row_index,
        column_headers_private=column_headers,
        parent_region_id=parent_region_id,
        source_region_ids=source_region_ids,
        entity_mentions=mentions,
        candidate_assertions=assertions,
        candidate_money_components=money,
        query_families=_query_families(chunk_type, assertions, mentions, money),
        graph_candidates=_graph_candidates(chunk_id, assertions, mentions, money),
        source_hash=_hash(raw_text),
        extraction_method=extraction_method,
        extraction_confidence=Decimal("1.00"),
        chunk_completeness=Decimal("1.00"),
        validation_status=ValidationStatus.ACCEPTED,
        privacy_class=PrivacyStatus.PRIVATE,
    )


def _union_bounds(cells: tuple[TableCell, ...]) -> BoundingBox:
    bounds = tuple(cell.bbox for cell in cells if cell.bbox is not None)
    if not bounds:
        raise ValueError("table row has no source geometry")
    return BoundingBox(
        x0=min(bound.x0 for bound in bounds),
        y0=min(bound.y0 for bound in bounds),
        x1=max(bound.x1 for bound in bounds),
        y1=max(bound.y1 for bound in bounds),
    )


def _column_headers(table: TableRecord) -> tuple[str, ...]:
    headers: list[str] = []
    for column_index in range(table.column_count):
        header = next(
            (
                cell.normalized_text_private
                for cell in table.cells
                if cell.is_header
                and cell.column_index <= column_index < cell.column_index + cell.column_span
            ),
            "",
        )
        headers.append(header)
    return tuple(headers)


def _row_amount(
    raw_text: str,
    row_cells: tuple[TableCell, ...],
    headers: tuple[str, ...],
) -> tuple[str, int, int] | None:
    amount_labels = ("amount", "price", "total", "value", "rate")
    for cell in row_cells:
        header = headers[cell.column_index].casefold() if cell.column_index < len(headers) else ""
        if not any(label in header for label in amount_labels):
            continue
        value = cell.raw_text_private.strip()
        if not re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?", value):
            continue
        start = raw_text.rfind(value)
        if start >= 0:
            return value, start, start + len(value)
    return None


def _table_regions(table: TableRecord, page_number: int) -> tuple[_Region, ...]:
    cells = tuple(sorted(table.cells, key=lambda cell: (cell.row_index, cell.column_index)))
    rows: dict[int, tuple[TableCell, ...]] = {
        row_index: tuple(cell for cell in cells if cell.row_index == row_index)
        for row_index in range(table.row_count)
    }
    rendered_rows = tuple(
        " | ".join(cell.raw_text_private.strip() for cell in rows[row_index])
        for row_index in range(table.row_count)
        if rows[row_index]
    )
    regions = [
        _Region(
            raw_text="\n".join(rendered_rows),
            chunk_type=ChunkType.ITEM_TABLE,
            bbox=table.bbox,
            source_region_ids=tuple(cell.cell_id for cell in cells),
            sort_key=(table.bbox.y0, table.bbox.x0, 1, 0),
            table_id=table.table_id,
            parent_region_id=f"page_{page_number:03}",
        )
    ]
    headers = _column_headers(table)
    for row_index in range(table.row_count):
        row_cells = rows[row_index]
        if not row_cells or all(cell.is_header for cell in row_cells):
            continue
        raw_text = " | ".join(cell.raw_text_private.strip() for cell in row_cells)
        if not raw_text.strip(" |"):
            continue
        bounds = _union_bounds(row_cells)
        regions.append(
            _Region(
                raw_text=raw_text,
                chunk_type=ChunkType.ITEM_ROW,
                bbox=bounds,
                source_region_ids=tuple(cell.cell_id for cell in row_cells),
                sort_key=(bounds.y0, bounds.x0, 2, row_index),
                table_id=table.table_id,
                row_index=row_index,
                column_headers=headers,
                parent_region_id=table.table_id,
                table_amount=_row_amount(raw_text, row_cells, headers),
            )
        )
    return tuple(regions)


def _document_regions(processed: ProcessedDocument) -> tuple[tuple[int, _Region], ...]:
    regions: list[tuple[int, _Region]] = []
    for page in processed.pages:
        for block in page.text_blocks:
            regions.append(
                (
                    page.page_number,
                    _Region(
                        raw_text=block.text_private,
                        chunk_type=_classify_chunk(block.text_private),
                        bbox=block.bbox,
                        source_region_ids=(block.block_id,),
                        sort_key=(block.bbox.y0, block.bbox.x0, 0, block.reading_order),
                        parent_region_id=f"page_{page.page_number:03}",
                    ),
                )
            )
        for table in page.tables:
            regions.extend(
                (page.page_number, region) for region in _table_regions(table, page.page_number)
            )
    return tuple(
        sorted(
            regions,
            key=lambda item: (item[0], *item[1].sort_key),
        )
    )


def chunk_document(processed: ProcessedDocument) -> ChunkingResult:
    source_id = processed.manifest.document_id
    strategy = route_document_strategy(processed.manifest.probable_document_type)
    if strategy is ChunkStrategy.UNKNOWN_LAYOUT:
        return ChunkingResult(
            source_kind=EvidenceSourceKind.DOCUMENT,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("unknown_document_role",),
        )
    if (
        processed.manifest.processing_status is not ProcessingStatus.COMPLETE
        or not processed.document.quality_accepted
    ):
        return ChunkingResult(
            source_kind=EvidenceSourceKind.DOCUMENT,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("phase1_quality_rejected",),
        )

    regions = _document_regions(processed)
    if not regions:
        return ChunkingResult(
            source_kind=EvidenceSourceKind.DOCUMENT,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("no_chunkable_regions",),
        )
    context = (
        f"{processed.manifest.probable_platform.value} "
        f"{processed.manifest.probable_document_type.value}"
    )
    chunks = tuple(
        _build_chunk(
            source_kind=EvidenceSourceKind.DOCUMENT,
            source_id=source_id,
            raw_text=region.raw_text,
            chunk_type=region.chunk_type,
            context=context,
            reading_order=reading_order,
            source_region_ids=region.source_region_ids,
            extraction_method=processed.pages[page_number - 1].extraction_method,
            bounding_box=region.bbox,
            page_number=page_number,
            table_id=region.table_id,
            row_index=region.row_index,
            column_headers=region.column_headers,
            parent_region_id=region.parent_region_id,
            table_amount=region.table_amount,
        )
        for reading_order, (page_number, region) in enumerate(regions)
    )
    return ChunkingResult(
        source_kind=EvidenceSourceKind.DOCUMENT,
        source_id=source_id,
        strategy=strategy,
        chunks=chunks,
        validation_status=ValidationStatus.ACCEPTED,
    )


def chunk_message(message: SourceMessage) -> ChunkingResult:
    raw_text = message.body_text_private.strip() or message.subject_private.strip()
    if not raw_text:
        return ChunkingResult(
            source_kind=EvidenceSourceKind.MESSAGE,
            source_id=message.message_id,
            strategy=ChunkStrategy.MESSAGE_ORDER,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("no_message_text",),
        )
    source_region = "body" if message.body_text_private.strip() else "subject"
    chunk = _build_chunk(
        source_kind=EvidenceSourceKind.MESSAGE,
        source_id=message.message_id,
        raw_text=raw_text,
        chunk_type=_classify_chunk(raw_text),
        context=f"{message.platform.value} {message.category.value} email order evidence",
        reading_order=0,
        source_region_ids=(f"{message.message_id}:{source_region}",),
        extraction_method=ExtractionMethod.EMAIL,
    )
    return ChunkingResult(
        source_kind=EvidenceSourceKind.MESSAGE,
        source_id=message.message_id,
        strategy=ChunkStrategy.MESSAGE_ORDER,
        chunks=(chunk,),
        validation_status=ValidationStatus.ACCEPTED,
    )


def validate_chunk_proposals(
    *,
    source_kind: EvidenceSourceKind,
    source_id: str,
    strategy: ChunkStrategy,
    proposals: Sequence[Mapping[str, object]],
) -> ChunkingResult:
    if not proposals:
        return ChunkingResult(
            source_kind=source_kind,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("empty_chunk_proposal",),
        )
    try:
        chunks = tuple(EvidenceChunk.model_validate(proposal) for proposal in proposals)
    except ValidationError:
        return ChunkingResult(
            source_kind=source_kind,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("invalid_chunk_proposal",),
        )
    if any(chunk.validation_status is not ValidationStatus.ACCEPTED for chunk in chunks) or len(
        {chunk.chunk_id for chunk in chunks}
    ) != len(chunks):
        return ChunkingResult(
            source_kind=source_kind,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("invalid_chunk_proposal",),
        )
    try:
        return ChunkingResult(
            source_kind=source_kind,
            source_id=source_id,
            strategy=strategy,
            chunks=chunks,
            validation_status=ValidationStatus.ACCEPTED,
        )
    except ValidationError:
        return ChunkingResult(
            source_kind=source_kind,
            source_id=source_id,
            strategy=strategy,
            chunks=(),
            validation_status=ValidationStatus.QUARANTINED,
            quarantine_reasons=("invalid_chunk_proposal",),
        )


def _atomic_private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_chunk_result(result: ChunkingResult, output_root: Path) -> Path:
    chunk_root = (
        output_root / result.source_id
        if result.source_kind is EvidenceSourceKind.DOCUMENT
        else output_root / "_messages" / result.source_id
    )
    manifest = result.model_dump(mode="json", exclude={"chunks"})
    manifest["chunk_schema_version"] = CHUNK_SCHEMA_VERSION
    _atomic_private_write(
        chunk_root / "chunk-manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    _atomic_private_write(
        chunk_root / "chunks.jsonl",
        "".join(f"{chunk.model_dump_json()}\n" for chunk in result.chunks).encode(),
    )
    quarantine_path = chunk_root / "chunk-quarantine.json"
    if result.validation_status is ValidationStatus.QUARANTINED:
        quarantine = {
            "reasons": result.quarantine_reasons,
            "source_id": result.source_id,
        }
        _atomic_private_write(
            quarantine_path,
            f"{json.dumps(quarantine, indent=2, sort_keys=True)}\n".encode(),
        )
    else:
        quarantine_path.unlink(missing_ok=True)
    return chunk_root


def read_processed_document(document_root: Path) -> ProcessedDocument:
    manifest = DocumentManifest.model_validate_json(
        (document_root / "manifest.json").read_text(encoding="utf-8")
    )
    document = DocumentRecord.model_validate_json(
        (document_root / "document.json").read_text(encoding="utf-8")
    )
    pages = tuple(
        PageRecord.model_validate_json(line)
        for line in (document_root / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    return ProcessedDocument(manifest=manifest, document=document, pages=pages)


def _inventory_sources(
    processed_root: Path,
) -> tuple[tuple[SourceDocument, ...], tuple[SourceMessage, ...]]:
    inventory_root = processed_root / "_inventory"
    documents = tuple(
        SourceDocument.model_validate_json(line)
        for line in (inventory_root / "documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    messages = tuple(
        SourceMessage.model_validate_json(line)
        for line in (inventory_root / "source_messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    )
    return documents, messages


def build_chunk_archive(processed_root: Path) -> ChunkArchiveSummary:
    documents, messages = _inventory_sources(processed_root)
    results = tuple(
        chunk_document(read_processed_document(processed_root / document.document_id))
        for document in documents
    ) + tuple(chunk_message(message) for message in messages)
    for result in results:
        write_chunk_result(result, processed_root)
    chunks = tuple(chunk for result in results for chunk in result.chunks)
    return ChunkArchiveSummary(
        document_sources=len(documents),
        message_sources=len(messages),
        accepted_sources=sum(
            result.validation_status is ValidationStatus.ACCEPTED for result in results
        ),
        quarantined_sources=sum(
            result.validation_status is ValidationStatus.QUARANTINED for result in results
        ),
        chunks=len(chunks),
        assertions=sum(len(chunk.candidate_assertions) for chunk in chunks),
        entity_mentions=sum(len(chunk.entity_mentions) for chunk in chunks),
        money_candidates=sum(len(chunk.candidate_money_components) for chunk in chunks),
    )


def _chunk_archive_hash(paths: tuple[Path, ...], root: Path) -> str:
    digest = sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def evaluate_chunk_archive(processed_root: Path) -> ChunkBenchmarkSummary:
    documents, messages = _inventory_sources(processed_root)
    source_roots = tuple(processed_root / document.document_id for document in documents) + tuple(
        processed_root / "_messages" / message.message_id for message in messages
    )
    valid_chunks: list[EvidenceChunk] = []
    invalid_chunks = 0
    accepted_sources = 0
    quarantined_sources = 0
    evaluated_sources = 0
    archive_paths: list[Path] = []
    messages_with_one_chunk = 0

    for source_root in source_roots:
        manifest_path = source_root / "chunk-manifest.json"
        chunks_path = source_root / "chunks.jsonl"
        if not manifest_path.is_file() or not chunks_path.is_file():
            continue
        archive_paths.extend((manifest_path, chunks_path))
        evaluated_sources += 1
        parsed_chunks: list[EvidenceChunk] = []
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            try:
                parsed_chunks.append(EvidenceChunk.model_validate_json(line))
            except ValidationError:
                invalid_chunks += 1
        valid_chunks.extend(parsed_chunks)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("validation_status") == ValidationStatus.ACCEPTED.value:
            accepted_sources += 1
        else:
            quarantined_sources += 1
            quarantine_path = source_root / "chunk-quarantine.json"
            if quarantine_path.is_file():
                archive_paths.append(quarantine_path)
        if source_root.parent.name == "_messages" and len(parsed_chunks) == 1:
            messages_with_one_chunk += 1

    mail_only_ids = {
        message.message_id for message in messages if not message.attachment_document_ids
    }
    mail_only_chunks = tuple(chunk for chunk in valid_chunks if chunk.source_id in mail_only_ids)
    mail_only_with_order_id = {
        chunk.source_id
        for chunk in mail_only_chunks
        if any(
            assertion.fact_type is CandidateFactType.ORDER_ID
            for assertion in chunk.candidate_assertions
        )
    }
    mail_only_with_merchant = {
        chunk.source_id
        for chunk in mail_only_chunks
        if any(mention.entity_type is EntityType.MERCHANT for mention in chunk.entity_mentions)
    }
    mail_only_with_money = {
        chunk.source_id for chunk in mail_only_chunks if chunk.candidate_money_components
    }
    phase1_tables = sum(
        read_processed_document(processed_root / document.document_id).document.table_count
        for document in documents
    )
    item_table_chunks = sum(chunk.chunk_type is ChunkType.ITEM_TABLE for chunk in valid_chunks)
    candidate_count = sum(len(chunk.candidate_assertions) for chunk in valid_chunks)
    mention_count = sum(len(chunk.entity_mentions) for chunk in valid_chunks)
    money_count = sum(len(chunk.candidate_money_components) for chunk in valid_chunks)
    expected_sources = len(documents) + len(messages)
    passed = (
        evaluated_sources == expected_sources
        and accepted_sources + quarantined_sources == expected_sources
        and invalid_chunks == 0
        and item_table_chunks == phase1_tables
        and messages_with_one_chunk == len(messages)
    )
    return ChunkBenchmarkSummary(
        expected_sources=expected_sources,
        evaluated_sources=evaluated_sources,
        accepted_sources=accepted_sources,
        quarantined_sources=quarantined_sources,
        valid_chunks=len(valid_chunks),
        invalid_chunks=invalid_chunks,
        phase1_tables=phase1_tables,
        item_table_chunks=item_table_chunks,
        message_sources=len(messages),
        messages_with_one_chunk=messages_with_one_chunk,
        mail_only_sources=len(mail_only_ids),
        mail_only_with_order_id=len(mail_only_with_order_id),
        mail_only_with_merchant=len(mail_only_with_merchant),
        mail_only_with_money=len(mail_only_with_money),
        candidate_assertions=candidate_count,
        entity_mentions=mention_count,
        money_candidates=money_count,
        unsupported_candidate_rate=(
            Decimal(invalid_chunks) / Decimal(len(valid_chunks) + invalid_chunks)
            if valid_chunks or invalid_chunks
            else Decimal("0")
        ),
        archive_sha256=_chunk_archive_hash(tuple(archive_paths), processed_root),
        passed=passed,
    )
