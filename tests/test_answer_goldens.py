from __future__ import annotations

from datetime import UTC, datetime

from lunarbit.answer_goldens import build_canonical_answer_goldens
from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelationshipType,
)
from lunarbit.models import OrderCategory, Platform, SourceMessage

MERCHANT = "merchant:ember"
OUTLET = "outlet:swiggy:ember"


def _message(index: int) -> SourceMessage:
    return SourceMessage(
        message_id=f"msg_{index:016x}",
        raw_sha256="a" * 64,
        platform=Platform.SWIGGY,
        category=OrderCategory.FOOD,
        occurred_at=datetime(2024 + index, 1, 1, tzinfo=UTC),
        source_locator_private=f"mail://{index}",
    )


def _graph() -> CanonicalGraph:
    nodes: list[GraphNode] = [
        GraphNode(
            node_id=MERCHANT,
            labels=(NodeLabel.MERCHANT,),
            properties={"normalized_name_private": "Ember Kitchen"},
        ),
        GraphNode(node_id=OUTLET, labels=(NodeLabel.OUTLET,), properties={}),
    ]
    relationships: list[GraphRelationship] = [
        GraphRelationship(
            relationship_id="rel:outlet-merchant",
            relationship_type=RelationshipType.OUTLET_OF,
            source_node_id=OUTLET,
            target_node_id=MERCHANT,
            properties={},
        )
    ]
    for index, (rice, rice_bowl) in enumerate(((100, 200), (120, 210)), start=1):
        order_id = f"order:{index}"
        message_id = f"msg_{index:016x}"
        nodes.extend(
            (
                GraphNode(
                    node_id=order_id,
                    labels=(NodeLabel.ORDER,),
                    properties={"platform": "swiggy"},
                ),
                GraphNode(
                    node_id=f"observation:{index}:rice",
                    labels=(NodeLabel.ITEM_OBSERVATION,),
                    properties={"observed_amount": rice, "currency": "INR"},
                ),
                GraphNode(
                    node_id=f"observation:{index}:rice-bowl",
                    labels=(NodeLabel.ITEM_OBSERVATION,),
                    properties={"observed_amount": rice_bowl, "currency": "INR"},
                ),
                GraphNode(
                    node_id=f"item:{index}:rice",
                    labels=(NodeLabel.MERCHANT_ITEM,),
                    properties={"normalized_name_private": "rice"},
                ),
                GraphNode(
                    node_id=f"item:{index}:rice-bowl",
                    labels=(NodeLabel.MERCHANT_ITEM,),
                    properties={"normalized_name_private": "rice bowl"},
                ),
                GraphNode(
                    node_id=f"message:{message_id}",
                    labels=(NodeLabel.SOURCE_MESSAGE,),
                    properties={},
                ),
            )
        )
        relationships.extend(
            (
                GraphRelationship(
                    relationship_id=f"rel:{index}:order-outlet",
                    relationship_type=RelationshipType.ORDERED_FROM,
                    source_node_id=order_id,
                    target_node_id=OUTLET,
                    properties={},
                ),
                GraphRelationship(
                    relationship_id=f"rel:{index}:order-message",
                    relationship_type=RelationshipType.DOCUMENTED_BY,
                    source_node_id=order_id,
                    target_node_id=f"message:{message_id}",
                    properties={},
                ),
                GraphRelationship(
                    relationship_id=f"rel:{index}:order-rice",
                    relationship_type=RelationshipType.HAS_ITEM_OBSERVATION,
                    source_node_id=order_id,
                    target_node_id=f"observation:{index}:rice",
                    properties={},
                ),
                GraphRelationship(
                    relationship_id=f"rel:{index}:order-rice-bowl",
                    relationship_type=RelationshipType.HAS_ITEM_OBSERVATION,
                    source_node_id=order_id,
                    target_node_id=f"observation:{index}:rice-bowl",
                    properties={},
                ),
                GraphRelationship(
                    relationship_id=f"rel:{index}:rice-item",
                    relationship_type=RelationshipType.LISTING_OF,
                    source_node_id=f"observation:{index}:rice",
                    target_node_id=f"item:{index}:rice",
                    properties={},
                ),
                GraphRelationship(
                    relationship_id=f"rel:{index}:rice-bowl-item",
                    relationship_type=RelationshipType.LISTING_OF,
                    source_node_id=f"observation:{index}:rice-bowl",
                    target_node_id=f"item:{index}:rice-bowl",
                    properties={},
                ),
            )
        )
    return CanonicalGraph(nodes=tuple(nodes), relationships=tuple(relationships))


def test_price_goldens_do_not_merge_prefix_item_names() -> None:
    goldens = build_canonical_answer_goldens(
        (_message(1), _message(2)),
        (),
        _graph(),
        cases_per_entity_family=20,
    )

    rice = next(
        golden
        for golden in goldens
        if golden.case_id.startswith("case:price-") and golden.request.slots.item_name == "rice"
    )
    rice_bowl = next(
        golden
        for golden in goldens
        if golden.case_id.startswith("case:price-")
        and golden.request.slots.item_name == "rice bowl"
    )
    assert rice.expected_fact_count == 2
    assert rice_bowl.expected_fact_count == 2
    assert rice.expected_calculation == "INR 120.00 - INR 100.00 = INR 20.00 (20.00%)"
    assert rice_bowl.expected_calculation == "INR 210.00 - INR 200.00 = INR 10.00 (5.00%)"
