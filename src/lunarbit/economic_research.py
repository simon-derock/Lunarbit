from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from statistics import median
from uuid import UUID

from pydantic import Field, model_validator

from lunarbit.economic import CounterfactualScenario
from lunarbit.finance import EpistemicMode, FinancialComponentType
from lunarbit.models import ContractModel

ECONOMIC_RESEARCH_VERSION = "economic-research-signals-v1.0.0"
NONCAUSAL_LABEL = "descriptive_noncausal_signal"
_DISCOUNT_TYPES = {
    FinancialComponentType.ITEM_DISCOUNT,
    FinancialComponentType.COUPON_DISCOUNT,
    FinancialComponentType.MEMBERSHIP_BENEFIT,
}


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _unique_provenance(
    values: tuple[ElasticityObservation | SubstitutionObservation | EconomicPoint, ...],
) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    events = tuple(sorted({event_id for value in values for event_id in value.event_ids}, key=str))
    evidence = tuple(
        sorted(
            {chunk_id for value in values for chunk_id in value.evidence_chunk_ids},
            key=str,
        )
    )
    return events, evidence


class ElasticityObservation(ContractModel):
    occurred_at: datetime
    unit_price: Decimal = Field(gt=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"))
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def time_is_valid(self) -> ElasticityObservation:
        _aware(self.occurred_at, "occurred_at")
        return self


class ElasticitySignal(ContractModel):
    elasticity: Decimal
    valid_transitions: int = Field(ge=3)
    label: str = NONCAUSAL_LABEL
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_RESEARCH_VERSION


class SubstitutionObservation(ContractModel):
    occurred_at: datetime
    focal_price: Decimal = Field(gt=Decimal("0"))
    focal_quantity: Decimal = Field(ge=Decimal("0"))
    alternative_quantity: Decimal = Field(ge=Decimal("0"))
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def time_is_valid(self) -> SubstitutionObservation:
        _aware(self.occurred_at, "occurred_at")
        return self


class SubstitutionSignal(ContractModel):
    directional_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    qualifying_transitions: int = Field(ge=1)
    label: str = NONCAUSAL_LABEL
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_RESEARCH_VERSION


class EconomicPoint(ContractModel):
    occurred_at: datetime
    value: Decimal
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def time_is_valid(self) -> EconomicPoint:
        _aware(self.occurred_at, "occurred_at")
        return self


class RobustAnomalyResult(ContractModel):
    method: str = "median_mad"
    median_value: Decimal
    median_absolute_deviation: Decimal = Field(ge=Decimal("0"))
    anomaly_indexes: tuple[int, ...]
    change_point_indexes: tuple[int, ...]
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_RESEARCH_VERSION


class CounterfactualComponent(ContractModel):
    component_type: FinancialComponentType
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class SimulatedComponent(ContractModel):
    component_type: FinancialComponentType
    observed_amount: Decimal
    simulated_amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class CounterfactualResult(ContractModel):
    scenario_id: str
    observed_total: Decimal
    simulated_total: Decimal
    difference: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    components: tuple[SimulatedComponent, ...] = Field(min_length=1)
    base_event_ids: tuple[UUID, ...] = Field(min_length=1)
    epistemic_mode: EpistemicMode
    formula: str = Field(min_length=1)
    algorithm_version: str = ECONOMIC_RESEARCH_VERSION

    @model_validator(mode="after")
    def simulation_is_separate_and_exact(self) -> CounterfactualResult:
        if self.epistemic_mode is not EpistemicMode.SIMULATED:
            raise ValueError("counterfactual results must remain simulated")
        if self.simulated_total - self.observed_total != self.difference:
            raise ValueError("counterfactual difference must be exact Decimal subtraction")
        return self


def _ordered[T: ElasticityObservation | SubstitutionObservation | EconomicPoint](
    values: tuple[T, ...],
) -> tuple[T, ...]:
    ordered = tuple(sorted(values, key=lambda item: item.occurred_at))
    times = tuple(item.occurred_at for item in ordered)
    if len(set(times)) != len(times):
        raise ValueError("economic observations require unique timestamps")
    return ordered


def estimate_price_elasticity_signal(
    observations: tuple[ElasticityObservation, ...],
) -> ElasticitySignal:
    if len(observations) < 4:
        raise ValueError("elasticity signal requires at least four observations")
    ordered = _ordered(observations)
    transitions: list[Decimal] = []
    for prior, current in pairwise(ordered):
        average_price = (prior.unit_price + current.unit_price) / Decimal("2")
        price_change = (current.unit_price - prior.unit_price) / average_price
        if price_change == 0:
            continue
        average_quantity = (prior.quantity + current.quantity) / Decimal("2")
        quantity_change = (current.quantity - prior.quantity) / average_quantity
        transitions.append(quantity_change / price_change)
    if len(transitions) < 3:
        raise ValueError("elasticity signal requires three nonzero price transitions")
    events, evidence = _unique_provenance(ordered)
    return ElasticitySignal(
        elasticity=median(transitions),
        valid_transitions=len(transitions),
        event_ids=events,
        evidence_chunk_ids=evidence,
    )


def estimate_substitution_signal(
    observations: tuple[SubstitutionObservation, ...],
) -> SubstitutionSignal:
    if len(observations) < 4:
        raise ValueError("substitution signal requires at least four observations")
    ordered = _ordered(observations)
    qualifying = 0
    directional = 0
    for prior, current in pairwise(ordered):
        if current.focal_price <= prior.focal_price:
            continue
        qualifying += 1
        if (
            current.focal_quantity < prior.focal_quantity
            and current.alternative_quantity > prior.alternative_quantity
        ):
            directional += 1
    if qualifying < 1:
        raise ValueError("substitution signal requires a focal-price increase")
    events, evidence = _unique_provenance(ordered)
    return SubstitutionSignal(
        directional_score=Decimal(directional) / Decimal(qualifying),
        qualifying_transitions=qualifying,
        event_ids=events,
        evidence_chunk_ids=evidence,
    )


def detect_robust_anomalies(
    points: tuple[EconomicPoint, ...],
    *,
    z_threshold: Decimal = Decimal("3.5"),
    minimum_segment: int = 3,
    relative_change_threshold: Decimal = Decimal("0.50"),
) -> RobustAnomalyResult:
    if len(points) < minimum_segment * 2:
        raise ValueError("anomaly detection requires two complete comparison segments")
    if z_threshold <= 0 or relative_change_threshold <= 0:
        raise ValueError("anomaly thresholds must be positive")
    ordered = _ordered(points)
    values = tuple(point.value for point in ordered)
    center = median(values)
    mad = median(tuple(abs(value - center) for value in values))
    scale = mad * Decimal("1.4826")
    anomalies = (
        tuple(
            index for index, value in enumerate(values) if abs(value - center) / scale > z_threshold
        )
        if scale > 0
        else ()
    )
    changes: list[int] = []
    for split in range(minimum_segment, len(values) - minimum_segment + 1):
        prior_center = median(values[:split])
        later_center = median(values[split:])
        denominator = abs(prior_center)
        if denominator == 0:
            qualifies = later_center != 0
        else:
            qualifies = abs(later_center - prior_center) / denominator >= relative_change_threshold
        if qualifies:
            changes.append(split)
    events, evidence = _unique_provenance(ordered)
    return RobustAnomalyResult(
        median_value=center,
        median_absolute_deviation=mad,
        anomaly_indexes=anomalies,
        change_point_indexes=tuple(changes),
        event_ids=events,
        evidence_chunk_ids=evidence,
    )


def _signed(component_type: FinancialComponentType, amount: Decimal) -> Decimal:
    return -amount if component_type in _DISCOUNT_TYPES else amount


def simulate_counterfactual(
    components: tuple[CounterfactualComponent, ...],
    scenario: CounterfactualScenario,
) -> CounterfactualResult:
    if not components:
        raise ValueError("counterfactual simulation requires observed components")
    by_type = {component.component_type: component for component in components}
    if len(by_type) != len(components):
        raise ValueError("counterfactual components must be unique by type")
    currencies = {component.currency for component in components}
    if len(currencies) != 1:
        raise ValueError("counterfactual simulation cannot mix currency")
    currency = next(iter(currencies))
    simulated = {key: value.amount for key, value in by_type.items()}
    for intervention in scenario.interventions:
        if intervention.currency != currency:
            raise ValueError("counterfactual intervention currency differs from history")
        if intervention.component_type not in simulated:
            raise ValueError("counterfactual intervention targets an unobserved component")
        observed = simulated[intervention.component_type]
        if intervention.replacement_amount is not None:
            simulated[intervention.component_type] = intervention.replacement_amount
        else:
            assert intervention.delta_ratio is not None
            simulated[intervention.component_type] = observed * (
                Decimal("1") + intervention.delta_ratio
            )
    ordered = tuple(sorted(components, key=lambda item: item.component_type.value))
    observed_total = sum(
        (_signed(item.component_type, item.amount) for item in ordered),
        start=Decimal("0"),
    )
    simulated_total = sum(
        (_signed(item.component_type, simulated[item.component_type]) for item in ordered),
        start=Decimal("0"),
    )
    result_components = tuple(
        SimulatedComponent(
            component_type=item.component_type,
            observed_amount=item.amount,
            simulated_amount=simulated[item.component_type],
            currency=currency,
        )
        for item in ordered
    )
    formula = " + ".join(
        (
            f"-{item.component_type.name}"
            if item.component_type in _DISCOUNT_TYPES
            else item.component_type.name
        )
        for item in ordered
    )
    return CounterfactualResult(
        scenario_id=scenario.scenario_id,
        observed_total=observed_total,
        simulated_total=simulated_total,
        difference=simulated_total - observed_total,
        currency=currency,
        components=result_components,
        base_event_ids=scenario.base_event_ids,
        epistemic_mode=EpistemicMode.SIMULATED,
        formula=formula,
    )
