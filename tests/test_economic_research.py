from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic import CounterfactualIntervention, CounterfactualScenario
from lunarbit.economic_research import (
    CounterfactualComponent,
    EconomicPoint,
    ElasticityObservation,
    SubstitutionObservation,
    detect_robust_anomalies,
    estimate_price_elasticity_signal,
    estimate_substitution_signal,
    simulate_counterfactual,
)
from lunarbit.finance import EpistemicMode, FinancialComponentType


def _time(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def _evidence(suffix: int) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    return (
        (UUID(f"10000000-0000-0000-0000-{suffix:012d}"),),
        (UUID(f"20000000-0000-0000-0000-{suffix:012d}"),),
    )


def test_elasticity_is_a_descriptive_signal_with_minimum_observations() -> None:
    observations = tuple(
        ElasticityObservation(
            occurred_at=_time(index),
            unit_price=Decimal(price),
            quantity=Decimal(quantity),
            event_ids=_evidence(index)[0],
            evidence_chunk_ids=_evidence(index)[1],
        )
        for index, (price, quantity) in enumerate(
            (("100", "10"), ("110", "9"), ("120", "8"), ("130", "7")), start=1
        )
    )

    result = estimate_price_elasticity_signal(observations)

    assert result.label == "descriptive_noncausal_signal"
    assert result.elasticity < 0
    assert result.valid_transitions == 3
    assert result.event_ids and result.evidence_chunk_ids
    with pytest.raises(ValueError, match="four"):
        estimate_price_elasticity_signal(observations[:3])


def test_substitution_signal_requires_directional_cross_item_evidence() -> None:
    observations = tuple(
        SubstitutionObservation(
            occurred_at=_time(index),
            focal_price=Decimal(focal_price),
            focal_quantity=Decimal(focal_quantity),
            alternative_quantity=Decimal(alternative_quantity),
            event_ids=_evidence(index)[0],
            evidence_chunk_ids=_evidence(index)[1],
        )
        for index, (focal_price, focal_quantity, alternative_quantity) in enumerate(
            (("100", "10", "2"), ("110", "9", "3"), ("120", "8", "4"), ("130", "7", "5")),
            start=1,
        )
    )

    result = estimate_substitution_signal(observations)

    assert result.label == "descriptive_noncausal_signal"
    assert result.directional_score == Decimal("1")
    assert result.qualifying_transitions == 3


def test_robust_anomaly_detection_uses_median_mad_and_marks_change_points() -> None:
    values = ("10", "10", "11", "10", "50", "51", "50", "52")
    points = tuple(
        EconomicPoint(
            occurred_at=_time(index),
            value=Decimal(value),
            event_ids=_evidence(index)[0],
            evidence_chunk_ids=_evidence(index)[1],
        )
        for index, value in enumerate(values, start=1)
    )

    result = detect_robust_anomalies(points, z_threshold=Decimal("3.5"))

    assert result.method == "median_mad"
    assert result.change_point_indexes
    assert all(index >= 3 for index in result.change_point_indexes)
    assert result.event_ids and result.evidence_chunk_ids


def test_counterfactual_simulation_never_mutates_observed_components() -> None:
    components = (
        CounterfactualComponent(
            component_type=FinancialComponentType.ITEM_GROSS,
            amount=Decimal("300.00"),
            currency="INR",
        ),
        CounterfactualComponent(
            component_type=FinancialComponentType.PLATFORM_FEE,
            amount=Decimal("12.00"),
            currency="INR",
        ),
        CounterfactualComponent(
            component_type=FinancialComponentType.COUPON_DISCOUNT,
            amount=Decimal("50.00"),
            currency="INR",
        ),
    )
    scenario = CounterfactualScenario(
        scenario_id="scenario:no-platform-fee",
        statement="Remove the observed platform fee while holding all else fixed.",
        base_event_ids=(UUID("10000000-0000-0000-0000-000000000001"),),
        interventions=(
            CounterfactualIntervention(
                component_type=FinancialComponentType.PLATFORM_FEE,
                replacement_amount=Decimal("0.00"),
                currency="INR",
            ),
        ),
        epistemic_mode=EpistemicMode.SIMULATED,
        created_at=_time(8),
    )

    result = simulate_counterfactual(components, scenario)

    assert result.observed_total == Decimal("262.00")
    assert result.simulated_total == Decimal("250.00")
    assert result.difference == Decimal("-12.00")
    assert result.epistemic_mode is EpistemicMode.SIMULATED
    assert components[1].amount == Decimal("12.00")
