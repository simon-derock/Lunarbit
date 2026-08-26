from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from lunarbit.graph import RelationshipType
from lunarbit.models import ContractModel
from lunarbit.retrieval import (
    EvidencePack,
    EvidenceVerification,
    QueryClassification,
    QueryIntent,
    QueryTemplate,
    TraversalAction,
    TraversalPolicy,
    TraversalStep,
    VerificationStatus,
    classify_query,
    validate_traversal,
    verify_evidence_pack,
)

QUERY_WORKFLOW_VERSION = "query-workflow-v1.0.0"


class QueryPlan(ContractModel):
    question: str = Field(min_length=1, max_length=500)
    classification: QueryClassification
    selected_templates: tuple[QueryTemplate, ...] = Field(min_length=1)
    traversal: tuple[TraversalStep, ...] = Field(min_length=1)
    policy: TraversalPolicy
    workflow_version: str = QUERY_WORKFLOW_VERSION


def _templates_for(question: str, intent: QueryIntent) -> tuple[QueryTemplate, ...]:
    normalized = " ".join(question.casefold().split())
    if any(
        token in normalized
        for token in ("which restaurants", "most orders", "most-ordered", "top restaurants")
    ):
        return (QueryTemplate.MERCHANT_ORDER_RANKING,)
    if "delivery" in normalized and any(
        token in normalized for token in ("who", "person", "times", "delivered")
    ):
        return (QueryTemplate.DELIVERY_MENTION_COUNT,)
    if any(token in normalized for token in ("price", "cost")) and any(
        token in normalized for token in ("ago", "history", "year", "same")
    ):
        return (QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY,)
    if intent is QueryIntent.FINANCIAL_AGGREGATION:
        return (QueryTemplate.FINANCIAL_COMPONENT_SUM,)
    if intent is QueryIntent.EVIDENCE_REQUEST:
        return (QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT,)
    if intent is QueryIntent.LEXICAL_LOOKUP:
        return (QueryTemplate.FULLTEXT_EVIDENCE,)
    if intent is QueryIntent.SEMANTIC_DISCOVERY:
        return (QueryTemplate.FULLTEXT_EVIDENCE, QueryTemplate.ORDER_RECONSTRUCTION)
    if intent is QueryIntent.MULTI_HOP_ECONOMIC:
        return (
            QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY,
            QueryTemplate.FINANCIAL_COMPONENT_SUM,
        )
    return (QueryTemplate.MERCHANT_ORDER_COUNT,)


def _traversal_for(templates: tuple[QueryTemplate, ...]) -> tuple[TraversalStep, ...]:
    steps: list[TraversalStep] = [
        TraversalStep(action=TraversalAction.RESOLVE_ENTITY, depth=0),
    ]
    if QueryTemplate.FULLTEXT_EVIDENCE in templates:
        steps.append(TraversalStep(action=TraversalAction.SEARCH_EVIDENCE, depth=0))
    if any(
        template
        in {
            QueryTemplate.MERCHANT_ORDER_RANKING,
            QueryTemplate.MERCHANT_ORDER_COUNT,
            QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY,
            QueryTemplate.ORDER_RECONSTRUCTION,
        }
        for template in templates
    ):
        steps.append(
            TraversalStep(
                action=TraversalAction.EXPAND_NEIGHBORS,
                depth=1,
                relationship_type=RelationshipType.ORDERED_FROM,
            )
        )
    if QueryTemplate.DELIVERY_MENTION_COUNT in templates:
        steps.append(
            TraversalStep(
                action=TraversalAction.EXPAND_NEIGHBORS,
                depth=1,
                relationship_type=RelationshipType.HAS_DELIVERY_MENTION,
            )
        )
    if any(
        template
        in {QueryTemplate.FINANCIAL_COMPONENT_SUM, QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT}
        for template in templates
    ):
        steps.extend(
            (
                TraversalStep(action=TraversalAction.RUN_METRIC, depth=1),
                TraversalStep(
                    action=TraversalAction.EXPAND_NEIGHBORS,
                    depth=2,
                    relationship_type=RelationshipType.EVIDENCED_BY,
                ),
            )
        )
    steps.extend(
        (
            TraversalStep(action=TraversalAction.VERIFY_PATH, depth=2),
            TraversalStep(action=TraversalAction.FINISH_ANSWER, depth=2),
        )
    )
    return tuple(steps)


def build_query_plan(question: str) -> QueryPlan:
    classification = classify_query(question)
    templates = _templates_for(question, classification.intent)
    policy = TraversalPolicy(
        maximum_depth=4,
        candidate_paths_per_step=2,
        maximum_actions=12,
        row_limit=50,
        relationship_allowlist=(
            RelationshipType.ORDERED_FROM,
            RelationshipType.OUTLET_OF,
            RelationshipType.HAS_ITEM_OBSERVATION,
            RelationshipType.LISTING_OF,
            RelationshipType.HAS_COMPONENT,
            RelationshipType.EVIDENCED_BY,
            RelationshipType.RECONCILED_BY,
            RelationshipType.HAS_CHUNK,
            RelationshipType.GROUPED_INTO,
            RelationshipType.HAS_DELIVERY_MENTION,
        ),
    )
    traversal = validate_traversal(_traversal_for(templates), policy)
    return QueryPlan(
        question=question,
        classification=classification,
        selected_templates=templates,
        traversal=traversal,
        policy=policy,
    )


def build_query_plan_from_templates(
    question: str,
    templates: tuple[QueryTemplate, ...],
) -> QueryPlan:
    """Compile a validated model proposal into the governed traversal plan."""
    if not templates:
        raise ValueError("at least one governed template is required")
    policy = TraversalPolicy(
        maximum_depth=4,
        candidate_paths_per_step=2,
        maximum_actions=12,
        row_limit=50,
        relationship_allowlist=tuple(RelationshipType),
    )
    return QueryPlan(
        question=question,
        classification=QueryClassification(
            intent=QueryIntent.EXACT_GRAPH,
            confidence=Decimal("0.90"),
            signals=("structured-model-plan",),
        ),
        selected_templates=templates,
        traversal=validate_traversal(_traversal_for(templates), policy),
        policy=policy,
    )


class AnswerDraft(ContractModel):
    direct_answer: str = Field(min_length=1, max_length=2_000)
    claim_ids: tuple[str, ...] = Field(min_length=1)
    calculation: str | None = Field(default=None, max_length=2_000)
    limitations: tuple[str, ...]


class AnswerStatus(StrEnum):
    VERIFIED = "verified"
    ABSTAINED = "abstained"


class FinalAnswer(ContractModel):
    status: AnswerStatus
    direct_answer: str | None
    calculation: str | None
    limitations: tuple[str, ...]
    citation_ids: tuple[str, ...]
    verification: EvidenceVerification
    abstention_reason: str | None = None


def finalize_answer(draft: AnswerDraft, evidence: EvidencePack) -> FinalAnswer:
    if tuple(evidence.claim_ids) != tuple(draft.claim_ids):
        raise ValueError("draft and evidence claim contracts differ")
    verification = verify_evidence_pack(evidence)
    if verification.status is VerificationStatus.ABSTAINED:
        return FinalAnswer(
            status=AnswerStatus.ABSTAINED,
            direct_answer=None,
            calculation=None,
            limitations=draft.limitations,
            citation_ids=verification.citation_ids,
            verification=verification,
            abstention_reason=verification.abstention_reason,
        )
    return FinalAnswer(
        status=AnswerStatus.VERIFIED,
        direct_answer=draft.direct_answer,
        calculation=draft.calculation,
        limitations=draft.limitations,
        citation_ids=verification.citation_ids,
        verification=verification,
    )
