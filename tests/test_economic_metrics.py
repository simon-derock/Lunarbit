from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic_metrics import (
    BasketObservation,
    PeriodEconomics,
    compute_fee_discount_membership_economics,
    decompose_spending_change,
    personal_food_price_index,
)


def _time(month: int) -> datetime:
    return datetime(2026, month, 1, tzinfo=UTC)


def _basket(
    suffix: int,
    group: str | None,
    price: str,
    quantity: str,
    *,
    reviewed: bool = True,
) -> BasketObservation:
    return BasketObservation(
        observation_id=f"observation:{suffix}",
        comparable_group_id=group,
        unit_price=Decimal(price),
        quantity=Decimal(quantity),
        reviewed_comparable=reviewed,
        event_ids=(UUID(f"10000000-0000-0000-0000-{suffix:012d}"),),
        evidence_chunk_ids=(UUID(f"20000000-0000-0000-0000-{suffix:012d}"),),
    )


def _period(
    *,
    start_month: int,
    basket: tuple[BasketObservation, ...],
    fees: str,
    taxes: str,
    discounts: str,
    membership_benefits: str,
    membership_cost: str,
    observed_total: str,
    order_count: int,
) -> PeriodEconomics:
    event_ids = tuple(sorted({event_id for item in basket for event_id in item.event_ids}, key=str))
    evidence_chunk_ids = tuple(
        sorted({chunk_id for item in basket for chunk_id in item.evidence_chunk_ids}, key=str)
    )
    return PeriodEconomics(
        period_start=_time(start_month),
        period_end=_time(start_month + 1),
        currency="INR",
        basket=basket,
        fees=Decimal(fees),
        taxes=Decimal(taxes),
        discounts=Decimal(discounts),
        membership_benefits=Decimal(membership_benefits),
        membership_cost=Decimal(membership_cost),
        observed_customer_total=Decimal(observed_total),
        order_count=order_count,
        event_ids=event_ids,
        evidence_chunk_ids=evidence_chunk_ids,
    )


def test_personal_food_price_index_uses_reviewed_matched_basket_and_reports_coverage() -> None:
    base = _period(
        start_month=1,
        basket=(_basket(1, "meal:a", "100", "2"), _basket(2, "meal:b", "50", "1")),
        fees="10",
        taxes="5",
        discounts="20",
        membership_benefits="0",
        membership_cost="0",
        observed_total="245",
        order_count=2,
    )
    current = _period(
        start_month=2,
        basket=(_basket(3, "meal:a", "120", "3"), _basket(4, "meal:c", "80", "1")),
        fees="15",
        taxes="6",
        discounts="30",
        membership_benefits="10",
        membership_cost="100",
        observed_total="421",
        order_count=2,
    )

    index = personal_food_price_index(base, current)

    assert index.value == Decimal("120")
    assert index.matched_group_ids == ("meal:a",)
    assert index.coverage_ratio == Decimal("0.8")
    assert index.base_basket_cost == Decimal("200")
    assert index.repriced_basket_cost == Decimal("240")


def test_spending_change_decomposition_closes_price_quantity_mix_and_platform_effects() -> None:
    base = _period(
        start_month=1,
        basket=(_basket(1, "meal:a", "100", "2"), _basket(2, "meal:b", "50", "1")),
        fees="10",
        taxes="5",
        discounts="20",
        membership_benefits="0",
        membership_cost="0",
        observed_total="245",
        order_count=2,
    )
    current = _period(
        start_month=2,
        basket=(_basket(3, "meal:a", "120", "3"), _basket(4, "meal:c", "80", "1")),
        fees="15",
        taxes="6",
        discounts="30",
        membership_benefits="10",
        membership_cost="100",
        observed_total="421",
        order_count=2,
    )

    result = decompose_spending_change(base, current)

    assert result.observed_change == Decimal("176")
    assert result.price_effect == Decimal("40")
    assert result.quantity_effect == Decimal("100")
    assert result.interaction_effect == Decimal("20")
    assert result.item_mix_effect == Decimal("30")
    assert result.fee_effect == Decimal("5")
    assert result.tax_effect == Decimal("1")
    assert result.discount_effect == Decimal("-10")
    assert result.membership_effect == Decimal("-10")
    assert result.unexplained_residual == Decimal("0")


def test_fee_discount_and_membership_economics_use_realized_values() -> None:
    period = _period(
        start_month=2,
        basket=(_basket(3, "meal:a", "120", "3"), _basket(4, "meal:c", "80", "1")),
        fees="15",
        taxes="6",
        discounts="30",
        membership_benefits="10",
        membership_cost="100",
        observed_total="421",
        order_count=2,
    )

    result = compute_fee_discount_membership_economics(period)

    assert result.fee_burden == Decimal("15") / Decimal("421")
    assert result.discount_capture == Decimal("40") / Decimal("440")
    assert result.membership_net_value == Decimal("-90")
    assert result.membership_roi == Decimal("-0.9")
    assert result.break_even_orders == 20


def test_economic_metrics_reject_currency_mismatch_and_unreviewed_only_baskets() -> None:
    base = _period(
        start_month=1,
        basket=(_basket(1, "meal:a", "100", "1", reviewed=False),),
        fees="0",
        taxes="0",
        discounts="0",
        membership_benefits="0",
        membership_cost="0",
        observed_total="100",
        order_count=1,
    )
    current = _period(
        start_month=2,
        basket=(_basket(2, "meal:a", "120", "1", reviewed=False),),
        fees="0",
        taxes="0",
        discounts="0",
        membership_benefits="0",
        membership_cost="0",
        observed_total="120",
        order_count=1,
    )

    with pytest.raises(ValueError, match="reviewed"):
        personal_food_price_index(base, current)
    with pytest.raises(ValueError, match="currency"):
        decompose_spending_change(base, current.model_copy(update={"currency": "USD"}))
