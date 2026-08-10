from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from lunarbit.models import (
    DocumentRole,
    OrderCategory,
    OrderEvidence,
    OrderEvidenceKind,
    Platform,
    SourceDocument,
    SourceMessage,
)
from lunarbit.resolve import (
    AgenticOrderRegionReference,
    OrderIdentityStatus,
    ResolutionSignal,
    ResolutionStatus,
    link_agentic_regions_to_order_evidence,
    public_order_id,
    resolve_order_evidence,
)


def _message(
    suffix: str,
    *,
    platform: Platform = Platform.SWIGGY,
    category: OrderCategory = OrderCategory.FOOD,
    documents: tuple[str, ...] = (),
) -> SourceMessage:
    message_id = f"msg_{suffix:0>16}"
    return SourceMessage(
        message_id=message_id,
        raw_sha256=sha256(message_id.encode()).hexdigest(),
        platform=platform,
        category=category,
        occurred_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
        source_locator_private=f"fixture:{message_id}",
        attachment_document_ids=documents,
    )


def _document(suffix: str, message_id: str) -> SourceDocument:
    document_id = f"doc_{suffix:0>16}"
    return SourceDocument(
        document_id=document_id,
        sha256=sha256(document_id.encode()).hexdigest(),
        message_id=message_id,
        platform=Platform.SWIGGY,
        category=OrderCategory.FOOD,
        role=DocumentRole.SWIGGY_RESTAURANT_INVOICE,
        source_filename_private="invoice.pdf",
        source_locator_private=f"fixture:{document_id}",
        mime_type="application/pdf",
        byte_count=100,
        page_count=1,
        native_text_available=True,
    )


def _evidence(
    evidence_id: str,
    message_id: str,
    kind: OrderEvidenceKind,
    order_id: str | None,
) -> OrderEvidence:
    return OrderEvidence(
        evidence_id=evidence_id,
        message_id=message_id,
        platform=Platform.SWIGGY,
        kind=kind,
        order_id_private=order_id,
    )


def test_order_resolution_is_deterministic_reversible_and_provenance_complete() -> None:
    ordinary_document_id = "doc_0000000000000001"
    history_document_id = "doc_0000000000000002"
    ordinary = _message("1", documents=(ordinary_document_id,))
    history = _message("2", documents=(history_document_id,))
    provisional = _message("3")
    documents = (
        _document("1", ordinary.message_id),
        _document("2", history.message_id),
    )
    evidence = (
        _evidence(
            "ordinary-111",
            ordinary.message_id,
            OrderEvidenceKind.PDF_BUNDLE,
            "111111111111111",
        ),
        _evidence(
            "history-111",
            history.message_id,
            OrderEvidenceKind.HISTORY_ROW,
            "111111111111111",
        ),
        _evidence(
            "history-222",
            history.message_id,
            OrderEvidenceKind.HISTORY_ROW,
            "222222222222222",
        ),
        _evidence(
            "mail-provisional",
            provisional.message_id,
            OrderEvidenceKind.EMAIL_ONLY,
            None,
        ),
    )
    region_links = {
        "ordinary-111": (uuid4(), uuid4()),
        "history-111": (uuid4(),),
        "history-222": (uuid4(),),
        "mail-provisional": (uuid4(),),
    }
    decided_at = datetime(2026, 8, 11, tzinfo=UTC)

    archive = resolve_order_evidence(
        (ordinary, history, provisional),
        documents,
        evidence,
        region_links_by_evidence_id=region_links,
        decided_at=decided_at,
    )
    replay = resolve_order_evidence(
        tuple(reversed((ordinary, history, provisional))),
        tuple(reversed(documents)),
        tuple(reversed(evidence)),
        region_links_by_evidence_id={
            key: tuple(reversed(value)) for key, value in reversed(tuple(region_links.items()))
        },
        decided_at=decided_at,
    )

    assert archive == replay
    assert archive.summary.resolved_orders == 2
    assert archive.summary.provisional_orders == 1
    assert archive.summary.duplicate_evidence_records == 1
    assert archive.summary.total_orders == 3
    assert len(archive.candidates) == 4
    assert len(archive.bundles) == 3
    assert len(archive.decisions) == 3

    resolved = next(
        order for order in archive.orders if order.platform_order_id_private == "111111111111111"
    )
    assert resolved.identity_status is OrderIdentityStatus.RESOLVED
    assert len(resolved.candidate_ids) == 2
    bundle = next(item for item in archive.bundles if item.order_id == resolved.order_id)
    assert set(bundle.message_ids) == {ordinary.message_id, history.message_id}
    assert set(bundle.document_ids) == {ordinary_document_id, history_document_id}
    assert set(bundle.agentic_region_ids) == {
        *region_links["ordinary-111"],
        *region_links["history-111"],
    }
    decision = next(
        item for item in archive.decisions if item.resolution_id == resolved.resolution_id
    )
    assert decision.status is ResolutionStatus.RESOLVED
    assert ResolutionSignal.EXACT_PLATFORM_ORDER_ID in decision.positive_signals
    assert ResolutionSignal.DUPLICATE_HISTORY_EVIDENCE in decision.positive_signals
    assert decision.candidate_ids == resolved.candidate_ids

    provisional_order = next(
        order
        for order in archive.orders
        if order.identity_status is OrderIdentityStatus.PROVISIONAL
    )
    assert provisional_order.platform_order_id_private is None
    assert provisional_order.provisional_fingerprint_private == provisional.message_id
    provisional_decision = next(
        item for item in archive.decisions if item.resolution_id == provisional_order.resolution_id
    )
    assert provisional_decision.status is ResolutionStatus.PROVISIONAL
    assert provisional_decision.positive_signals == (ResolutionSignal.SINGLE_MESSAGE_EVIDENCE,)

    all_candidate_ids = [
        candidate_id for order in archive.orders for candidate_id in order.candidate_ids
    ]
    assert sorted(all_candidate_ids) == sorted(
        candidate.candidate_id for candidate in archive.candidates
    )


def test_order_resolution_rejects_missing_or_cross_platform_source_ownership() -> None:
    message = _message("1")
    missing_message_evidence = _evidence(
        "missing-message",
        "msg_0000000000009999",
        OrderEvidenceKind.EMAIL_ONLY,
        "111111111111111",
    )
    cross_platform_evidence = OrderEvidence(
        evidence_id="cross-platform",
        message_id=message.message_id,
        platform=Platform.ZOMATO,
        kind=OrderEvidenceKind.EMAIL_ONLY,
        order_id_private="1234567890",
    )

    with pytest.raises(ValueError, match="unknown source message"):
        resolve_order_evidence(
            (message,),
            (),
            (missing_message_evidence,),
            decided_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="platform and category"):
        resolve_order_evidence(
            (message,),
            (),
            (cross_platform_evidence,),
            decided_at=datetime(2026, 8, 11, tzinfo=UTC),
        )


def test_public_order_ids_are_keyed_stable_and_do_not_expose_private_ids() -> None:
    private_order_id = "111111111111111"
    key = b"a deterministic fixture key with at least 32 bytes"
    order_id = UUID("967dd360-35af-5ce1-b6bb-0c5dd4e17a83")

    first = public_order_id(
        order_id=order_id,
        platform=Platform.SWIGGY,
        private_order_id=private_order_id,
        key=key,
    )
    second = public_order_id(
        order_id=order_id,
        platform=Platform.SWIGGY,
        private_order_id=private_order_id,
        key=key,
    )

    assert first == second
    assert first.startswith("ORD-SW-")
    assert private_order_id not in first
    assert (
        public_order_id(
            order_id=order_id,
            platform=Platform.SWIGGY,
            private_order_id=private_order_id,
            key=b"a different fixture key with at least 32 bytes",
        )
        != first
    )
    with pytest.raises(ValueError, match="at least 32 bytes"):
        public_order_id(
            order_id=order_id,
            platform=Platform.SWIGGY,
            private_order_id=private_order_id,
            key=b"short",
        )


def test_agentic_region_links_use_bundle_scope_but_isolate_history_rows_by_order_id() -> None:
    ordinary_document_id = "doc_0000000000000001"
    history_document_id = "doc_0000000000000002"
    ordinary = _message("1", documents=(ordinary_document_id,))
    history = _message("2", documents=(history_document_id,))
    evidence = (
        _evidence(
            "ordinary-111",
            ordinary.message_id,
            OrderEvidenceKind.PDF_BUNDLE,
            "111111111111111",
        ),
        _evidence(
            "history-111",
            history.message_id,
            OrderEvidenceKind.HISTORY_ROW,
            "111111111111111",
        ),
        _evidence(
            "history-222",
            history.message_id,
            OrderEvidenceKind.HISTORY_ROW,
            "222222222222222",
        ),
    )
    ordinary_region = AgenticOrderRegionReference(
        region_id=UUID("10000000-0000-0000-0000-000000000001"),
        source_ids=(ordinary_document_id,),
        order_ids_private=(),
    )
    first_history_region = AgenticOrderRegionReference(
        region_id=UUID("20000000-0000-0000-0000-000000000001"),
        source_ids=(history_document_id,),
        order_ids_private=("111111111111111",),
    )
    second_history_region = AgenticOrderRegionReference(
        region_id=UUID("20000000-0000-0000-0000-000000000002"),
        source_ids=(history_document_id,),
        order_ids_private=("222222222222222",),
    )

    links = link_agentic_regions_to_order_evidence(
        (ordinary, history),
        evidence,
        (ordinary_region, first_history_region, second_history_region),
    )

    assert links == {
        "history-111": (first_history_region.region_id,),
        "history-222": (second_history_region.region_id,),
        "ordinary-111": (ordinary_region.region_id,),
    }
