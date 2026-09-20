from __future__ import annotations

from lunarbit.public import PublicNodeLabel, assert_public_payload
from lunarbit.public_projection import (
    _GRAPH_TOTALS_CYPHER,
    _MERCHANT_NEIGHBORHOOD_NODE_CYPHER,
    _NODE_COUNTS_CYPHER,
    _RELATIONSHIP_COUNTS_CYPHER,
    AggregateRelationship,
    AggregateSnapshotSource,
    MerchantNeighborhoodSource,
    NavigationSnapshotSource,
    build_aggregate_snapshot,
    build_merchant_neighborhood_snapshot,
)


def test_merchant_neighborhood_query_includes_direct_canonical_order_paths() -> None:
    """Canonical identity edges must remain visible after provider-path collapse."""

    assert "direct_order:LunarbitNode:Order" in _MERCHANT_NEIGHBORHOOD_NODE_CYPHER
    assert "collect(DISTINCT order) + collect(DISTINCT direct_order)" in (
        _MERCHANT_NEIGHBORHOOD_NODE_CYPHER
    )
    assert "UNWIND orders AS selected_order" in _MERCHANT_NEIGHBORHOOD_NODE_CYPHER


def _merchant_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "canonical_id": "identity:kms",
            "labels": ["LunarbitNode", "MerchantIdentity"],
            "canonical_name_private": "KMS Hakkim",
        },
        {
            "canonical_id": "listing:swiggy-kms",
            "labels": ["LunarbitNode", "Merchant"],
            "display_name_private": "KMS Hakkim - Swiggy",
            "platform": "swiggy",
        },
        {
            "canonical_id": "listing:zomato-kms",
            "labels": ["LunarbitNode", "Merchant"],
            "display_name_private": "KMS Hakkim - Zomato",
            "platform": "zomato",
        },
        {"canonical_id": "outlet:swiggy-kms", "labels": ["LunarbitNode", "Outlet"]},
        {"canonical_id": "outlet:zomato-kms", "labels": ["LunarbitNode", "Outlet"]},
        {
            "canonical_id": "order:one",
            "labels": ["LunarbitNode", "Order"],
            "platform": "swiggy",
        },
        {
            "canonical_id": "order:two",
            "labels": ["LunarbitNode", "Order"],
            "platform": "zomato",
        },
        {
            "canonical_id": "item:biriyani-one",
            "labels": ["LunarbitNode", "ItemObservation"],
            "raw_name_private": "Chicken Biryani",
        },
        {
            "canonical_id": "item:biriyani-two",
            "labels": ["LunarbitNode", "ItemObservation"],
            "raw_name_private": "Chicken Biryani",
        },
        {
            "canonical_id": "platform:swiggy",
            "labels": ["LunarbitNode", "Platform"],
            "display_name_private": "Swiggy",
            "platform": "swiggy",
        },
    )


def test_merchant_neighborhood_collapses_provider_listings_to_one_hotel() -> None:
    rows = _merchant_rows()
    relationships = (
        {
            "source_id": "order:one",
            "target_id": "outlet:swiggy-kms",
            "relationship": "ORDERED_FROM",
        },
        {
            "source_id": "order:two",
            "target_id": "outlet:zomato-kms",
            "relationship": "ORDERED_FROM",
        },
        {
            "source_id": "order:one",
            "target_id": "item:biriyani-one",
            "relationship": "HAS_ITEM_OBSERVATION",
        },
        {
            "source_id": "order:two",
            "target_id": "item:biriyani-two",
            "relationship": "HAS_ITEM_OBSERVATION",
        },
        {"source_id": "order:one", "target_id": "platform:swiggy", "relationship": "PLACED_ON"},
    )

    snapshot = build_merchant_neighborhood_snapshot(
        canonical_id="identity:kms", nodes=rows, relationships=relationships
    )

    merchants = [node for node in snapshot.nodes if node.label is PublicNodeLabel.MERCHANT]
    assert len(merchants) == 1
    assert merchants[0].title == "KMS Hakkim"
    assert sum(edge.relationship == "ORDERED_FROM" for edge in snapshot.edges) == 2
    assert sum(edge.relationship == "SERVED_BY" for edge in snapshot.edges) == 2
    assert all(
        edge.target == merchants[0].id
        for edge in snapshot.edges
        if edge.relationship == "SERVED_BY"
    )
    assert all("Swiggy" not in node.title and "Zomato" not in node.title for node in merchants)
    assert_public_payload(snapshot.model_dump(mode="json"))


def test_merchant_neighborhood_source_resolves_opaque_alias_and_preserves_platform_paths() -> None:
    class Reader:
        def merchant_identity_ids(self) -> tuple[str, ...]:
            return ("identity:kms",)

        def merchant_neighborhood_nodes(self, *, canonical_id: str, limit: int):
            assert canonical_id == "identity:kms"
            assert limit == 10_000
            return _merchant_rows()

        def merchant_neighborhood_relationships(self, *, canonical_ids, limit: int):
            assert "identity:kms" in canonical_ids
            assert limit == 20_000
            return (
                {
                    "source_id": "order:one",
                    "target_id": "outlet:swiggy-kms",
                    "relationship": "ORDERED_FROM",
                },
                {
                    "source_id": "order:two",
                    "target_id": "outlet:zomato-kms",
                    "relationship": "ORDERED_FROM",
                },
            )

    from lunarbit.public_projection import _public_alias

    snapshot = MerchantNeighborhoodSource(Reader()).snapshot(_public_alias("identity:kms"))
    assert snapshot.mode == "neo4j_merchant_neighborhood"
    assert len([node for node in snapshot.nodes if node.label is PublicNodeLabel.MERCHANT]) == 1
    assert len(snapshot.edges) == 4
    assert sum(edge.relationship == "SERVED_BY" for edge in snapshot.edges) == 2


def test_merchant_neighborhood_rejects_unknown_or_malformed_alias() -> None:
    class Reader:
        def merchant_identity_ids(self) -> tuple[str, ...]:
            return ("identity:kms",)

        def merchant_neighborhood_nodes(self, *, canonical_id: str, limit: int):
            raise AssertionError("should not query an unknown alias")

        def merchant_neighborhood_relationships(self, *, canonical_ids, limit: int):
            raise AssertionError("should not query an unknown alias")

    source = MerchantNeighborhoodSource(Reader())
    import pytest

    with pytest.raises(Exception, match="public merchant"):
        source.snapshot("pub:node:not-an-alias")


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


def test_navigation_projection_is_dense_anonymized_and_frontend_closed() -> None:
    class Reader:
        def graph_totals(self) -> tuple[int, int]:
            return (48_518, 69_527)

        def node_counts(self) -> dict[PublicNodeLabel, int]:
            return {}

        def relationship_counts(self, limit: int) -> tuple[AggregateRelationship, ...]:
            return ()

        def navigation_nodes(self, *, per_class: int):
            assert per_class == 2
            return (
                {
                    "canonical_id": "order:private-1",
                    "labels": ["LunarbitNode", "Order"],
                    "platform": "swiggy",
                    "order_type": "food",
                },
                {
                    "canonical_id": "merchant:private-1",
                    "labels": ["LunarbitNode", "Merchant"],
                    "display_name_private": "Ember Kitchen",
                    "platform": "swiggy",
                },
                {
                    "canonical_id": "item:private-1",
                    "labels": ["LunarbitNode", "ItemObservation"],
                    "raw_name_private": "Biryani",
                    "platform": "swiggy",
                },
                {
                    "canonical_id": "money:private-1",
                    "labels": ["LunarbitNode", "MoneyComponent"],
                    "component_type": "delivery_charge",
                    "amount": "42.00",
                    "currency": "INR",
                },
            )

        def navigation_relationships(self, *, canonical_ids, limit: int):
            assert limit == 20
            return (
                {
                    "source_id": "order:private-1",
                    "target_id": "merchant:private-1",
                    "relationship": "ORDERED_FROM",
                },
                {
                    "source_id": "order:private-1",
                    "target_id": "item:private-1",
                    "relationship": "HAS_ITEM_OBSERVATION",
                },
                {
                    "source_id": "order:private-1",
                    "target_id": "money:private-1",
                    "relationship": "HAS_COMPONENT",
                },
            )

    snapshot = NavigationSnapshotSource(Reader(), per_class=2, relationship_limit=20).snapshot()
    payload = snapshot.model_dump(mode="json")

    assert snapshot.mode == "neo4j_navigation_projection"
    assert len(snapshot.nodes) == 4
    assert len(snapshot.edges) == 3
    assert all(node.id.startswith("pub:node:") for node in snapshot.nodes)
    assert all("private-1" not in str(node.model_dump()) for node in snapshot.nodes)
    assert_public_payload(payload)


def test_numeric_only_item_names_are_quarantined_at_public_boundary() -> None:
    from lunarbit.public_projection import _navigation_node

    node = _navigation_node(
        {
            "canonical_id": "item:numeric",
            "labels": ["LunarbitNode", "MerchantItem"],
            "display_name_private": "14.90",
        }
    )

    assert node.title == "Unresolved item observation"
    assert node.subtitle == "Numeric extraction quarantined"
