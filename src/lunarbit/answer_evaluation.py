from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from math import ceil
from time import monotonic_ns

from pydantic import Field, model_validator

from lunarbit.api import PrivateGroundedAnswer
from lunarbit.models import ContractModel
from lunarbit.runtime import RuntimeRequest, RuntimeStatus

ANSWER_EVALUATION_VERSION = "grounded-answer-evaluation-v1.0.0"


class AnswerFamily(StrEnum):
    FINANCIAL_AGGREGATION = "financial_aggregation"
    PRICE_HISTORY = "price_history"
    MERCHANT_ORDER_COUNT = "merchant_order_count"
    DELIVERY_MENTION_COUNT = "delivery_mention_count"
    ABSTENTION = "abstention"


class AnswerGolden(ContractModel):
    case_id: str = Field(pattern=r"^case:[a-z0-9][a-z0-9-]*$")
    family: AnswerFamily
    request: RuntimeRequest
    expected_status: RuntimeStatus
    expected_fact_count: int = Field(ge=0)
    expected_direct_answer: str | None = Field(default=None, repr=False)
    expected_calculation: str | None = Field(default=None, repr=False)
    minimum_citations: int = Field(ge=0)
    expected_abstention_reason: str | None = None

    @model_validator(mode="after")
    def expectation_is_coherent(self) -> AnswerGolden:
        if self.expected_status is RuntimeStatus.VERIFIED:
            if (
                self.expected_fact_count < 1
                or self.expected_direct_answer is None
                or self.minimum_citations < 1
                or self.expected_abstention_reason is not None
            ):
                raise ValueError("verified goldens require facts, an answer, and citations")
        elif (
            self.expected_direct_answer is not None
            or self.expected_calculation is not None
            or self.expected_abstention_reason is None
        ):
            raise ValueError("abstention goldens cannot expect answer content")
        return self


class AnswerCaseOutcome(ContractModel):
    case_id: str
    family: AnswerFamily
    status_matches: bool
    answer_matches: bool
    calculation_matches: bool
    fact_count_matches: bool
    citation_supports: bool
    abstention_matches: bool
    latency_ms: Decimal = Field(ge=Decimal("0"))


class AnswerEvaluationSummary(ContractModel):
    cases: int = Field(ge=1)
    status_accuracy: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    answer_exact_match: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    calculation_exact_match: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    fact_count_accuracy: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    citation_support_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    abstention_accuracy: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    p50_latency_ms: Decimal = Field(ge=Decimal("0"))
    p95_latency_ms: Decimal = Field(ge=Decimal("0"))


class AnswerEvaluationReport(ContractModel):
    evaluation_version: str = ANSWER_EVALUATION_VERSION
    outcomes: tuple[AnswerCaseOutcome, ...]
    summary: AnswerEvaluationSummary


def _rate(values: tuple[bool, ...]) -> Decimal:
    return Decimal(sum(values)) / Decimal(len(values))


def _percentile(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal:
    ordered = tuple(sorted(values))
    index = max(0, ceil(float(percentile) * len(ordered)) - 1)
    return ordered[index]


def evaluate_grounded_answers(
    goldens: tuple[AnswerGolden, ...],
    run: Callable[[RuntimeRequest], PrivateGroundedAnswer],
) -> AnswerEvaluationReport:
    if not goldens:
        raise ValueError("answer evaluation requires at least one golden")
    case_ids = tuple(golden.case_id for golden in goldens)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("answer golden case IDs must be unique")
    outcomes: list[AnswerCaseOutcome] = []
    for golden in goldens:
        started = monotonic_ns()
        observed = run(golden.request)
        latency_ms = Decimal(monotonic_ns() - started) / Decimal("1000000")
        expected_status = golden.expected_status.value
        outcomes.append(
            AnswerCaseOutcome(
                case_id=golden.case_id,
                family=golden.family,
                status_matches=observed.status == expected_status,
                answer_matches=(observed.direct_answer == golden.expected_direct_answer),
                calculation_matches=(observed.calculation == golden.expected_calculation),
                fact_count_matches=(observed.fact_count == golden.expected_fact_count),
                citation_supports=(
                    len(observed.citation_ids) >= golden.minimum_citations
                    and observed.verification_status == expected_status
                ),
                abstention_matches=(
                    observed.abstention_reason == golden.expected_abstention_reason
                ),
                latency_ms=latency_ms,
            )
        )
    values = tuple(outcomes)
    latencies = tuple(value.latency_ms for value in values)
    abstentions = tuple(
        value.abstention_matches
        for value, golden in zip(values, goldens, strict=True)
        if golden.expected_status is RuntimeStatus.ABSTAINED
    )
    return AnswerEvaluationReport(
        outcomes=values,
        summary=AnswerEvaluationSummary(
            cases=len(values),
            status_accuracy=_rate(tuple(value.status_matches for value in values)),
            answer_exact_match=_rate(tuple(value.answer_matches for value in values)),
            calculation_exact_match=_rate(tuple(value.calculation_matches for value in values)),
            fact_count_accuracy=_rate(tuple(value.fact_count_matches for value in values)),
            citation_support_rate=_rate(tuple(value.citation_supports for value in values)),
            abstention_accuracy=_rate(abstentions) if abstentions else Decimal("1"),
            p50_latency_ms=_percentile(latencies, Decimal("0.50")),
            p95_latency_ms=_percentile(latencies, Decimal("0.95")),
        ),
    )
