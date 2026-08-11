from __future__ import annotations

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
