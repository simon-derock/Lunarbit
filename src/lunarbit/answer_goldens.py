from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from lunarbit.answer_evaluation import AnswerFamily, AnswerGolden
from lunarbit.finance import MoneyComponent
from lunarbit.graph import CanonicalGraph, NodeLabel, RelationshipType
from lunarbit.models import SourceMessage
from lunarbit.runtime import QuerySlots, RuntimeRequest, RuntimeStatus

ANSWER_GOLDEN_POLICY_VERSION = "canonical-answer-goldens-v1.0.0"


def _case_id(family: str, identity: str) -> str:
    digest = sha256(identity.encode()).hexdigest()[:16]
    return f"case:{family}-{digest}"


def _financial_calculation(components: tuple[MoneyComponent, ...]) -> str:
    ordered = tuple(sorted(components, key=lambda value: f"money:{value.component_id}"))
    currency = ordered[0].currency
    total = sum((value.amount for value in ordered), start=Decimal("0"))
    if len(ordered) <= 20:
        terms = " + ".join(f"{currency} {value.amount:.2f}" for value in ordered)
        return f"{terms} = {currency} {total:.2f}"
    canonical_terms = "\n".join(
        f"money:{value.component_id}|{currency}|{value.amount}" for value in ordered
    )
    return (
        f"Decimal sum of {len(ordered)} distinct source-backed components = "
        f"{currency} {total:.2f}; ordered-term SHA-256="
        f"{sha256(canonical_terms.encode()).hexdigest()}"
    )


def _financial_goldens(
    components: tuple[MoneyComponent, ...],
    graph: CanonicalGraph,
) -> tuple[AnswerGolden, ...]:
    order_platform = {
        node.node_id.removeprefix("order:"): str(node.properties["platform"])
        for node in graph.nodes
        if NodeLabel.ORDER in node.labels
    }
    grouped: dict[tuple[str, str], list[MoneyComponent]] = defaultdict(list)
    for component in components:
        platforms = {
            order_platform[str(order_id)]
            for order_id in component.order_ids
            if str(order_id) in order_platform
        }
        if len(platforms) != 1:
            continue
        grouped[(platforms.pop(), component.component_type.value)].append(component)
    preferred_types = {
        "platform_fee",
        "delivery_charge",
        "tax",
        "coupon_discount",
        "packing_charge",
        "handling_fee",
    }
    values: list[AnswerGolden] = []
    for (platform, component_type), items in sorted(grouped.items()):
        if component_type not in preferred_types or len(items) > 2_400:
            continue
        ordered = tuple(sorted(items, key=lambda value: str(value.component_id)))
        currency = ordered[0].currency
        if any(item.currency != currency for item in ordered):
            continue
        total = sum((item.amount for item in ordered), start=Decimal("0"))
        noun = "component" if len(ordered) == 1 else "components"
        component_label = component_type.replace("_", " ")
        values.append(
            AnswerGolden(
                case_id=_case_id("financial", f"{platform}|{component_type}"),
                family=AnswerFamily.FINANCIAL_AGGREGATION,
                request=RuntimeRequest(
                    question=f"How much {component_label} did I pay?",
                    slots=QuerySlots(
                        platform=platform,
                        component_type=component_type,
                        limit=200,
                    ),
                ),
                expected_status=RuntimeStatus.VERIFIED,
                expected_fact_count=len(ordered),
                expected_direct_answer=(
                    f"The evidence-backed {component_label} total for {platform.title()} is "
                    f"{currency} {total:.2f} across {len(ordered)} distinct {noun}."
                ),
                expected_calculation=_financial_calculation(ordered),
                minimum_citations=len(ordered),
                expected_abstention_reason=None,
            )
        )
    return tuple(values)


def _graph_maps(
    graph: CanonicalGraph,
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    order_outlets: dict[str, set[str]] = defaultdict(set)
    outlet_merchants: dict[str, set[str]] = defaultdict(set)
    order_observations: dict[str, set[str]] = defaultdict(set)
    observation_items: dict[str, set[str]] = defaultdict(set)
    order_messages: dict[str, set[str]] = defaultdict(set)
    for relationship in graph.relationships:
        if relationship.relationship_type is RelationshipType.ORDERED_FROM:
            order_outlets[relationship.source_node_id].add(relationship.target_node_id)
        elif relationship.relationship_type is RelationshipType.OUTLET_OF:
            outlet_merchants[relationship.source_node_id].add(relationship.target_node_id)
        elif relationship.relationship_type is RelationshipType.HAS_ITEM_OBSERVATION:
            order_observations[relationship.source_node_id].add(relationship.target_node_id)
        elif relationship.relationship_type is RelationshipType.LISTING_OF:
            observation_items[relationship.source_node_id].add(relationship.target_node_id)
        elif (
            relationship.relationship_type is RelationshipType.DOCUMENTED_BY
            and relationship.source_node_id.startswith("order:")
            and relationship.target_node_id.startswith("message:")
        ):
            order_messages[relationship.source_node_id].add(
                relationship.target_node_id.removeprefix("message:")
            )
    return (
        order_outlets,
        outlet_merchants,
        order_observations,
        observation_items,
        order_messages,
    )


def _merchant_goldens(
    graph: CanonicalGraph,
    *,
    limit: int,
) -> tuple[AnswerGolden, ...]:
    order_outlets, outlet_merchants, _, _, _ = _graph_maps(graph)
    names = {
        node.node_id: str(node.properties["normalized_name_private"])
        for node in graph.nodes
        if NodeLabel.MERCHANT in node.labels
        and isinstance(node.properties.get("normalized_name_private"), str)
    }
    orders_by_name: dict[str, set[str]] = defaultdict(set)
    for order_id, outlet_ids in order_outlets.items():
        for outlet_id in outlet_ids:
            for merchant_id in outlet_merchants.get(outlet_id, set()):
                if merchant_id in names:
                    orders_by_name[names[merchant_id]].add(order_id)
    selected = sorted(orders_by_name.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]
    return tuple(
        AnswerGolden(
            case_id=_case_id("merchant", name),
            family=AnswerFamily.MERCHANT_ORDER_COUNT,
            request=RuntimeRequest(
                question="How many times did I order from this merchant?",
                slots=QuerySlots(merchant_name=name, limit=200),
            ),
            expected_status=RuntimeStatus.VERIFIED,
            expected_fact_count=len(order_ids),
            expected_direct_answer=(
                f"The graph links this merchant to {len(order_ids)} source-backed "
                f"{'order' if len(order_ids) == 1 else 'orders'}."
            ),
            expected_calculation=None,
            minimum_citations=1,
            expected_abstention_reason=None,
        )
        for name, order_ids in selected
    )


def _delivery_goldens(
    graph: CanonicalGraph,
    *,
    limit: int,
) -> tuple[AnswerGolden, ...]:
    names = {
        node.node_id: str(node.properties["normalized_value_private"])
        for node in graph.nodes
        if NodeLabel.PERSON_MENTION in node.labels
        and isinstance(node.properties.get("normalized_value_private"), str)
    }
    orders_by_name: dict[str, set[str]] = defaultdict(set)
    for relationship in graph.relationships:
        if relationship.relationship_type is RelationshipType.HAS_DELIVERY_MENTION:
            name = names.get(relationship.target_node_id)
            if name:
                orders_by_name[name].add(relationship.source_node_id)
    candidates = tuple(item for item in orders_by_name.items() if 1 <= len(item[1]) < 200)
    selected = sorted(candidates, key=lambda item: (-len(item[1]), item[0]))[:limit]
    return tuple(
        AnswerGolden(
            case_id=_case_id("delivery", name),
            family=AnswerFamily.DELIVERY_MENTION_COUNT,
            request=RuntimeRequest(
                question="How many times did this delivery person deliver to me?",
                slots=QuerySlots(delivery_name=name, limit=200),
            ),
            expected_status=RuntimeStatus.VERIFIED,
            expected_fact_count=len(order_ids),
            expected_direct_answer=(
                f"The source evidence links this delivery-person mention to "
                f"{len(order_ids)} distinct "
                f"{'order' if len(order_ids) == 1 else 'orders'}."
            ),
            expected_calculation=None,
            minimum_citations=len(order_ids),
            expected_abstention_reason=None,
        )
        for name, order_ids in selected
    )


def _price_goldens(
    messages: tuple[SourceMessage, ...],
    graph: CanonicalGraph,
    *,
    limit: int,
) -> tuple[AnswerGolden, ...]:
    (
        order_outlets,
        outlet_merchants,
        order_observations,
        observation_items,
        order_messages,
    ) = _graph_maps(graph)
    message_times = {
        message.message_id: message.occurred_at
        for message in messages
        if message.occurred_at is not None
    }
    merchant_names = {
        node.node_id: str(node.properties["normalized_name_private"])
        for node in graph.nodes
        if NodeLabel.MERCHANT in node.labels
        and isinstance(node.properties.get("normalized_name_private"), str)
    }
    item_names = {
        node.node_id: str(node.properties["normalized_name_private"])
        for node in graph.nodes
        if NodeLabel.MERCHANT_ITEM in node.labels
        and isinstance(node.properties.get("normalized_name_private"), str)
    }
    observation_values = {
        node.node_id: (
            Decimal(str(node.properties["observed_amount"])),
            str(node.properties["currency"]),
        )
        for node in graph.nodes
        if NodeLabel.ITEM_OBSERVATION in node.labels
    }
    records: list[tuple[str, str, str, datetime, Decimal, str]] = []
    for order_id, observation_ids in order_observations.items():
        times = tuple(
            message_times[message_id]
            for message_id in order_messages.get(order_id, set())
            if message_id in message_times
        )
        if not times:
            continue
        occurred_at = min(times)
        assert occurred_at is not None
        merchant_ids = {
            merchant_id
            for outlet_id in order_outlets.get(order_id, set())
            for merchant_id in outlet_merchants.get(outlet_id, set())
        }
        for merchant_id in merchant_ids:
            merchant_name = merchant_names.get(merchant_id)
            if merchant_name is None:
                continue
            for observation_id in observation_ids:
                value = observation_values.get(observation_id)
                if value is None:
                    continue
                for item_id in observation_items.get(observation_id, set()):
                    item_name = item_names.get(item_id)
                    if item_name:
                        records.append(
                            (
                                merchant_name,
                                item_name,
                                order_id,
                                occurred_at,
                                value[0],
                                value[1],
                            )
                        )
    candidates = sorted({(record[0], record[1]) for record in records})
    valid: list[tuple[str, str, tuple[tuple[datetime, Decimal, str], ...]]] = []
    for merchant_name, query_item in candidates:
        by_order: dict[str, tuple[datetime, Decimal, str]] = {}
        conflict = False
        for record in records:
            if record[0] != merchant_name or query_item not in record[1]:
                continue
            candidate = (record[3], record[4], record[5])
            previous = by_order.get(record[2])
            if previous is not None and previous != candidate:
                conflict = True
                break
            by_order[record[2]] = candidate
        values = tuple(sorted(by_order.values(), key=lambda item: item[0]))
        if not conflict and 2 <= len(values) < 200 and len({value[2] for value in values}) == 1:
            valid.append((merchant_name, query_item, values))
    selected = sorted(valid, key=lambda item: (-len(item[2]), item[0], item[1]))[:limit]
    goldens: list[AnswerGolden] = []
    for merchant_name, item_name, observations in selected:
        earliest, latest = observations[0], observations[-1]
        currency = earliest[2]
        delta = latest[1] - earliest[1]
        if earliest[1] == 0:
            calculation = f"{currency} {latest[1]:.2f} - {currency} 0.00 = {currency} {delta:.2f}"
        else:
            percentage = delta / earliest[1] * Decimal("100")
            calculation = (
                f"{currency} {latest[1]:.2f} - {currency} {earliest[1]:.2f} = "
                f"{currency} {delta:.2f} ({percentage:.2f}%)"
            )
        goldens.append(
            AnswerGolden(
                case_id=_case_id("price", f"{merchant_name}|{item_name}"),
                family=AnswerFamily.PRICE_HISTORY,
                request=RuntimeRequest(
                    question="What did the same item cost at this restaurant over time?",
                    slots=QuerySlots(
                        merchant_name=merchant_name,
                        item_name=item_name,
                        limit=200,
                    ),
                ),
                expected_status=RuntimeStatus.VERIFIED,
                expected_fact_count=len(observations),
                expected_direct_answer=(
                    f"The source-backed item price changed from {currency} "
                    f"{earliest[1]:.2f} on {earliest[0].date().isoformat()} to "
                    f"{currency} {latest[1]:.2f} on {latest[0].date().isoformat()}."
                ),
                expected_calculation=calculation,
                minimum_citations=len(observations),
                expected_abstention_reason=None,
            )
        )
    return tuple(goldens)


def _abstention_goldens() -> tuple[AnswerGolden, ...]:
    missing = "lunarbit-canonical-oracle-no-match"
    return (
        AnswerGolden(
            case_id="case:abstain-financial",
            family=AnswerFamily.ABSTENTION,
            request=RuntimeRequest(
                question="How much missing charge did I pay?",
                slots=QuerySlots(
                    platform="swiggy",
                    component_type=missing,
                    limit=200,
                ),
            ),
            expected_status=RuntimeStatus.ABSTAINED,
            expected_fact_count=0,
            expected_direct_answer=None,
            expected_calculation=None,
            minimum_citations=0,
            expected_abstention_reason="incomplete_evidence_coverage",
        ),
        AnswerGolden(
            case_id="case:abstain-merchant",
            family=AnswerFamily.ABSTENTION,
            request=RuntimeRequest(
                question="How many times did I order from this merchant?",
                slots=QuerySlots(merchant_name=missing, limit=200),
            ),
            expected_status=RuntimeStatus.ABSTAINED,
            expected_fact_count=0,
            expected_direct_answer=None,
            expected_calculation=None,
            minimum_citations=0,
            expected_abstention_reason="incomplete_evidence_coverage",
        ),
        AnswerGolden(
            case_id="case:abstain-delivery",
            family=AnswerFamily.ABSTENTION,
            request=RuntimeRequest(
                question="How many times did this delivery person deliver to me?",
                slots=QuerySlots(delivery_name=missing, limit=200),
            ),
            expected_status=RuntimeStatus.ABSTAINED,
            expected_fact_count=0,
            expected_direct_answer=None,
            expected_calculation=None,
            minimum_citations=0,
            expected_abstention_reason="incomplete_evidence_coverage",
        ),
    )


def build_canonical_answer_goldens(
    messages: tuple[SourceMessage, ...],
    components: tuple[MoneyComponent, ...],
    graph: CanonicalGraph,
    *,
    cases_per_entity_family: int = 5,
) -> tuple[AnswerGolden, ...]:
    if not 1 <= cases_per_entity_family <= 20:
        raise ValueError("entity-family golden count must be between 1 and 20")
    goldens = (
        *_financial_goldens(components, graph),
        *_price_goldens(messages, graph, limit=cases_per_entity_family),
        *_merchant_goldens(graph, limit=cases_per_entity_family),
        *_delivery_goldens(graph, limit=cases_per_entity_family),
        *_abstention_goldens(),
    )
    case_ids = tuple(golden.case_id for golden in goldens)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("canonical answer golden IDs must be unique")
    return tuple(sorted(goldens, key=lambda value: value.case_id))
