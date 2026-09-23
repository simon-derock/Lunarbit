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

    assert "MerchantIdentity" in queries[0].cypher
    assert "CONTAINS $merchant_name" in queries[0].cypher


def test_query_binding_supports_global_restaurant_ranking_without_name_slot() -> None:
    plan = build_query_plan("Which restaurants' orders are most?")
    queries = bind_query_plan(plan, QuerySlots(limit=20))
    assert queries[0].template is QueryTemplate.MERCHANT_ORDER_RANKING
    assert queries[0].parameters == {"limit": 20}


def test_unsupported_plan_abstains_without_touching_graph() -> None:
    class ExplodingReader:
        def run(self, query):
            raise AssertionError("unsupported questions must not access the graph")

    request = RuntimeRequest(
        question="What is my favorite color?",
        slots=QuerySlots(),
    )
    result = retrieve_grounded_context(request, ExplodingReader())

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.abstention_reason == "unsupported"
    assert result.verification.citation_ids == ()


def test_unbound_order_count_requests_scope_without_graph_access() -> None:
    request = RuntimeRequest(question="How many orders did I make?", slots=QuerySlots())
    result = retrieve_grounded_context(request, StubReader(()))

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.abstention_reason == "clarification_required"
    assert result.review_required is True
    assert result.review_reason == "clarification_required"


def test_fee_discount_analysis_abstains_without_graph_facts() -> None:
    request = RuntimeRequest(
        question="Did discounts offset delivery fees at KMS Hakkim?",
        slots=QuerySlots(merchant_name="kms hakkim"),
    )
    result = retrieve_grounded_context(request, StubReader(()))

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.abstention_reason == "incomplete_evidence_coverage"
    assert result.review_required is False


def test_merchant_order_count_accepts_reviewed_name_prefixes() -> None:
    reader = StubReader(
        (
            {
                "order_count": 14,
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
                "merchant_name": "KMS Hakkim Kalyana Biriyani",
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How many orders from KMS Hakkim?",
            slots=QuerySlots(merchant_name="kms hakkim"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == "The graph links this merchant to 14 source-backed orders."


def test_yearly_spend_aggregates_distinct_orders_with_decimal_totals() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "year": 2024,
                "component_type": "customer_total",
                "amount": "120.10",
                "currency": "INR",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:2",
                "year": 2024,
                "component_type": "customer_total",
                "amount": "80.20",
                "currency": "INR",
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
            {
                "order_id": "order:3",
                "year": 2025,
                "component_type": "customer_total",
                "amount": "50.00",
                "currency": "INR",
                "chunk_id": "chunk:3",
                "source_id": "message:3",
                "source_hash": "c" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="What was my total food spending for each year?",
            slots=QuerySlots(),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 3
    assert result.direct_answer == (
        "Yearly source-backed spending: 2024: INR 200.30 across 2 orders; "
        "2025: INR 50.00 across 1 order."
    )
    assert (
        result.calculation
        == "2024: INR 120.10 + INR 80.20 = INR 200.30; 2025: INR 50.00 = INR 50.00"
    )


def test_yearly_spend_abstains_when_currencies_conflict() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "year": 2024,
                "component_type": "customer_total",
                "amount": "120.00",
                "currency": "INR",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:2",
                "year": 2025,
                "component_type": "customer_total",
                "amount": "10.00",
                "currency": "USD",
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="What was my total food spending for each year?",
            slots=QuerySlots(),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.review_required is True
    assert result.review_reason == "financial_conflict"


def test_spending_change_point_reports_temporal_regime_shift() -> None:
    rows = tuple(
        {
            "order_id": f"order:{index}",
            "component_type": "customer_total",
            "amount": str("100.00" if index < 3 else "250.00"),
            "currency": "INR",
            "occurred_at": f"2024-0{index + 1}-15T12:00:00+00:00",
            "chunk_id": f"chunk:{index}",
            "source_id": f"message:{index}",
            "source_hash": chr(97 + index) * 64,
        }
        for index in range(6)
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="When did my spending change point occur?",
            slots=QuerySlots(),
        ),
        StubReader(rows),
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert "spending regime shift" in (result.direct_answer or "")
    assert "2024-04-15" in (result.direct_answer or "")
    assert "change point" in (result.calculation or "").lower()


def test_fee_discount_analysis_calculates_offset_and_net_burden() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "component_type": "delivery_charge",
                "amount": "40.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:1",
                "component_type": "coupon_discount",
                "amount": "15.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim",
                "chunk_id": "chunk:2",
                "source_id": "message:1",
                "source_hash": "b" * 64,
            },
            {
                "order_id": "order:2",
                "component_type": "platform_fee",
                "amount": "20.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim",
                "chunk_id": "chunk:3",
                "source_id": "message:2",
                "source_hash": "c" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="Did discounts offset delivery fees at KMS Hakkim?",
            slots=QuerySlots(merchant_name="kms hakkim"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 3
    assert result.direct_answer == (
        "At KMS Hakkim, INR 60.00 of fees were offset by INR 15.00 in discounts "
        "(25.00% offset), leaving a net fee burden of INR 45.00."
    )
    assert result.calculation == "INR 60.00 - INR 15.00 = INR 45.00"


def test_spending_change_decomposes_volume_and_average_order_effects() -> None:
    reader = StubReader(
        tuple(
            {
                "order_id": f"order:{year}-{index}",
                "year": year,
                "component_type": "customer_total",
                "amount": str(amount),
                "currency": "INR",
                "chunk_id": f"chunk:{year}-{index}",
                "source_id": f"message:{year}-{index}",
                "source_hash": (chr(96 + year - 2022) * 64),
            }
            for year, amounts in ((2024, (100, 100)), (2025, (150, 150, 150)))
            for index, amount in enumerate(amounts, start=1)
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="What caused my spending to change between years?",
            slots=QuerySlots(),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "Between 2024 and 2025, spending increased by INR 250.00: "
        "INR 100.00 from order volume and INR 150.00 from average order cost."
    )
    assert (
        result.calculation
        == "INR 250.00 = INR 100.00 volume effect + INR 150.00 average-order effect"
    )


def test_delivery_fee_counterfactual_reports_observed_savings_without_mutating_history() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "component_type": "delivery_charge",
                "amount": "40.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:2",
                "component_type": "delivery_charge",
                "amount": "25.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim",
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How much would I have saved if delivery fees were waived at KMS Hakkim?",
            slots=QuerySlots(merchant_name="kms hakkim"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "Waiving observed delivery fees at KMS Hakkim would have saved INR 65.00 across 2 orders."
    )
    assert result.calculation == "INR 40.00 + INR 25.00 = INR 65.00 simulated saving"


def test_item_price_change_ranking_reports_largest_source_backed_increases() -> None:
    reader = StubReader(
        (
            {
                "item_name": "biryani",
                "amount": "200.00",
                "currency": "INR",
                "occurred_at": "2024-01-10T12:00:00+00:00",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "item_name": "biryani",
                "amount": "260.00",
                "currency": "INR",
                "occurred_at": "2025-01-10T12:00:00+00:00",
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
            {
                "item_name": "parotta",
                "amount": "100.00",
                "currency": "INR",
                "occurred_at": "2024-01-10T12:00:00+00:00",
                "chunk_id": "chunk:3",
                "source_id": "message:3",
                "source_hash": "c" * 64,
            },
            {
                "item_name": "parotta",
                "amount": "110.00",
                "currency": "INR",
                "occurred_at": "2025-01-10T12:00:00+00:00",
                "chunk_id": "chunk:4",
                "source_id": "message:4",
                "source_hash": "d" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="Which dishes increased in price the most?",
            slots=QuerySlots(),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "Largest source-backed item price increases: biryani: INR 200.00 to INR 260.00 "
        "(+INR 60.00, +30.00%); parotta: INR 100.00 to INR 110.00 (+INR 10.00, +10.00%)."
    )


def test_personal_food_price_index_uses_equal_weighted_matched_items() -> None:
    reader = StubReader(
        (
            {
                "item_name": "biryani",
                "amount": "200.00",
                "currency": "INR",
                "occurred_at": "2024-01-10T12:00:00+00:00",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "item_name": "biryani",
                "amount": "260.00",
                "currency": "INR",
                "occurred_at": "2025-01-10T12:00:00+00:00",
                "chunk_id": "chunk:2",
                "source_id": "message:2",
                "source_hash": "b" * 64,
            },
            {
                "item_name": "parotta",
                "amount": "100.00",
                "currency": "INR",
                "occurred_at": "2024-01-10T12:00:00+00:00",
                "chunk_id": "chunk:3",
                "source_id": "message:3",
                "source_hash": "c" * 64,
            },
            {
                "item_name": "parotta",
                "amount": "110.00",
                "currency": "INR",
                "occurred_at": "2025-01-10T12:00:00+00:00",
                "chunk_id": "chunk:4",
                "source_id": "message:4",
                "source_hash": "d" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How much has my food basket inflation been?",
            slots=QuerySlots(),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "The matched personal food-basket price index is 120.00 "
        "(increased 20.00% from the observed baseline)."
    )


def test_spending_anomaly_detection_uses_robust_modified_z_score() -> None:
    rows = tuple(
        {
            "order_id": f"order:{index}",
            "component_type": "customer_total",
            "amount": str(amount),
            "currency": "INR",
            "occurred_at": f"2025-01-{index + 1:02d}T12:00:00+00:00",
            "chunk_id": f"chunk:{index}",
            "source_id": f"message:{index}",
            "source_hash": f"{index:x}" * 64,
        }
        for index, amount in enumerate((100, 105, 110, 115, 500))
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="Which spending orders are unusual outliers?",
            slots=QuerySlots(),
        ),
        StubReader(rows),
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer is not None
    assert "Detected 1 source-backed spending anomaly" in result.direct_answer
    assert "order:4: INR 500.00" in result.direct_answer


def test_spending_concentration_reports_hhi_and_top_merchant_share() -> None:
    rows = tuple(
        {
            "merchant_name": merchant,
            "order_id": f"order:{index}",
            "component_type": "customer_total",
            "amount": str(amount),
            "currency": "INR",
            "chunk_id": f"chunk:{index}",
            "source_id": f"message:{index}",
            "source_hash": f"{index:x}" * 64,
        }
        for index, (merchant, amount) in enumerate(
            (("KMS Hakkim", "100.00"), ("KMS Hakkim", "100.00"), ("Other Kitchen", "200.00"))
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How concentrated is my restaurant spending?",
            slots=QuerySlots(),
        ),
        StubReader(rows),
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.direct_answer == (
        "Food spending concentration is 5000.00 HHI; Other Kitchen represents "
        "50.00% of source-backed spend. Merchant shares: KMS Hakkim: 50.00%; "
        "Other Kitchen: 50.00%."
    )


def test_merchant_order_count_abstains_on_ambiguous_identity_prefix() -> None:
    reader = StubReader(
        (
            {"order_count": 10, "merchant_name": "Hotel Alpha"},
            {"order_count": 8, "merchant_name": "Hotel Beta"},
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How many orders from Hotel?",
            slots=QuerySlots(merchant_name="hotel"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.ABSTAINED
    assert result.direct_answer is None
    assert result.review_required is True
    assert result.review_reason == "identity_ambiguity"


def test_merchant_spend_uses_customer_totals_once_per_order() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "component_type": "invoice_total",
                "amount": "120.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim Kalyana Biriyani",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
            {
                "order_id": "order:1",
                "component_type": "customer_total",
                "amount": "100.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim Kalyana Biriyani",
                "chunk_id": "chunk:2",
                "source_id": "message:1",
                "source_hash": "b" * 64,
            },
            {
                "order_id": "order:2",
                "component_type": "customer_total",
                "amount": "80.00",
                "currency": "INR",
                "merchant_name": "KMS Hakkim Kalyana Biriyani",
                "chunk_id": "chunk:3",
                "source_id": "message:2",
                "source_hash": "c" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How much did I spend at KMS Hakkim?",
            slots=QuerySlots(merchant_name="kms hakkim"),
        ),
        reader,
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.fact_count == 2
    assert (
        result.direct_answer
        == "Source-backed spend at this merchant is INR 180.00 across 2 orders."
    )


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


def test_delivery_answer_reports_reviewed_pseudonymous_identity() -> None:
    reader = StubReader(
        (
            {
                "order_id": "order:1",
                "person_public_id": "556326",
                "chunk_id": "chunk:1",
                "source_id": "message:1",
                "source_hash": "a" * 64,
            },
        )
    )
    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How many orders did delivery participant 556326 deliver?",
            slots=QuerySlots(delivery_name="556326"),
        ),
        reader,
    )

    assert result.fact_count == 1
    assert "556326" in result.limitations[0]


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


def test_large_financial_calculations_are_bounded_and_content_addressed() -> None:
    rows = tuple(
        {
            "component_id": f"money:{index:02d}",
            "amount": "1.00",
            "currency": "INR",
            "chunk_id": f"chunk:{index:02d}",
            "source_id": f"document:{index:02d}",
            "source_hash": f"{index % 16:x}" * 64,
        }
        for index in range(30)
    )

    result = retrieve_grounded_context(
        RuntimeRequest(
            question="How much platform fee did I pay?",
            slots=QuerySlots(platform="swiggy", component_type="platform_fee"),
        ),
        StubReader(rows),
    )

    assert result.status is RuntimeStatus.VERIFIED
    assert result.calculation is not None
    assert len(result.calculation) < 300
    assert result.calculation.startswith(
        "Decimal sum of 30 distinct source-backed components = INR 30.00; "
    )
    assert "ordered-term SHA-256=" in result.calculation
