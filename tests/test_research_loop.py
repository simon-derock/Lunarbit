from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic import (
    EconomicMetric,
    ExperimentPlan,
    FindingStatus,
    Hypothesis,
    HypothesisOrigin,
    ResearchTool,
)
from lunarbit.research_loop import (
    ResearchLedger,
    ResearchProposal,
    ResearchStepResult,
    ToolVerdict,
    execute_research_loop,
)


def _time(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def _proposal(*, tools: tuple[ResearchTool, ...] | None = None) -> ResearchProposal:
    selected = tools or (ResearchTool.RUN_METRIC, ResearchTool.RETRIEVE_EVIDENCE)
    hypothesis = Hypothesis(
        hypothesis_id="hypothesis:fee-burden-rise",
        statement="Fee burden increased during the reviewed period.",
        metric=EconomicMetric.FEE_BURDEN,
        origin=HypothesisOrigin.LLM_PROPOSED,
        valid_from=_time(1),
        valid_to=_time(5),
        allowed_tools=(ResearchTool.RUN_METRIC, ResearchTool.RETRIEVE_EVIDENCE),
    )
    return ResearchProposal(
        hypothesis=hypothesis,
        experiment=ExperimentPlan(
            experiment_id="experiment:fee-burden-rise",
            hypothesis_id=hypothesis.hypothesis_id,
            tools=selected,
            maximum_actions=3,
            required_metrics=(EconomicMetric.FEE_BURDEN,),
            created_at=_time(6),
        ),
    )


class SupportingTools:
    def execute(self, tool: ResearchTool, hypothesis: Hypothesis) -> ResearchStepResult:
        suffix = 1 if tool is ResearchTool.RUN_METRIC else 2
        return ResearchStepResult(
            tool=tool,
            verdict=ToolVerdict.SUPPORTS,
            metric=hypothesis.metric,
            metric_value=Decimal("0.12"),
            event_ids=(UUID(f"10000000-0000-0000-0000-{suffix:012d}"),),
            evidence_chunk_ids=(UUID(f"20000000-0000-0000-0000-{suffix:012d}"),),
            calculation_ids=(f"calculation:{suffix}",),
            limitations=(),
        )


def test_research_loop_produces_evidence_bound_finding_and_updated_ledger() -> None:
    result = execute_research_loop(
        _proposal(),
        SupportingTools(),
        ledger=ResearchLedger(),
    )

    assert result.finding.status is FindingStatus.SUPPORTED
    assert len(result.steps) == 2
    assert len(result.finding.event_ids) == 2
    assert len(result.finding.evidence_chunk_ids) == 2
    assert len(result.finding.calculation_ids) == 2
    assert result.finding.confidence == Decimal("1")
    assert result.ledger.hypothesis_fingerprints


def test_research_loop_rejects_disallowed_tools_before_execution() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        execute_research_loop(
            _proposal(tools=(ResearchTool.RUN_COUNTERFACTUAL,)),
            SupportingTools(),
            ledger=ResearchLedger(),
        )


def test_research_loop_suppresses_duplicate_hypotheses() -> None:
    first = execute_research_loop(_proposal(), SupportingTools(), ledger=ResearchLedger())

    with pytest.raises(ValueError, match="duplicate"):
        execute_research_loop(_proposal(), SupportingTools(), ledger=first.ledger)


class UnsupportedTools:
    def execute(self, tool: ResearchTool, hypothesis: Hypothesis) -> ResearchStepResult:
        return ResearchStepResult(
            tool=tool,
            verdict=ToolVerdict.SUPPORTS,
            metric=hypothesis.metric,
            metric_value=Decimal("0.12"),
            event_ids=(),
            evidence_chunk_ids=(),
            calculation_ids=(),
            limitations=("No source evidence was returned.",),
        )


def test_research_loop_refuses_support_without_calculation_and_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        execute_research_loop(_proposal(), UnsupportedTools(), ledger=ResearchLedger())
