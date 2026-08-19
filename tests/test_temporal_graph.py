from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic import FinancialEvent, FinancialEventType, financial_event_id
from lunarbit.finance import EpistemicMode, FinancialScope, TruthScope
from lunarbit.graph import CanonicalGraph, GraphNode, NodeLabel, RelationshipType
from lunarbit.temporal_graph import EventSupersession, extend_graph_with_financial_events

COMPONENT_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRECTED_COMPONENT_ID = UUID("10000000-0000-0000-0000-000000000002")
ORDER_ID = UUID("20000000-0000-0000-0000-000000000001")
CHUNK_ID = UUID("30000000-0000-0000-0000-000000000001")
CORRECTED_CHUNK_ID = UUID("30000000-0000-0000-0000-000000000002")


def _time(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def _event(
    *,
    observed_day: int,
    valid_from: int,
    valid_to: int | None,
    component_id: UUID = COMPONENT_ID,
    chunk_id: UUID = CHUNK_ID,
    amount: str = "12.00",
) -> FinancialEvent:
    occurred_at = _time(1)
    return FinancialEvent(
        event_id=financial_event_id(
            component_ids=(component_id,),
            event_type=FinancialEventType.CHARGE_ASSESSED,
            occurred_at=occurred_at,
        ),
        event_type=FinancialEventType.CHARGE_ASSESSED,
        component_ids=(component_id,),
        order_ids=(ORDER_ID,),
        amount=Decimal(amount),
        currency="INR",
        scope=FinancialScope.ORDER,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        occurred_at=occurred_at,
        observed_at=_time(observed_day),
        valid_from=_time(valid_from),
        valid_to=_time(valid_to) if valid_to else None,
        source_chunk_ids=(chunk_id,),
        source_hashes=(("a" if chunk_id == CHUNK_ID else "b") * 64,),
    )


def _base_graph() -> CanonicalGraph:
    return CanonicalGraph(
        nodes=(
            GraphNode(node_id=f"order:{ORDER_ID}", labels=(NodeLabel.ORDER,), properties={}),
            GraphNode(
                node_id=f"money:{COMPONENT_ID}",
                labels=(NodeLabel.MONEY_COMPONENT,),
                properties={},
            ),
            GraphNode(
                node_id=f"money:{CORRECTED_COMPONENT_ID}",
                labels=(NodeLabel.MONEY_COMPONENT,),
                properties={},
            ),
            GraphNode(
                node_id=f"chunk:{CHUNK_ID}",
                labels=(NodeLabel.EVIDENCE_CHUNK,),
                properties={},
            ),
            GraphNode(
                node_id=f"chunk:{CORRECTED_CHUNK_ID}",
                labels=(NodeLabel.EVIDENCE_CHUNK,),
                properties={},
            ),
        ),
        relationships=(),
    )


def test_temporal_event_graph_links_order_component_and_source_evidence() -> None:
    event = _event(observed_day=2, valid_from=1, valid_to=None)

    graph = extend_graph_with_financial_events(_base_graph(), (event,))
    event_node = next(node for node in graph.nodes if NodeLabel.FINANCIAL_EVENT in node.labels)
    event_relationships = {
        relationship.relationship_type
        for relationship in graph.relationships
        if event_node.node_id in {relationship.source_node_id, relationship.target_node_id}
    }

    assert event_node.properties["amount"] == "12.00"
    assert event_node.properties["occurred_at"] == _time(1).isoformat()
    assert event_node.properties["observed_at"] == _time(2).isoformat()
    assert event_relationships >= {
        RelationshipType.HAS_FINANCIAL_EVENT,
        RelationshipType.EVENT_FOR_COMPONENT,
        RelationshipType.EVIDENCED_BY,
    }


def test_temporal_extension_is_idempotent() -> None:
    event = _event(observed_day=2, valid_from=1, valid_to=None)
    once = extend_graph_with_financial_events(_base_graph(), (event,))
    twice = extend_graph_with_financial_events(once, (event,))

    assert twice == once


def test_supersession_requires_contiguous_validity_and_later_observation() -> None:
    prior = _event(observed_day=2, valid_from=1, valid_to=3)
    corrected = _event(
        observed_day=4,
        valid_from=3,
        valid_to=None,
        component_id=CORRECTED_COMPONENT_ID,
        chunk_id=CORRECTED_CHUNK_ID,
        amount="10.00",
    )
    supersession = EventSupersession(
        new_event_id=corrected.event_id,
        prior_event_id=prior.event_id,
        reason="Later source corrected the asserted fee.",
        decided_at=_time(4),
    )

    graph = extend_graph_with_financial_events(
        _base_graph(),
        (prior, corrected),
        supersessions=(supersession,),
    )

    assert any(
        relationship.relationship_type is RelationshipType.SUPERSEDES
        for relationship in graph.relationships
    )

    invalid = _event(
        observed_day=4,
        valid_from=4,
        valid_to=None,
        component_id=CORRECTED_COMPONENT_ID,
        chunk_id=CORRECTED_CHUNK_ID,
        amount="10.00",
    )
    with pytest.raises(ValueError, match="contiguous"):
        extend_graph_with_financial_events(
            _base_graph(),
            (prior, invalid),
            supersessions=(supersession.model_copy(update={"new_event_id": invalid.event_id}),),
        )
