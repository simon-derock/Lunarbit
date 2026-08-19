from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic import FinancialEventType
from lunarbit.economic_pipeline import compile_economic_intelligence
from lunarbit.finance import (
    EpistemicMode,
    FinancialComponentType,
    FinancialScope,
    FundingStatus,
    MoneyComponent,
    TruthScope,
)
from lunarbit.financial_chunks import FinancialChunkLevel
from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelationshipType,
)
from lunarbit.models import (
    DocumentRole,
    OrderCategory,
    Platform,
    SourceDocument,
    SourceMessage,
)

MESSAGE_ID = "msg_0000000000000001"
DOCUMENT_ID = "doc_0000000000000001"
ORDER_ID = UUID("20000000-0000-0000-0000-000000000001")
COMPONENT_ID = UUID("10000000-0000-0000-0000-000000000001")
CHUNK_ID = UUID("30000000-0000-0000-0000-000000000001")
OUTLET_ID = "outlet:40000000-0000-0000-0000-000000000001"
MERCHANT_ID = "merchant:50000000-0000-0000-0000-000000000001"
SOURCE_HASH = "a" * 64


def _occurred_at() -> datetime:
    return datetime(2024, 5, 6, 12, 30, tzinfo=UTC)


def _message(*, occurred_at: datetime | None = None) -> SourceMessage:
    return SourceMessage(
        message_id=MESSAGE_ID,
        raw_sha256="b" * 64,
        platform=Platform.ZOMATO,
        category=OrderCategory.FOOD,
        occurred_at=_occurred_at() if occurred_at is None else occurred_at,
        source_locator_private="mailbox/message.eml",
    )


def _document() -> SourceDocument:
    return SourceDocument(
        document_id=DOCUMENT_ID,
        sha256="c" * 64,
        message_id=MESSAGE_ID,
        platform=Platform.ZOMATO,
        category=OrderCategory.FOOD,
        role=DocumentRole.ZOMATO_MERCHANT_INVOICE,
        source_filename_private="invoice.pdf",
        source_locator_private="mailbox/invoice.pdf",
        mime_type="application/pdf",
        byte_count=100,
        page_count=1,
        native_text_available=True,
    )


def _component(
    *,
    source_id: str = DOCUMENT_ID,
    component_type: FinancialComponentType = FinancialComponentType.PACKING_CHARGE,
) -> MoneyComponent:
    return MoneyComponent(
        component_id=COMPONENT_ID,
        source_component_id=UUID("60000000-0000-0000-0000-000000000001"),
        order_ids=(ORDER_ID,),
        component_type=component_type,
        amount=Decimal("12.00"),
        source_amount_string_private="12.00",
        currency="INR",
        source_precision=2,
        scope=FinancialScope.ORDER,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        funding_status=FundingStatus.UNRESOLVED,
        source_id=source_id,
        source_chunk_id=CHUNK_ID,
    )


def _graph() -> CanonicalGraph:
    nodes = (
        GraphNode(node_id=f"order:{ORDER_ID}", labels=(NodeLabel.ORDER,), properties={}),
        GraphNode(
            node_id=f"money:{COMPONENT_ID}",
            labels=(NodeLabel.MONEY_COMPONENT,),
            properties={},
        ),
        GraphNode(
            node_id=f"chunk:{CHUNK_ID}",
            labels=(NodeLabel.EVIDENCE_CHUNK,),
            properties={
                "source_hash": SOURCE_HASH,
                "semantic_summary_private": "Packing fee asserted by the merchant invoice.",
                "normalized_text_private": "Packing charge INR 12.00",
            },
        ),
        GraphNode(node_id=OUTLET_ID, labels=(NodeLabel.OUTLET,), properties={}),
        GraphNode(node_id=MERCHANT_ID, labels=(NodeLabel.MERCHANT,), properties={}),
    )
    relationships = (
        GraphRelationship(
            relationship_id="relationship:ordered-from",
            relationship_type=RelationshipType.ORDERED_FROM,
            source_node_id=f"order:{ORDER_ID}",
            target_node_id=OUTLET_ID,
            properties={},
        ),
        GraphRelationship(
            relationship_id="relationship:outlet-of",
            relationship_type=RelationshipType.OUTLET_OF,
            source_node_id=OUTLET_ID,
            target_node_id=MERCHANT_ID,
            properties={},
        ),
    )
    return CanonicalGraph(nodes=nodes, relationships=relationships)


def test_pipeline_resolves_document_time_and_builds_closed_financial_views() -> None:
    result = compile_economic_intelligence(
        (_message(),),
        (_document(),),
        (_component(),),
        _graph(),
    )

    assert result.summary.source_components == 1
    assert result.summary.financial_events == 1
    assert result.summary.evidence_cells == 1
    assert result.events[0].event_type is FinancialEventType.CHARGE_ASSESSED
    assert result.events[0].occurred_at == _occurred_at()
    assert result.events[0].observed_at == _occurred_at()
    assert result.evidence_cells[0].source_hash == SOURCE_HASH
    assert "Packing fee asserted" in result.evidence_cells[0].source_text_private
    assert {chunk.level for chunk in result.chunk_archive.chunks} == set(FinancialChunkLevel)
    assert result.summary.entity_histories == 2
    assert result.summary.research_windows == 1
    assert len(result.graph.nodes) == len(_graph().nodes) + 1
    assert result.summary.graph_event_relationships == 3


def test_pipeline_resolves_message_sources_without_a_document() -> None:
    result = compile_economic_intelligence(
        (_message(),),
        (),
        (_component(source_id=MESSAGE_ID),),
        _graph(),
    )

    assert result.events[0].occurred_at == _occurred_at()
    assert result.summary.source_documents == 0


@pytest.mark.parametrize(
    ("component_type", "expected"),
    (
        (FinancialComponentType.ITEM_NET, FinancialEventType.PURCHASE_ASSERTED),
        (FinancialComponentType.COUPON_DISCOUNT, FinancialEventType.DISCOUNT_APPLIED),
        (
            FinancialComponentType.MEMBERSHIP_BENEFIT,
            FinancialEventType.MEMBERSHIP_BENEFIT_REALIZED,
        ),
        (FinancialComponentType.TAX, FinancialEventType.TAX_ASSESSED),
        (FinancialComponentType.PAYMENT_ASSERTION, FinancialEventType.PAYMENT_ASSERTED),
        (FinancialComponentType.REFUND, FinancialEventType.REFUND_ASSERTED),
        (
            FinancialComponentType.UNEXPLAINED_FINANCIAL_RESIDUAL,
            FinancialEventType.RECONCILIATION_RESIDUAL,
        ),
    ),
)
def test_pipeline_maps_financial_semantics_deterministically(
    component_type: FinancialComponentType,
    expected: FinancialEventType,
) -> None:
    result = compile_economic_intelligence(
        (_message(),),
        (_document(),),
        (_component(component_type=component_type),),
        _graph(),
    )

    assert result.events[0].event_type is expected


def test_pipeline_rejects_missing_time_or_evidence_instead_of_inventing_truth() -> None:
    missing_time = _message().model_copy(update={"occurred_at": None})
    with pytest.raises(ValueError, match="occurred_at"):
        compile_economic_intelligence(
            (missing_time,),
            (_document(),),
            (_component(),),
            _graph(),
        )

    graph_without_chunk = CanonicalGraph(
        nodes=tuple(node for node in _graph().nodes if node.node_id != f"chunk:{CHUNK_ID}"),
        relationships=_graph().relationships,
    )
    with pytest.raises(ValueError, match="evidence chunk"):
        compile_economic_intelligence(
            (_message(),),
            (_document(),),
            (_component(),),
            graph_without_chunk,
        )


def test_pipeline_is_byte_stable_under_reordered_inventory_inputs() -> None:
    unused = _message().model_copy(
        update={
            "message_id": "msg_0000000000000002",
            "raw_sha256": "d" * 64,
            "occurred_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    )
    left = compile_economic_intelligence(
        (_message(), unused),
        (_document(),),
        (_component(),),
        _graph(),
    )
    right = compile_economic_intelligence(
        (unused, _message()),
        (_document(),),
        (_component(),),
        _graph(),
    )

    assert left.model_dump_json() == right.model_dump_json()
