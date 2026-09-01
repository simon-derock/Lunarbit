from __future__ import annotations

from decimal import Decimal

from lunarbit.answer_evaluation import (
    AnswerFamily,
    AnswerGolden,
    compare_answer_variants,
    evaluate_grounded_answers,
)
from lunarbit.api import PrivateGroundedAnswer
from lunarbit.runtime import QuerySlots, RuntimeRequest, RuntimeStatus


def _golden(
    case_id: str,
    *,
    status: RuntimeStatus = RuntimeStatus.VERIFIED,
) -> AnswerGolden:
    return AnswerGolden(
        case_id=case_id,
        family=AnswerFamily.FINANCIAL_AGGREGATION,
        request=RuntimeRequest(
            question="How much platform fee did I pay?",
            slots=QuerySlots(platform="swiggy", component_type="platform_fee"),
        ),
        expected_status=status,
        expected_fact_count=2 if status is RuntimeStatus.VERIFIED else 0,
        expected_direct_answer=("Verified answer" if status is RuntimeStatus.VERIFIED else None),
        expected_calculation=("Exact calculation" if status is RuntimeStatus.VERIFIED else None),
        minimum_citations=2 if status is RuntimeStatus.VERIFIED else 0,
        expected_abstention_reason=(
            "no_graph_facts" if status is RuntimeStatus.ABSTAINED else None
        ),
    )


def test_answer_evaluation_scores_exactness_support_and_abstention() -> None:
    goldens = (
        _golden("case:one"),
        _golden("case:two"),
        _golden("case:three", status=RuntimeStatus.ABSTAINED),
    )
    calls = [0]

    def run(request: RuntimeRequest) -> PrivateGroundedAnswer:
        case = calls[0]
        calls[0] += 1
        if case == 2:
            return PrivateGroundedAnswer(
                status="abstained",
                direct_answer=None,
                calculation=None,
                fact_count=0,
                citation_ids=(),
                verification_status="abstained",
                limitations=(),
                abstention_reason="no_graph_facts",
            )
        return PrivateGroundedAnswer(
            status="verified",
            direct_answer="Verified answer",
            calculation="Exact calculation" if case == 0 else "Wrong calculation",
            fact_count=2,
            citation_ids=("citation:1", "citation:2"),
            verification_status="verified",
            limitations=(),
            abstention_reason=None,
        )

    report = evaluate_grounded_answers(goldens, run)

    assert report.summary.cases == 3
    assert report.summary.status_accuracy == Decimal("1")
    assert report.summary.answer_exact_match == Decimal("1")
    assert report.summary.calculation_exact_match == Decimal("0.6666666666666666666666666667")
    assert report.summary.fact_count_accuracy == Decimal("1")
    assert report.summary.citation_support_rate == Decimal("1")
    assert report.summary.abstention_accuracy == Decimal("1")
    assert report.summary.p95_latency_ms >= report.summary.p50_latency_ms
    assert report.outcomes[1].calculation_matches is False


def test_answer_evaluation_rejects_duplicate_case_identity() -> None:
    golden = _golden("case:duplicate")

    def should_not_run(_: RuntimeRequest) -> PrivateGroundedAnswer:
        raise AssertionError("duplicate validation must run before evaluation")

    try:
        evaluate_grounded_answers((golden, golden), should_not_run)
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate answer goldens must be rejected")


def test_variant_comparison_flags_quality_regression_on_same_goldens() -> None:
    goldens = (_golden("case:ab"),)

    def baseline(_: RuntimeRequest) -> PrivateGroundedAnswer:
        return PrivateGroundedAnswer(
            status="verified",
            direct_answer="Verified answer",
            calculation="Exact calculation",
            fact_count=2,
            citation_ids=("citation:1", "citation:2"),
            verification_status="verified",
            limitations=(),
            abstention_reason=None,
        )

    def candidate(_: RuntimeRequest) -> PrivateGroundedAnswer:
        return PrivateGroundedAnswer(
            status="verified",
            direct_answer="Verified answer",
            calculation="Exact calculation",
            fact_count=2,
            citation_ids=(),
            verification_status="verified",
            limitations=(),
            abstention_reason=None,
        )

    comparison = compare_answer_variants(goldens, baseline, candidate)

    assert comparison.status_accuracy_delta == 0
    assert comparison.citation_support_rate_delta == -1
    assert comparison.candidate_non_regression is False
