from __future__ import annotations

from hashlib import sha256

from lunarbit.extract import (
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
