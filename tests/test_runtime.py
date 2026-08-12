from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from lunarbit.agent import build_query_plan
from lunarbit.retrieval import GovernedQuery, QueryTemplate, VerificationStatus
from lunarbit.runtime import (
    GraphReader,
    QuerySlots,
    RuntimeRequest,
    RuntimeStatus,
    bind_query_plan,
    retrieve_grounded_context,
)


class StubReader(GraphReader):
    def __init__(self, rows: tuple[Mapping[str, Any], ...]) -> None:
        self.rows = rows
        self.queries: list[object] = []

    def run(self, query: GovernedQuery) -> tuple[Mapping[str, Any], ...]:
        self.queries.append(query)
        return self.rows


class PagingReader(GraphReader):
    def __init__(self, rows: tuple[Mapping[str, Any], ...]) -> None:
        self.rows = rows
        self.offsets: list[int] = []

    def run(self, query: GovernedQuery) -> tuple[Mapping[str, Any], ...]:
        parameters = query.parameters
        offset = int(parameters["offset"])
        limit = int(parameters["limit"])
        self.offsets.append(offset)
        return self.rows[offset : offset + limit]


def test_query_binding_requires_typed_slots_and_keeps_values_out_of_cypher() -> None:
    plan = build_query_plan("What did the same biryani cost three years ago?")
    slots = QuerySlots(merchant_name="sample kitchen", item_name="biryani", limit=30)

    queries = bind_query_plan(plan, slots)

    assert len(queries) == 1
    assert queries[0].template is QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY
    assert queries[0].parameters["merchant_name"] == "sample kitchen"
    assert "sample kitchen" not in queries[0].cypher
    with pytest.raises(ValueError, match="item_name"):
        bind_query_plan(plan, QuerySlots(merchant_name="sample kitchen"))


def test_financial_filters_apply_before_optional_evidence_expansion() -> None:
    plan = build_query_plan("How much platform fee did I pay?")
    query = bind_query_plan(
        plan,
        QuerySlots(platform="swiggy", component_type="platform_fee"),
    )[0]

    assert query.cypher.index("WHERE component.component_type") < query.cypher.index(
        "OPTIONAL MATCH"
    )


def test_financial_runtime_uses_decimal_deduplication_and_evidence_verification() -> None:
    source_hash = "a" * 64
    reader = StubReader(
        (
            {
                "component_id": "money:1",
                "amount": "10.10",
                "currency": "INR",
                "chunk_id": "chunk:1",
                "source_id": "document:1",
                "source_hash": source_hash,
            },
            {
                "component_id": "money:1",
                "amount": "10.10",
                "currency": "INR",
                "chunk_id": "chunk:2",
                "source_id": "document:1",
                "source_hash": source_hash,
            },
            {
                "component_id": "money:2",
                "amount": "0.20",
                "currency": "INR",
                "chunk_id": "chunk:3",
                "source_id": "document:2",
                "source_hash": "b" * 64,
            },
        )
    )
    request = RuntimeRequest(
        question="How much platform fee did I pay?",
        slots=QuerySlots(platform="swiggy", component_type="platform_fee", limit=50),
    )

    result = retrieve_grounded_context(request, reader)

    assert result.status is RuntimeStatus.VERIFIED
    assert result.verification.status is VerificationStatus.VERIFIED
    assert result.direct_answer == (
        "The evidence-backed platform fee total for Swiggy is INR 10.30 "
        "across 2 distinct components."
    )
    assert result.calculation == "INR 10.10 + INR 0.20 = INR 10.30"
    assert result.fact_count == 2
    assert len(result.citations) == 3


def test_runtime_abstains_when_rows_have_no_source_addressable_evidence() -> None:
    reader = StubReader(
        (
            {
                "component_id": "money:1",
                "amount": "10.10",
                "currency": "INR",
                "chunk_id": None,
                "source_id": None,
                "source_hash": None,
            },
        )
    )
    request = RuntimeRequest(
        question="How much platform fee did I pay?",
        slots=QuerySlots(platform="swiggy", component_type="platform_fee"),
    )

    result = retrieve_grounded_context(request, reader)

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.direct_answer is None
    assert result.verification.status is VerificationStatus.ABSTAINED
    assert result.abstention_reason == "incomplete_evidence_coverage"


def test_price_history_answer_uses_temporal_decimal_comparison() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:old",
                "amount": "320.00",
                "currency": "INR",
                "occurred_at": "2022-01-05T10:00:00+00:00",
                "chunk_id": "chunk:old",
                "source_id": "document:old",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:new",
                "amount": "420.00",
                "currency": "INR",
                "occurred_at": "2025-01-05T10:00:00+00:00",
                "chunk_id": "chunk:new",
                "source_id": "document:new",
                "source_hash": "b" * 64,
            },
        )
    )
    request = RuntimeRequest(
        question="What did the same biryani cost at this restaurant three years ago?",
        slots=QuerySlots(merchant_name="sample kitchen", item_name="biryani"),
    )

    result = retrieve_grounded_context(request, reader)

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "The source-backed item price changed from INR 320.00 on 2022-01-05 "
        "to INR 420.00 on 2025-01-05."
    )
    assert result.calculation == "INR 420.00 - INR 320.00 = INR 100.00 (31.25%)"
    assert result.fact_count == 2


def test_financial_runtime_pages_until_every_component_is_covered() -> None:
    reader = PagingReader(
        tuple(
            {
                "component_id": f"money:{index}",
                "amount": "1.00",
                "currency": "INR",
                "chunk_id": f"chunk:{index}",
                "source_id": f"document:{index}",
                "source_hash": f"{index:x}" * 64,
            }
            for index in range(1, 6)
        )
    )
    request = RuntimeRequest(
        question="How much platform fee did I pay?",
        slots=QuerySlots(platform="swiggy", component_type="platform_fee", limit=2),
    )

    result = retrieve_grounded_context(request, reader)

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 5
    assert "INR 5.00" in (result.direct_answer or "")
    assert reader.offsets == [0, 2, 4]


def test_financial_runtime_abstains_if_page_budget_cannot_prove_completion() -> None:
    reader = PagingReader(
        tuple(
            {
                "component_id": f"money:{index}",
                "amount": "1.00",
                "currency": "INR",
                "chunk_id": f"chunk:{index}",
                "source_id": f"document:{index}",
                "source_hash": (f"{index:x}" * 64)[:64],
            }
            for index in range(1, 14)
        )
    )
    request = RuntimeRequest(
        question="How much platform fee did I pay?",
        slots=QuerySlots(platform="swiggy", component_type="platform_fee", limit=1),
    )

    result = retrieve_grounded_context(request, reader)

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.direct_answer is None
    assert result.abstention_reason == "query_action_budget_exhausted"
    assert reader.offsets == list(range(12))


def test_delivery_answer_counts_orders_without_overclaiming_person_identity() -> None:
    reader = StubReader(
        tuple(
            {
                "order_id": order_id,
                "mention_id": f"mention:{index}",
                "chunk_id": f"chunk:{index}",
                "source_id": f"message:{index}",
                "source_hash": f"{index:x}" * 64,
            }
            for index, order_id in enumerate(("order:1", "order:1", "order:2"), start=1)
        )
    )

    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How many times did this delivery person deliver to me?",
            slots=QuerySlots(delivery_name="sample person"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 2
    assert result.direct_answer == (
        "The source evidence links this delivery-person mention to 2 distinct orders."
    )
    assert "mention-level" in result.limitations[0]


def test_merchant_order_answer_uses_the_consistent_graph_aggregate() -> None:
    reader = StubReader(
        (
            {
                "order_count": 3,
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_count": 3,
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
        )
    )

    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How many times did I order from Sample Kitchen?",
            slots=QuerySlots(merchant_name="sample kitchen"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 3
    assert result.direct_answer == "The graph links this merchant to 3 source-backed orders."
