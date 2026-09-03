from __future__ import annotations

from decimal import Decimal

from lunarbit.agent import (
    AnswerDraft,
    AnswerStatus,
    QueryDisposition,
    build_query_plan,
    finalize_answer,
)
from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    QueryIntent,
    QueryTemplate,
)


def test_query_plan_selects_bounded_governed_tools_for_price_history() -> None:
    plan = build_query_plan("What did the same biryani cost at this restaurant three years ago?")

    assert plan.classification.intent is QueryIntent.EXACT_GRAPH
    assert plan.selected_templates == (QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY,)
    assert plan.traversal[-1].action.value == "finish_answer"
    assert len(plan.traversal) <= plan.policy.maximum_actions


def test_query_plan_supports_cross_restaurant_order_ranking() -> None:
    plan = build_query_plan("Which restaurants' orders are most?")
    assert plan.selected_templates == (QueryTemplate.MERCHANT_ORDER_RANKING,)


def test_query_plan_does_not_default_unknown_questions_to_merchant_count() -> None:
    plan = build_query_plan("What is my favorite color?")

    assert plan.disposition is QueryDisposition.UNSUPPORTED
    assert plan.selected_templates == ()
    assert plan.traversal == ()


def test_query_plan_requests_scope_for_unbound_order_count() -> None:
    plan = build_query_plan("How many orders did I make?")

    assert plan.disposition is QueryDisposition.CLARIFICATION_REQUIRED
    assert plan.selected_templates == ()


def test_answer_finalization_requires_claim_level_evidence() -> None:
    draft = AnswerDraft(
        direct_answer="The verified synthetic total is INR 500.00.",
        claim_ids=("claim:total",),
        calculation="INR 450.00 + INR 50.00 = INR 500.00",
        limitations=(),
    )
    citation = EvidenceCitation(
        citation_id="citation:public:1",
        chunk_node_id="chunk:private:1",
        source_node_id="document:private:1",
        source_hash="a" * 64,
        authority_score=Decimal("1.00"),
        supports_claim_ids=("claim:total",),
        quality_flags=(),
    )

    verified = finalize_answer(
        draft,
        EvidencePack(claim_ids=draft.claim_ids, citations=(citation,)),
    )
    abstained = finalize_answer(
        draft,
        EvidencePack(claim_ids=draft.claim_ids, citations=()),
    )

    assert verified.status is AnswerStatus.VERIFIED
    assert verified.direct_answer == draft.direct_answer
    assert abstained.status is AnswerStatus.ABSTAINED
    assert abstained.direct_answer is None
    assert abstained.abstention_reason == "incomplete_evidence_coverage"
