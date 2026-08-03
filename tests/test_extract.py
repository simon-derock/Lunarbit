from __future__ import annotations

from hashlib import sha256
from json import dumps
from pathlib import Path

from lunarbit.extract import (
    build_source_inventory,
    classify_document_role,
    classify_platform,
    count_orders,
    document_id_from_bytes,
    extract_order_id_candidates,
    message_id_from_bytes,
)
from lunarbit.models import (
    DocumentRole,
    OrderCategory,
    OrderEvidence,
    OrderEvidenceKind,
    OrderIdSource,
    Platform,
)


def test_content_ids_are_deterministic_and_namespaced() -> None:
    payload = b"synthetic invoice bytes"

    assert document_id_from_bytes(payload) == f"doc_{sha256(payload).hexdigest()[:16]}"
    assert message_id_from_bytes(payload) == f"msg_{sha256(payload).hexdigest()[:16]}"
    assert document_id_from_bytes(payload) == document_id_from_bytes(payload)
    assert document_id_from_bytes(payload + b"!") != document_id_from_bytes(payload)


def test_platform_classification_uses_sender_and_subject() -> None:
    assert classify_platform("receipts@zomato.com", "Your order") is Platform.ZOMATO
    assert classify_platform("noreply@swiggy.in", "Your invoice") is Platform.SWIGGY
    assert classify_platform("orders@example.com", "Your Instamart order") is Platform.SWIGGY
    assert classify_platform("hello@example.com", "Interview update") is None


def test_document_roles_are_content_aware() -> None:
    assert (
        classify_document_role(
            platform=Platform.ZOMATO,
            category=OrderCategory.FOOD,
            filename="Order_ID_0000000000.pdf",
            text="Zomato Food Order: Summary and Receipt",
        )
        is DocumentRole.ZOMATO_ORDER_SUMMARY
    )
    assert (
        classify_document_role(
            platform=Platform.SWIGGY,
            category=OrderCategory.FOOD,
            filename="opaque.pdf",
            text="TAX INVOICE\nInvoice From: Swiggy Limited\nPlatform fee for Order (123456789012345)",
        )
        is DocumentRole.SWIGGY_PLATFORM_FEE_INVOICE
    )
    assert (
        classify_document_role(
            platform=Platform.SWIGGY,
            category=OrderCategory.FOOD,
            filename="opaque.pdf",
            text="Number of Orders 10\nOrder Details\nDate / Time  Order ID  Restaurant Name",
        )
        is DocumentRole.SWIGGY_ORDER_HISTORY_REPORT
    )


def test_order_id_candidates_prefer_labelled_commerce_fields() -> None:
    zomato = extract_order_id_candidates(
        Platform.ZOMATO,
        "Invoice No: 123456789012345 Order ID: 1234567890",
        source=OrderIdSource.PDF_LABEL,
    )
    swiggy = extract_order_id_candidates(
        Platform.SWIGGY,
        "Invoice No: 1234567890123456 Order ID: 123456789012345",
        source=OrderIdSource.PDF_LABEL,
    )

    assert [candidate.value_private for candidate in zomato] == ["1234567890"]
    assert [candidate.value_private for candidate in swiggy] == ["123456789012345"]


def test_order_count_deduplicates_history_and_preserves_provisional_messages() -> None:
    evidence = (
        OrderEvidence(
            evidence_id="ev_pdf_1",
            message_id="msg_pdf_1",
            platform=Platform.SWIGGY,
            kind=OrderEvidenceKind.PDF_BUNDLE,
            order_id_private="111111111111111",
        ),
        OrderEvidence(
            evidence_id="ev_mail_1",
            message_id="msg_mail_1",
            platform=Platform.ZOMATO,
            kind=OrderEvidenceKind.EMAIL_ONLY,
            order_id_private="2222222222",
        ),
        OrderEvidence(
            evidence_id="ev_history_duplicate",
            message_id="msg_history",
            platform=Platform.SWIGGY,
            kind=OrderEvidenceKind.HISTORY_ROW,
            order_id_private="111111111111111",
        ),
        OrderEvidence(
            evidence_id="ev_history_new",
            message_id="msg_history",
            platform=Platform.SWIGGY,
            kind=OrderEvidenceKind.HISTORY_ROW,
            order_id_private="333333333333333",
        ),
        OrderEvidence(
            evidence_id="ev_mail_provisional",
            message_id="msg_mail_provisional",
            platform=Platform.SWIGGY,
            kind=OrderEvidenceKind.EMAIL_ONLY,
        ),
        OrderEvidence(
            evidence_id="ev_pdf_provisional",
            message_id="msg_pdf_provisional",
            platform=Platform.SWIGGY,
            kind=OrderEvidenceKind.PDF_BUNDLE,
        ),
    )

    summary = count_orders(evidence)

    assert summary.resolved_orders == 3
    assert summary.provisional_orders == 2
    assert summary.total_orders == 5
    assert summary.history_duplicates == 1


def test_inventory_combines_pdf_backed_and_mail_only_orders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_payload = b"%PDF-1.4\nsynthetic"
    pdf_sha256 = sha256(pdf_payload).hexdigest()

    pdf_bundle = tmp_path / "zomato" / "pdf-bundle"
    pdf_attachments = pdf_bundle / "attachments"
    pdf_attachments.mkdir(parents=True)
    (pdf_bundle / "email.eml").write_bytes(b"synthetic zomato message")
    (pdf_bundle / "body.html").write_text(
        "<p>Order ID: 1234567890</p>",
        encoding="utf-8",
    )
    (pdf_attachments / "Order_ID_1234567890.pdf").write_bytes(pdf_payload)
    (pdf_bundle / "manifest.json").write_text(
        dumps(
            {
                "schemaVersion": "1.0.0",
                "orderUid": "synthetic-zomato-order",
                "vendor": "zomato",
                "category": "food",
                "orderId": "1234567890",
                "source": {"provider": "fixture"},
                "email": {
                    "internalDate": "2026-08-03T12:00:00+00:00",
                    "from": "receipts@zomato.com",
                    "subject": "Synthetic order",
                },
                "attachments": [
                    {
                        "path": "attachments/Order_ID_1234567890.pdf",
                        "filename": "Order_ID_1234567890.pdf",
                        "mimeType": "application/pdf",
                        "bytes": len(pdf_payload),
                        "sha256": pdf_sha256,
                        "validPdfSignature": True,
                    }
                ],
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    mail_bundle = tmp_path / "swiggy" / "mail-bundle"
    mail_bundle.mkdir(parents=True)
    (mail_bundle / "email.eml").write_bytes(b"synthetic swiggy message")
    (mail_bundle / "body.html").write_text(
        "<p>Order ID: 123456789012345</p>",
        encoding="utf-8",
    )
    (mail_bundle / "manifest.json").write_text(
        dumps(
            {
                "schemaVersion": "1.0.0",
                "orderUid": "synthetic-swiggy-order",
                "vendor": "swiggy",
                "category": "food",
                "orderId": "123456789012345",
                "source": {"provider": "fixture"},
                "email": {
                    "internalDate": "2026-08-03T13:00:00+00:00",
                    "from": "noreply@swiggy.in",
                    "subject": "Synthetic order",
                },
                "attachments": [],
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "lunarbit.extract.extract_pdf_text",
        lambda _: "Zomato Food Order: Summary and Receipt\nOrder ID: 1234567890",
    )
    monkeypatch.setattr("lunarbit.extract.pdf_page_count", lambda _: 1)

    inventory = build_source_inventory(tmp_path)

    assert inventory.summary.relevant_messages == 2
    assert inventory.summary.unique_pdf_documents == 1
    assert inventory.summary.pdf_pages == 1
    assert inventory.summary.pdf_backed_order_messages == 1
    assert inventory.summary.mail_only_order_messages == 1
    assert inventory.summary.orders.resolved_orders == 2
    assert inventory.summary.orders.provisional_orders == 0
    assert inventory.summary.orders.total_orders == 2
