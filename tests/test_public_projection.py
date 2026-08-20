from __future__ import annotations

from lunarbit.public import PublicNodeLabel, assert_public_payload
from lunarbit.public_projection import (
    _GRAPH_TOTALS_CYPHER,
    _NODE_COUNTS_CYPHER,
    _RELATIONSHIP_COUNTS_CYPHER,
    AggregateRelationship,
    AggregateSnapshotSource,
    build_aggregate_snapshot,
)


def test_aggregate_projection_publishes_topology_without_private_node_values() -> None:
    snapshot = build_aggregate_snapshot(
        node_counts={
            PublicNodeLabel.ORDER: 454,
            PublicNodeLabel.MERCHANT: 87,
            PublicNodeLabel.ITEM: 1_203,
            PublicNodeLabel.MONEY_COMPONENT: 2_901,
            PublicNodeLabel.EVIDENCE: 24_675,
            PublicNodeLabel.RECONCILIATION: 454,
        },
        relationships=(
            AggregateRelationship(
                source_label=PublicNodeLabel.ORDER,
                target_label=PublicNodeLabel.MONEY_COMPONENT,
                relationship="HAS_COMPONENT",
                count=2_901,
            ),
            AggregateRelationship(
                source_label=PublicNodeLabel.MONEY_COMPONENT,
                target_label=PublicNodeLabel.EVIDENCE,
                relationship="EVIDENCED_BY",
                count=2_901,
            ),
        ),
        graph_node_count=48_784,
        graph_relationship_count=70_010,
    )

    payload = snapshot.model_dump(mode="json")

    assert snapshot.mode == "neo4j_aggregate_projection"
    assert {node.id for node in snapshot.nodes} == {
        "pub:class:order",
        "pub:class:merchant",
        "pub:class:item",
        "pub:class:money-component",
        "pub:class:evidence",
        "pub:class:reconciliation",
    }
    assert payload["edges"][0]["properties"] == {"count": 2_901}
    assert_public_payload(payload)


def test_aggregate_snapshot_source_builds_from_a_read_only_aggregate_reader() -> None:
    class Reader:
        def graph_totals(self) -> tuple[int, int]:
            return (18, 27)

        def node_counts(self) -> dict[PublicNodeLabel, int]:
            return {
                PublicNodeLabel.ORDER: 4,
                PublicNodeLabel.EVIDENCE: 9,
            }

        def relationship_counts(self, limit: int) -> tuple[AggregateRelationship, ...]:
            assert limit == 40
            return (
                AggregateRelationship(
                    source_label=PublicNodeLabel.ORDER,
                    target_label=PublicNodeLabel.EVIDENCE,
                    relationship="DOCUMENTED_BY",
                    count=4,
                ),
            )

    snapshot = AggregateSnapshotSource(Reader(), relationship_limit=40).snapshot()

    assert snapshot.metrics[0].value == "18"
    assert snapshot.metrics[1].value == "27"
    assert snapshot.nodes[0].title == "Reconstructed orders"
    assert snapshot.edges[0].relationship == "DOCUMENTED_BY"


def test_aggregate_snapshot_source_caches_only_the_safe_aggregate_projection() -> None:
    class Reader:
        calls = 0

        def graph_totals(self) -> tuple[int, int]:
            self.calls += 1
            return (18, 27)

        def node_counts(self) -> dict[PublicNodeLabel, int]:
            return {
                PublicNodeLabel.ORDER: 4,
                PublicNodeLabel.EVIDENCE: 9,
            }

        def relationship_counts(self, limit: int) -> tuple[AggregateRelationship, ...]:
            return (
                AggregateRelationship(
                    source_label=PublicNodeLabel.ORDER,
                    target_label=PublicNodeLabel.EVIDENCE,
                    relationship="DOCUMENTED_BY",
                    count=4,
                ),
            )

    reader = Reader()
    now = [100.0]
    source = AggregateSnapshotSource(
        reader,
        refresh_seconds=15,
        clock=lambda: now[0],
    )

    first = source.snapshot()
    second = source.snapshot()
    now[0] = 115.0
    refreshed = source.snapshot()

    assert first is second
    assert refreshed is not first
    assert reader.calls == 2


def test_aggregate_queries_never_select_canonical_ids_or_properties() -> None:
    query_text = " ".join(
        (_GRAPH_TOTALS_CYPHER, _NODE_COUNTS_CYPHER, _RELATIONSHIP_COUNTS_CYPHER)
    ).casefold()

    assert "node_id" not in query_text
    assert "_private" not in query_text
    assert ".properties" not in query_text
    assert "source_hash" not in query_text
