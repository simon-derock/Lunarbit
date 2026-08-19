from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.finance import (
    EpistemicMode,
    FinancialComponentType,
    FinancialScope,
    TruthScope,
)
from lunarbit.models import ContractModel

ECONOMIC_POLICY_VERSION = "economic-intelligence-v1.0.0"


class FinancialEventType(StrEnum):
    PURCHASE_ASSERTED = "purchase_asserted"
    CHARGE_ASSESSED = "charge_assessed"
    DISCOUNT_APPLIED = "discount_applied"
    MEMBERSHIP_BENEFIT_REALIZED = "membership_benefit_realized"
    TAX_ASSESSED = "tax_assessed"
    PAYMENT_ASSERTED = "payment_asserted"
    REFUND_ASSERTED = "refund_asserted"
    RECONCILIATION_RESIDUAL = "reconciliation_residual"


class EconomicMetric(StrEnum):
    PERSONAL_FOOD_PRICE_INDEX = "personal_food_price_index"
    SPENDING_CHANGE = "spending_change"
    FEE_BURDEN = "fee_burden"
    DISCOUNT_CAPTURE = "discount_capture"
    MEMBERSHIP_ROI = "membership_roi"
    PRICE_ELASTICITY_SIGNAL = "price_elasticity_signal"
    SUBSTITUTION_SIGNAL = "substitution_signal"
    ANOMALY_SCORE = "anomaly_score"


class HypothesisOrigin(StrEnum):
    USER_PROPOSED = "user_proposed"
    LLM_PROPOSED = "llm_proposed"
    DETERMINISTIC_TRIGGER = "deterministic_trigger"


class ResearchTool(StrEnum):
    RUN_METRIC = "run_metric"
    RETRIEVE_EVIDENCE = "retrieve_evidence"
    COMPARE_PERIODS = "compare_periods"
    EXPAND_GRAPH = "expand_graph"
    RUN_COUNTERFACTUAL = "run_counterfactual"


class FindingStatus(StrEnum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def financial_event_id(
    *,
    component_ids: tuple[UUID, ...],
    event_type: FinancialEventType,
    occurred_at: datetime,
) -> UUID:
    if not component_ids:
        raise ValueError("financial event identity requires a money component")
    _aware(occurred_at, "occurred_at")
    identity = ",".join(sorted(str(value) for value in component_ids))
    return uuid5(
        NAMESPACE_URL,
        f"lunarbit-financial-event-v1:{event_type.value}:{occurred_at.isoformat()}:{identity}",
    )


class FinancialEvent(ContractModel):
    event_id: UUID
    event_type: FinancialEventType
    component_ids: tuple[UUID, ...] = Field(min_length=1)
    order_ids: tuple[UUID, ...]
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    scope: FinancialScope
    epistemic_mode: EpistemicMode
    truth_scope: TruthScope
    occurred_at: datetime
    observed_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    source_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    source_hashes: tuple[str, ...] = Field(min_length=1)
    policy_version: str = ECONOMIC_POLICY_VERSION

    @model_validator(mode="after")
    def temporal_identity_and_provenance_are_valid(self) -> FinancialEvent:
        for name in ("occurred_at", "observed_at", "valid_from"):
            _aware(getattr(self, name), name)
        if self.valid_to is not None:
            _aware(self.valid_to, "valid_to")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be later than valid_from")
        if len(self.source_chunk_ids) != len(self.source_hashes):
            raise ValueError("every source chunk must carry one source hash")
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in self.source_hashes
        ):
            raise ValueError("source hashes must be lowercase SHA-256 values")
        expected = financial_event_id(
            component_ids=self.component_ids,
            event_type=self.event_type,
            occurred_at=self.occurred_at,
        )
        if self.event_id != expected:
            raise ValueError("financial event ID must be content-addressed")
        return self


class IndexObservation(ContractModel):
    period_start: datetime
    period_end: datetime
    value: Decimal
    coverage_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    calculation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def period_is_valid(self) -> IndexObservation:
        _aware(self.period_start, "period_start")
        _aware(self.period_end, "period_end")
        if self.period_end <= self.period_start:
            raise ValueError("index period_end must be later than period_start")
        return self


class EconomicSeries(ContractModel):
    series_id: str = Field(min_length=1)
    metric: EconomicMetric
    dimensions: dict[str, str]
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    observations: tuple[IndexObservation, ...] = Field(min_length=1)
    algorithm_version: str = ECONOMIC_POLICY_VERSION

    @model_validator(mode="after")
    def observations_are_ordered(self) -> EconomicSeries:
        starts = tuple(value.period_start for value in self.observations)
        if starts != tuple(sorted(starts)) or len(set(starts)) != len(starts):
            raise ValueError("economic observations must be unique and chronological")
        return self


class Hypothesis(ContractModel):
    hypothesis_id: str = Field(pattern=r"^hypothesis:[a-z0-9][a-z0-9-]*$")
    statement: str = Field(min_length=12, max_length=500)
    metric: EconomicMetric
    origin: HypothesisOrigin
    valid_from: datetime
    valid_to: datetime
    allowed_tools: tuple[ResearchTool, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def research_window_is_valid(self) -> Hypothesis:
        _aware(self.valid_from, "valid_from")
        _aware(self.valid_to, "valid_to")
        if self.valid_to <= self.valid_from:
            raise ValueError("hypothesis valid_to must be later than valid_from")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("hypothesis tools must be unique")
        return self


class ExperimentPlan(ContractModel):
    experiment_id: str = Field(pattern=r"^experiment:[a-z0-9][a-z0-9-]*$")
    hypothesis_id: str = Field(pattern=r"^hypothesis:[a-z0-9][a-z0-9-]*$")
    tools: tuple[ResearchTool, ...] = Field(min_length=1)
    maximum_actions: int = Field(ge=1, le=20)
    required_metrics: tuple[EconomicMetric, ...] = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def created_time_is_valid(self) -> ExperimentPlan:
        _aware(self.created_at, "created_at")
        return self


class EconomicFinding(ContractModel):
    finding_id: str = Field(pattern=r"^finding:[a-z0-9][a-z0-9-]*$")
    hypothesis_id: str = Field(pattern=r"^hypothesis:[a-z0-9][a-z0-9-]*$")
    experiment_id: str = Field(pattern=r"^experiment:[a-z0-9][a-z0-9-]*$")
    status: FindingStatus
    statement: str = Field(min_length=12, max_length=1_000)
    event_ids: tuple[UUID, ...]
    evidence_chunk_ids: tuple[UUID, ...]
    calculation_ids: tuple[str, ...]
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def conclusion_is_evidence_bound(self) -> EconomicFinding:
        if self.status is not FindingStatus.INCONCLUSIVE and (
            not self.event_ids or not self.evidence_chunk_ids or not self.calculation_ids
        ):
            raise ValueError("supported or refuted findings require calculation and evidence")
        return self


class CounterfactualIntervention(ContractModel):
    component_type: FinancialComponentType
    replacement_amount: Decimal | None = None
    delta_ratio: Decimal | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def exactly_one_intervention_is_declared(self) -> CounterfactualIntervention:
        if (self.replacement_amount is None) == (self.delta_ratio is None):
            raise ValueError("declare exactly one replacement amount or delta ratio")
        return self


class CounterfactualScenario(ContractModel):
    scenario_id: str = Field(pattern=r"^scenario:[a-z0-9][a-z0-9-]*$")
    statement: str = Field(min_length=12, max_length=500)
    base_event_ids: tuple[UUID, ...] = Field(min_length=1)
    interventions: tuple[CounterfactualIntervention, ...] = Field(min_length=1)
    epistemic_mode: EpistemicMode
    created_at: datetime

    @model_validator(mode="after")
    def scenario_is_explicitly_simulated(self) -> CounterfactualScenario:
        _aware(self.created_at, "created_at")
        if self.epistemic_mode is not EpistemicMode.SIMULATED:
            raise ValueError("counterfactual scenarios must remain simulated")
        return self
