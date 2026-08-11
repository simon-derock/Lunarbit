from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from lunarbit.agent import build_query_plan
from lunarbit.retrieval import QueryTemplate, VerificationStatus
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

    def run(self, query: object) -> tuple[Mapping[str, Any], ...]:
        self.queries.append(query)
        return self.rows


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
    assert result.verification.status is VerificationStatus.ABSTAINED
    assert result.abstention_reason == "incomplete_evidence_coverage"
