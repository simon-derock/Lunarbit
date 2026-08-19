from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from pydantic import Field, model_validator

from lunarbit.economic import FinancialEvent
from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelationshipType,
)
from lunarbit.models import ContractModel

TEMPORAL_GRAPH_POLICY_VERSION = "temporal-financial-graph-v1.0.0"


class EventSupersession(ContractModel):
    new_event_id: UUID
    prior_event_id: UUID
    reason: str = Field(min_length=12, max_length=500)
    decided_at: datetime
    policy_version: str = TEMPORAL_GRAPH_POLICY_VERSION

    @model_validator(mode="after")
    def identity_and_time_are_valid(self) -> EventSupersession:
        if self.new_event_id == self.prior_event_id:
            raise ValueError("an event cannot supersede itself")
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("supersession decided_at must be timezone-aware")
        return self


def _node_id(kind: str, value: object) -> str:
    return f"{kind}:{value}"


def _relationship(
    relationship_type: RelationshipType,
    source: str,
    target: str,
    *,
    properties: dict[str, str] | None = None,
) -> GraphRelationship:
    digest = sha256(f"{relationship_type.value}|{source}|{target}".encode()).hexdigest()[:24]
    return GraphRelationship(
        relationship_id=f"relationship:{relationship_type.value.casefold()}:{digest}",
        relationship_type=relationship_type,
        source_node_id=source,
        target_node_id=target,
        properties=properties or {},
    )


def _event_node(event: FinancialEvent) -> GraphNode:
    return GraphNode(
        node_id=_node_id("financial_event", event.event_id),
        labels=(NodeLabel.FINANCIAL_EVENT,),
        properties={
            "event_type": event.event_type.value,
            "amount": str(event.amount),
            "currency": event.currency,
            "scope": event.scope.value,
            "epistemic_mode": event.epistemic_mode.value,
            "truth_scope": event.truth_scope.value,
            "occurred_at": event.occurred_at.isoformat(),
            "observed_at": event.observed_at.isoformat(),
            "valid_from": event.valid_from.isoformat(),
            "valid_to": event.valid_to.isoformat() if event.valid_to else None,
            "source_count": len(event.source_chunk_ids),
            "policy_version": event.policy_version,
            "privacy_class": "private",
        },
    )


def _detect_supersession_cycles(values: tuple[EventSupersession, ...]) -> None:
    edges: dict[UUID, list[UUID]] = defaultdict(list)
    for value in values:
        edges[value.new_event_id].append(value.prior_event_id)
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(event_id: UUID) -> None:
        if event_id in visiting:
            raise ValueError("financial event supersession graph cannot contain cycles")
        if event_id in visited:
            return
        visiting.add(event_id)
        for target in edges[event_id]:
            visit(target)
        visiting.remove(event_id)
        visited.add(event_id)

    for event_id in tuple(edges):
        visit(event_id)


def _validate_supersessions(
    events: dict[UUID, FinancialEvent],
    supersessions: tuple[EventSupersession, ...],
) -> None:
    pairs = tuple((value.new_event_id, value.prior_event_id) for value in supersessions)
    if len(set(pairs)) != len(pairs):
        raise ValueError("financial event supersessions must be unique")
    _detect_supersession_cycles(supersessions)
    for value in supersessions:
        try:
            new = events[value.new_event_id]
            prior = events[value.prior_event_id]
        except KeyError as error:
            raise ValueError("supersession references an unknown financial event") from error
        if new.event_type is not prior.event_type:
            raise ValueError("supersession events must represent the same event type")
        if new.order_ids != prior.order_ids or new.currency != prior.currency:
            raise ValueError("supersession events must retain order and currency scope")
        if prior.valid_to is None or prior.valid_to != new.valid_from:
            raise ValueError("supersession validity intervals must be contiguous")
        if new.observed_at <= prior.observed_at:
            raise ValueError("superseding evidence must be observed later")
        if value.decided_at < new.observed_at:
            raise ValueError("supersession cannot be decided before new evidence is observed")


def extend_graph_with_financial_events(
    base: CanonicalGraph,
    events: tuple[FinancialEvent, ...],
    *,
    supersessions: tuple[EventSupersession, ...] = (),
) -> CanonicalGraph:
    by_event_id = {event.event_id: event for event in events}
    if len(by_event_id) != len(events):
        raise ValueError("financial event IDs must be unique")
    _validate_supersessions(by_event_id, supersessions)
    base_node_ids = {node.node_id for node in base.nodes}
    required = {
        *(_node_id("order", order_id) for event in events for order_id in event.order_ids),
        *(
            _node_id("money", component_id)
            for event in events
            for component_id in event.component_ids
        ),
        *(_node_id("chunk", chunk_id) for event in events for chunk_id in event.source_chunk_ids),
    }
    missing = required - base_node_ids
    if missing:
        raise ValueError("temporal financial events reference missing canonical graph nodes")
    nodes_by_id = {node.node_id: node for node in base.nodes}
    relationships_by_id = {
        relationship.relationship_id: relationship for relationship in base.relationships
    }
    for event in sorted(events, key=lambda value: str(value.event_id)):
        node = _event_node(event)
        existing = nodes_by_id.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError("financial event node identity collision")
        nodes_by_id[node.node_id] = node
        event_node_id = node.node_id
        relationships = [
            *(
                _relationship(
                    RelationshipType.HAS_FINANCIAL_EVENT,
                    _node_id("order", order_id),
                    event_node_id,
                )
                for order_id in event.order_ids
            ),
            *(
                _relationship(
                    RelationshipType.EVENT_FOR_COMPONENT,
                    event_node_id,
                    _node_id("money", component_id),
                )
                for component_id in event.component_ids
            ),
            *(
                _relationship(
                    RelationshipType.EVIDENCED_BY,
                    event_node_id,
                    _node_id("chunk", chunk_id),
                )
                for chunk_id in event.source_chunk_ids
            ),
        ]
        for relationship in relationships:
            existing_relationship = relationships_by_id.get(relationship.relationship_id)
            if existing_relationship is not None and existing_relationship != relationship:
                raise ValueError("financial event relationship identity collision")
            relationships_by_id[relationship.relationship_id] = relationship
    for value in sorted(
        supersessions, key=lambda item: (str(item.new_event_id), str(item.prior_event_id))
    ):
        relationship = _relationship(
            RelationshipType.SUPERSEDES,
            _node_id("financial_event", value.new_event_id),
            _node_id("financial_event", value.prior_event_id),
            properties={
                "reason": value.reason,
                "decided_at": value.decided_at.isoformat(),
                "policy_version": value.policy_version,
            },
        )
        existing_relationship = relationships_by_id.get(relationship.relationship_id)
        if existing_relationship is not None and existing_relationship != relationship:
            raise ValueError("supersession relationship identity collision")
        relationships_by_id[relationship.relationship_id] = relationship
    return CanonicalGraph(
        nodes=tuple(sorted(nodes_by_id.values(), key=lambda value: value.node_id)),
        relationships=tuple(
            sorted(relationships_by_id.values(), key=lambda value: value.relationship_id)
        ),
    )
