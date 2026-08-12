from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from pydantic import Field, model_validator

from lunarbit.models import ContractModel

ECONOMIC_METRIC_VERSION = "personal-commerce-economics-v1.0.0"


class BasketObservation(ContractModel):
    observation_id: str = Field(min_length=1)
    comparable_group_id: str | None = Field(default=None, min_length=1)
    unit_price: Decimal = Field(ge=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"))
    reviewed_comparable: bool
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reviewed_observation_has_group(self) -> BasketObservation:
        if self.reviewed_comparable and self.comparable_group_id is None:
            raise ValueError("reviewed comparable observations require a comparable group")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("basket event IDs must be unique")
        if len(set(self.evidence_chunk_ids)) != len(self.evidence_chunk_ids):
            raise ValueError("basket evidence IDs must be unique")
        return self

    @property
    def spend(self) -> Decimal:
        return self.unit_price * self.quantity


class PeriodEconomics(ContractModel):
    period_start: datetime
    period_end: datetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    basket: tuple[BasketObservation, ...] = Field(min_length=1)
    fees: Decimal = Field(ge=Decimal("0"))
    taxes: Decimal = Field(ge=Decimal("0"))
    discounts: Decimal = Field(ge=Decimal("0"))
    membership_benefits: Decimal = Field(ge=Decimal("0"))
    membership_cost: Decimal = Field(ge=Decimal("0"))
    observed_customer_total: Decimal
    order_count: int = Field(ge=1)
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_METRIC_VERSION

    @model_validator(mode="after")
    def period_and_provenance_are_valid(self) -> PeriodEconomics:
        for value, name in (
            (self.period_start, "period_start"),
            (self.period_end, "period_end"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be later than period_start")
        if len({item.observation_id for item in self.basket}) != len(self.basket):
            raise ValueError("basket observation IDs must be unique")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("period event IDs must be unique")
        if len(set(self.evidence_chunk_ids)) != len(self.evidence_chunk_ids):
            raise ValueError("period evidence IDs must be unique")
        return self


class PersonalFoodPriceIndex(ContractModel):
    value: Decimal = Field(ge=Decimal("0"))
    base_basket_cost: Decimal = Field(gt=Decimal("0"))
    repriced_basket_cost: Decimal = Field(ge=Decimal("0"))
    coverage_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    matched_group_ids: tuple[str, ...] = Field(min_length=1)
    excluded_observations: int = Field(ge=0)
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_METRIC_VERSION


class SpendingChangeDecomposition(ContractModel):
    observed_change: Decimal
    price_effect: Decimal
    quantity_effect: Decimal
    interaction_effect: Decimal
    item_mix_effect: Decimal
    fee_effect: Decimal
    tax_effect: Decimal
    discount_effect: Decimal
    membership_effect: Decimal
    unexplained_residual: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_METRIC_VERSION

    @model_validator(mode="after")
    def effects_close_to_observed_change(self) -> SpendingChangeDecomposition:
        explained = sum(
            (
                self.price_effect,
                self.quantity_effect,
                self.interaction_effect,
                self.item_mix_effect,
                self.fee_effect,
                self.tax_effect,
                self.discount_effect,
                self.membership_effect,
                self.unexplained_residual,
            ),
            start=Decimal("0"),
        )
        if explained != self.observed_change:
            raise ValueError("spending decomposition must close exactly")
        return self


class PlatformEconomics(ContractModel):
    fee_burden: Decimal | None = Field(default=None, ge=Decimal("0"))
    discount_capture: Decimal | None = Field(default=None, ge=Decimal("0"))
    membership_net_value: Decimal
    membership_roi: Decimal | None
    break_even_orders: int | None = Field(default=None, ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_METRIC_VERSION


class _BasketAggregate:
    def __init__(self) -> None:
        self.quantity = Decimal("0")
        self.spend = Decimal("0")

    @property
    def unit_price(self) -> Decimal:
        return self.spend / self.quantity


def _grouped_basket(
    period: PeriodEconomics,
    *,
    comparable_only: bool,
) -> dict[str, _BasketAggregate]:
    groups: dict[str, _BasketAggregate] = defaultdict(_BasketAggregate)
    for observation in period.basket:
        if comparable_only:
            if not observation.reviewed_comparable or observation.comparable_group_id is None:
                continue
            key = observation.comparable_group_id
        elif observation.reviewed_comparable and observation.comparable_group_id is not None:
            key = observation.comparable_group_id
        else:
            key = f"unmatched:{observation.observation_id}"
        groups[key].quantity += observation.quantity
        groups[key].spend += observation.spend
    return dict(groups)


def _provenance(*periods: PeriodEconomics) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    events = tuple(
        sorted({event_id for period in periods for event_id in period.event_ids}, key=str)
    )
    evidence = tuple(
        sorted(
            {chunk_id for period in periods for chunk_id in period.evidence_chunk_ids},
            key=str,
        )
    )
    return events, evidence


def _same_currency(base: PeriodEconomics, current: PeriodEconomics) -> None:
    if base.currency != current.currency:
        raise ValueError("economic metrics cannot mix currency")


def personal_food_price_index(
    base: PeriodEconomics,
    current: PeriodEconomics,
) -> PersonalFoodPriceIndex:
    _same_currency(base, current)
    base_groups = _grouped_basket(base, comparable_only=True)
    current_groups = _grouped_basket(current, comparable_only=True)
    if not base_groups or not current_groups:
        raise ValueError("price index requires reviewed comparable observations")
    matched = tuple(sorted(set(base_groups) & set(current_groups)))
    if not matched:
        raise ValueError("price index requires a reviewed matched basket")
    eligible_base_cost = sum((value.spend for value in base_groups.values()), start=Decimal("0"))
    base_basket_cost = sum((base_groups[group].spend for group in matched), start=Decimal("0"))
    if eligible_base_cost <= 0 or base_basket_cost <= 0:
        raise ValueError("price index base basket must have positive spend")
    repriced = sum(
        (base_groups[group].quantity * current_groups[group].unit_price for group in matched),
        start=Decimal("0"),
    )
    events, evidence = _provenance(base, current)
    return PersonalFoodPriceIndex(
        value=repriced / base_basket_cost * Decimal("100"),
        base_basket_cost=base_basket_cost,
        repriced_basket_cost=repriced,
        coverage_ratio=base_basket_cost / eligible_base_cost,
        matched_group_ids=matched,
        excluded_observations=sum(
            not item.reviewed_comparable or item.comparable_group_id is None
            for item in (*base.basket, *current.basket)
        ),
        event_ids=events,
        evidence_chunk_ids=evidence,
    )


def decompose_spending_change(
    base: PeriodEconomics,
    current: PeriodEconomics,
) -> SpendingChangeDecomposition:
    _same_currency(base, current)
    base_groups = _grouped_basket(base, comparable_only=False)
    current_groups = _grouped_basket(current, comparable_only=False)
    common = set(base_groups) & set(current_groups)
    price_effect = sum(
        (
            (current_groups[group].unit_price - base_groups[group].unit_price)
            * base_groups[group].quantity
            for group in common
        ),
        start=Decimal("0"),
    )
    quantity_effect = sum(
        (
            (current_groups[group].quantity - base_groups[group].quantity)
            * base_groups[group].unit_price
            for group in common
        ),
        start=Decimal("0"),
    )
    interaction_effect = sum(
        (
            (current_groups[group].unit_price - base_groups[group].unit_price)
            * (current_groups[group].quantity - base_groups[group].quantity)
            for group in common
        ),
        start=Decimal("0"),
    )
    item_mix_effect = sum(
        (current_groups[group].spend for group in set(current_groups) - common),
        start=Decimal("0"),
    ) - sum(
        (base_groups[group].spend for group in set(base_groups) - common),
        start=Decimal("0"),
    )
    fee_effect = current.fees - base.fees
    tax_effect = current.taxes - base.taxes
    discount_effect = -(current.discounts - base.discounts)
    membership_effect = -(current.membership_benefits - base.membership_benefits)
    observed_change = current.observed_customer_total - base.observed_customer_total
    subtotal = sum(
        (
            price_effect,
            quantity_effect,
            interaction_effect,
            item_mix_effect,
            fee_effect,
            tax_effect,
            discount_effect,
            membership_effect,
        ),
        start=Decimal("0"),
    )
    events, evidence = _provenance(base, current)
    return SpendingChangeDecomposition(
        observed_change=observed_change,
        price_effect=price_effect,
        quantity_effect=quantity_effect,
        interaction_effect=interaction_effect,
        item_mix_effect=item_mix_effect,
        fee_effect=fee_effect,
        tax_effect=tax_effect,
        discount_effect=discount_effect,
        membership_effect=membership_effect,
        unexplained_residual=observed_change - subtotal,
        currency=base.currency,
        event_ids=events,
        evidence_chunk_ids=evidence,
    )


def compute_fee_discount_membership_economics(
    period: PeriodEconomics,
) -> PlatformEconomics:
    gross_item_spend = sum((item.spend for item in period.basket), start=Decimal("0"))
    fee_burden = (
        period.fees / period.observed_customer_total if period.observed_customer_total > 0 else None
    )
    realized_savings = period.discounts + period.membership_benefits
    discount_capture = realized_savings / gross_item_spend if gross_item_spend > 0 else None
    net_value = period.membership_benefits - period.membership_cost
    membership_roi = net_value / period.membership_cost if period.membership_cost > 0 else None
    average_benefit = period.membership_benefits / Decimal(period.order_count)
    break_even = (
        int((period.membership_cost / average_benefit).to_integral_value(rounding=ROUND_CEILING))
        if period.membership_cost > 0 and average_benefit > 0
        else 0
        if period.membership_cost == 0
        else None
    )
    return PlatformEconomics(
        fee_burden=fee_burden,
        discount_capture=discount_capture,
        membership_net_value=net_value,
        membership_roi=membership_roi,
        break_even_orders=break_even,
        currency=period.currency,
        event_ids=period.event_ids,
        evidence_chunk_ids=period.evidence_chunk_ids,
    )
