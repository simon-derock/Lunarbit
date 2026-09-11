from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelationshipType,
    neo4j_write_batches,
)
from lunarbit.resolve import ProvisionalOutlet, ResolutionStatus
from scripts.build_graph import _primary_outlet_ids


def test_canonical_graph_rejects_duplicate_nodes_and_orphan_relationships() -> None:
    order = GraphNode(
        node_id="order:1", labels=(NodeLabel.ORDER,), properties={"status": "resolved"}
    )
    platform = GraphNode(
        node_id="platform:swiggy",
        labels=(NodeLabel.PLATFORM,),
        properties={"name": "Swiggy"},
    )
    placed_on = GraphRelationship(
        relationship_id="relationship:placed-on:1",
        relationship_type=RelationshipType.PLACED_ON,
        source_node_id=order.node_id,
        target_node_id=platform.node_id,
        properties={},
    )

    graph = CanonicalGraph(nodes=(order, platform), relationships=(placed_on,))

    assert graph.nodes == (order, platform)
    with pytest.raises(ValidationError, match="node IDs must be unique"):
        CanonicalGraph(nodes=(order, order), relationships=())
    with pytest.raises(ValidationError, match="existing graph nodes"):
        CanonicalGraph(nodes=(order,), relationships=(placed_on,))


def test_neo4j_batches_are_deterministic_idempotent_and_parameterized() -> None:
    nodes = tuple(
        GraphNode(
            node_id=f"order:{index}",
            labels=(NodeLabel.ORDER,),
            properties={"sequence": index},
        )
        for index in range(3)
    )
    graph = CanonicalGraph(nodes=nodes, relationships=())

    batches = neo4j_write_batches(graph, batch_size=2)
    replay = neo4j_write_batches(
        CanonicalGraph(nodes=tuple(reversed(nodes)), relationships=()),
        batch_size=2,
    )

    assert batches == replay
    assert [len(batch.parameters["rows"]) for batch in batches] == [2, 1]
    assert all("UNWIND $rows" in batch.cypher for batch in batches)
    assert all("MERGE" in batch.cypher for batch in batches)
    assert all("order:0" not in batch.cypher for batch in batches)


def test_outlet_paths_dedupe_per_order_and_merchant_without_dropping_evidence() -> None:
    order_id = UUID("00000000-0000-0000-0000-000000000001")
    merchant_id = UUID("00000000-0000-0000-0000-000000000002")
    first = ProvisionalOutlet(
        outlet_id=UUID("00000000-0000-0000-0000-000000000003"),
        merchant_id=merchant_id,
        order_id=order_id,
        mention_ids=(UUID("00000000-0000-0000-0000-000000000004"),),
        identity_status=ResolutionStatus.PROVISIONAL,
        resolution_id=UUID("00000000-0000-0000-0000-000000000005"),
    )
    second = first.model_copy(update={"outlet_id": UUID("00000000-0000-0000-0000-000000000006")})

    selected = _primary_outlet_ids((second, first))
    assert selected == frozenset({first.outlet_id})


def test_outlet_paths_dedupe_provider_listings_under_one_merchant_identity() -> None:
    order_id = UUID("00000000-0000-0000-0000-000000000001")
    listing_a = UUID("00000000-0000-0000-0000-000000000002")
    listing_b = UUID("00000000-0000-0000-0000-000000000003")
    identity_id = UUID("00000000-0000-0000-0000-000000000004")

    def outlet(outlet_id: str, merchant_id: UUID) -> ProvisionalOutlet:
        return ProvisionalOutlet(
            outlet_id=UUID(outlet_id),
            merchant_id=merchant_id,
            order_id=order_id,
            mention_ids=(UUID("00000000-0000-0000-0000-000000000005"),),
            identity_status=ResolutionStatus.PROVISIONAL,
            resolution_id=UUID("00000000-0000-0000-0000-000000000006"),
        )

    first = outlet("00000000-0000-0000-0000-000000000007", listing_a)
    second = outlet("00000000-0000-0000-0000-000000000008", listing_b)
    selected = _primary_outlet_ids(
        (second, first), {listing_a: identity_id, listing_b: identity_id}
    )
    assert selected == frozenset({first.outlet_id})
