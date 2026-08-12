from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from pydantic import Field, model_validator

from lunarbit.economic import (
    EconomicFinding,
    EconomicMetric,
    ExperimentPlan,
    FindingStatus,
    Hypothesis,
    ResearchTool,
)
from lunarbit.models import ContractModel

RESEARCH_LOOP_VERSION = "governed-economic-research-v1.0.0"


class ToolVerdict(StrEnum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    INCONCLUSIVE = "inconclusive"


class ResearchStepResult(ContractModel):
    tool: ResearchTool
    verdict: ToolVerdict
    metric: EconomicMetric
    metric_value: Decimal | None
    event_ids: tuple[UUID, ...]
    evidence_chunk_ids: tuple[UUID, ...]
    calculation_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def conclusive_steps_are_evidence_bound(self) -> ResearchStepResult:
        if self.verdict is not ToolVerdict.INCONCLUSIVE and (
            not self.event_ids or not self.evidence_chunk_ids or not self.calculation_ids
        ):
            raise ValueError("conclusive research steps require calculation and evidence")
        return self


class ResearchProposal(ContractModel):
    hypothesis: Hypothesis
    experiment: ExperimentPlan

    @model_validator(mode="after")
    def experiment_is_bounded_by_hypothesis(self) -> ResearchProposal:
        if self.experiment.hypothesis_id != self.hypothesis.hypothesis_id:
            raise ValueError("experiment must test its declared hypothesis")
        if not set(self.experiment.tools) <= set(self.hypothesis.allowed_tools):
            raise ValueError("experiment tool allowlist rejected the proposal")
        if len(self.experiment.tools) > self.experiment.maximum_actions:
            raise ValueError("experiment exceeds its action budget")
        if self.hypothesis.metric not in self.experiment.required_metrics:
            raise ValueError("experiment must require the hypothesis metric")
        if len(set(self.experiment.tools)) != len(self.experiment.tools):
            raise ValueError("experiment cannot repeat a research tool")
        return self


class ResearchLedger(ContractModel):
    hypothesis_fingerprints: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def ledger_entries_are_unique(self) -> ResearchLedger:
        if len(set(self.hypothesis_fingerprints)) != len(self.hypothesis_fingerprints):
            raise ValueError("research ledger hypothesis fingerprints must be unique")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("research ledger finding IDs must be unique")
        return self


class ResearchToolExecutor(Protocol):
    def execute(self, tool: ResearchTool, hypothesis: Hypothesis) -> ResearchStepResult: ...


class ResearchRun(ContractModel):
    proposal: ResearchProposal
    steps: tuple[ResearchStepResult, ...] = Field(min_length=1)
    finding: EconomicFinding
    ledger: ResearchLedger
    workflow_version: str = RESEARCH_LOOP_VERSION


def _fingerprint(hypothesis: Hypothesis) -> str:
    normalized = " ".join(hypothesis.statement.casefold().split())
    identity = "|".join(
        (
            hypothesis.metric.value,
            normalized,
            hypothesis.valid_from.isoformat(),
            hypothesis.valid_to.isoformat(),
        )
    )
    return sha256(identity.encode()).hexdigest()


def _finding_status(steps: tuple[ResearchStepResult, ...]) -> FindingStatus:
    verdicts = {step.verdict for step in steps}
    if ToolVerdict.SUPPORTS in verdicts and ToolVerdict.REFUTES in verdicts:
        return FindingStatus.INCONCLUSIVE
    if ToolVerdict.SUPPORTS in verdicts:
        return FindingStatus.SUPPORTED
    if ToolVerdict.REFUTES in verdicts:
        return FindingStatus.REFUTED
    return FindingStatus.INCONCLUSIVE


def _finding_statement(hypothesis: Hypothesis, status: FindingStatus) -> str:
    if status is FindingStatus.SUPPORTED:
        prefix = "Deterministic evidence supports the reviewed hypothesis:"
    elif status is FindingStatus.REFUTED:
        prefix = "Deterministic evidence refutes the reviewed hypothesis:"
    else:
        prefix = "Available deterministic evidence is inconclusive for the hypothesis:"
    return f"{prefix} {hypothesis.statement}"


def execute_research_loop(
    proposal: ResearchProposal,
    executor: ResearchToolExecutor,
    *,
    ledger: ResearchLedger,
) -> ResearchRun:
    fingerprint = _fingerprint(proposal.hypothesis)
    if fingerprint in ledger.hypothesis_fingerprints:
        raise ValueError("duplicate economic hypothesis suppressed by the research ledger")
    if len(proposal.experiment.tools) > proposal.experiment.maximum_actions:
        raise ValueError("economic research action budget exceeded")
    steps: list[ResearchStepResult] = []
    for tool in proposal.experiment.tools:
        if tool not in proposal.hypothesis.allowed_tools:
            raise ValueError("economic research tool allowlist rejected execution")
        result = executor.execute(tool, proposal.hypothesis)
        if result.tool is not tool:
            raise ValueError("research tool returned a result for a different action")
        if result.metric not in proposal.experiment.required_metrics:
            raise ValueError("research tool returned an undeclared metric")
        steps.append(result)
    completed = tuple(steps)
    status = _finding_status(completed)
    event_ids = tuple(sorted({value for step in completed for value in step.event_ids}, key=str))
    evidence_ids = tuple(
        sorted({value for step in completed for value in step.evidence_chunk_ids}, key=str)
    )
    calculation_ids = tuple(sorted({value for step in completed for value in step.calculation_ids}))
    conclusive = sum(step.verdict is not ToolVerdict.INCONCLUSIVE for step in completed)
    confidence = Decimal(conclusive) / Decimal(len(completed))
    finding_digest = sha256(
        f"{proposal.hypothesis.hypothesis_id}|{proposal.experiment.experiment_id}|"
        f"{status.value}|{','.join(calculation_ids)}".encode()
    ).hexdigest()[:24]
    finding_id = f"finding:{finding_digest}"
    limitations = tuple(
        dict.fromkeys(
            (
                "The research loop reports evidence-bound association, not causal proof.",
                *(value for step in completed for value in step.limitations),
            )
        )
    )
    finding = EconomicFinding(
        finding_id=finding_id,
        hypothesis_id=proposal.hypothesis.hypothesis_id,
        experiment_id=proposal.experiment.experiment_id,
        status=status,
        statement=_finding_statement(proposal.hypothesis, status),
        event_ids=event_ids,
        evidence_chunk_ids=evidence_ids,
        calculation_ids=calculation_ids,
        confidence=confidence,
        limitations=limitations,
    )
    updated_ledger = ResearchLedger(
        hypothesis_fingerprints=tuple(sorted((*ledger.hypothesis_fingerprints, fingerprint))),
        finding_ids=tuple(sorted((*ledger.finding_ids, finding.finding_id))),
    )
    return ResearchRun(
        proposal=proposal,
        steps=completed,
        finding=finding,
        ledger=updated_ledger,
    )
