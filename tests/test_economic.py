from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from lunarbit.economic import (
    CounterfactualIntervention,
    CounterfactualScenario,
    EconomicFinding,
    EconomicMetric,
    FinancialEvent,
    FinancialEventType,
    FindingStatus,
    Hypothesis,
    HypothesisOrigin,
    IndexObservation,
    ResearchTool,
    financial_event_id,
)
from lunarbit.finance import (
    EpistemicMode,
    FinancialComponentType,
    FinancialScope,
    TruthScope,
)


def _time(day: int) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC)


def _event() -> FinancialEvent:
    return FinancialEvent(
        event_id=financial_event_id(
            component_ids=(UUID("10000000-0000-0000-0000-000000000001"),),
            event_type=FinancialEventType.CHARGE_ASSESSED,
            occurred_at=_time(1),
        ),
        event_type=FinancialEventType.CHARGE_ASSESSED,
        component_ids=(UUID("10000000-0000-0000-0000-000000000001"),),
        order_ids=(UUID("20000000-0000-0000-0000-000000000001"),),
        amount=Decimal("12.00"),
        currency="INR",
        scope=FinancialScope.ORDER,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        occurred_at=_time(1),
        observed_at=_time(2),
        valid_from=_time(1),
        valid_to=None,
        source_chunk_ids=(UUID("30000000-0000-0000-0000-000000000001"),),
        source_hashes=("a" * 64,),
    )


def test_financial_event_is_decimal_temporal_provenance_and_content_addressed() -> None:
    event = _event()
    repeated = financial_event_id(
        component_ids=event.component_ids,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
    )

    assert event.event_id == repeated
    assert event.amount == Decimal("12.00")
    assert event.source_chunk_ids and event.source_hashes
    with pytest.raises(ValidationError):
        FinancialEvent.model_validate({**event.model_dump(), "amount": 12.0})


def test_financial_event_rejects_invalid_validity_interval() -> None:
    with pytest.raises(ValidationError, match="valid_to"):
        FinancialEvent.model_validate(
            {**_event().model_dump(), "valid_to": _time(1), "valid_from": _time(2)}
        )


def test_index_observation_requires_evidence_and_bounded_coverage() -> None:
    observation = IndexObservation(
        period_start=_time(1),
        period_end=_time(2),
        value=Decimal("103.25"),
        coverage_ratio=Decimal("0.90"),
        event_ids=(_event().event_id,),
        calculation_id="calc:pfpi:2026-08",
    )

    assert observation.value == Decimal("103.25")
    with pytest.raises(ValidationError):
        IndexObservation.model_validate(
            {**observation.model_dump(), "coverage_ratio": Decimal("1.01")}
        )


def test_economic_finding_cannot_exist_without_experiment_and_evidence() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="hypothesis:fee-burden",
        statement="Fee burden increased in the reviewed period.",
        metric=EconomicMetric.FEE_BURDEN,
        origin=HypothesisOrigin.LLM_PROPOSED,
        valid_from=_time(1),
        valid_to=_time(2),
        allowed_tools=(ResearchTool.RUN_METRIC, ResearchTool.RETRIEVE_EVIDENCE),
    )

    with pytest.raises(ValidationError, match="evidence"):
        EconomicFinding(
            finding_id="finding:fee-burden",
            hypothesis_id=hypothesis.hypothesis_id,
            experiment_id="experiment:fee-burden",
            status=FindingStatus.SUPPORTED,
            statement="Fee burden increased.",
            event_ids=(),
            evidence_chunk_ids=(),
            calculation_ids=(),
            confidence=Decimal("0.90"),
            limitations=(),
        )


def test_counterfactuals_are_explicitly_simulated_and_do_not_mutate_history() -> None:
    scenario = CounterfactualScenario(
        scenario_id="scenario:no-platform-fee",
        statement="Remove the observed platform fee while holding other components fixed.",
        base_event_ids=(_event().event_id,),
        interventions=(
            CounterfactualIntervention(
                component_type=FinancialComponentType.PLATFORM_FEE,
                replacement_amount=Decimal("0.00"),
                currency="INR",
            ),
        ),
        epistemic_mode=EpistemicMode.SIMULATED,
        created_at=_time(2),
    )

    assert scenario.epistemic_mode is EpistemicMode.SIMULATED
    with pytest.raises(ValidationError, match="simulated"):
        CounterfactualScenario.model_validate(
            {**scenario.model_dump(), "epistemic_mode": EpistemicMode.OBSERVED}
        )
