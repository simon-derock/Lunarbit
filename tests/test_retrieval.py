from __future__ import annotations

from decimal import Decimal

import pytest

from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    FactFamily,
    QueryIntent,
    QueryTemplate,
    RetrievalCandidate,
    TraversalAction,
    TraversalPolicy,
    TraversalStep,
    VerificationStatus,
    authority_score,
    classify_query,
    governed_query,
    reciprocal_rank_fusion,
    validate_traversal,
    verify_evidence_pack,
)
from lunarbit.graph import RelationshipType


@pytest.mark.parametrize(
    ("question", "intent"),
    (
        ("How many times did I order from Sample Kitchen?", QueryIntent.EXACT_GRAPH),
        ("How much platform fee did I pay in 2025?", QueryIntent.FINANCIAL_AGGREGATION),
        ("Find invoice rows containing MEALX", QueryIntent.LEXICAL_LOOKUP),
        ("Which orders felt expensive for what I received?", QueryIntent.SEMANTIC_DISCOVERY),
        ("Prove the 14.24 tax", QueryIntent.EVIDENCE_REQUEST),
        (
            "Did discounts offset rising fees for comparable chicken meals?",
            QueryIntent.MULTI_HOP_ECONOMIC,
        ),
    ),
)
def test_query_classification_routes_governed_commerce_intents(
    question: str,
    intent: QueryIntent,
) -> None:
    assert classify_query(question).intent is intent


def test_governed_queries_are_read_only_parameterized_and_bounded() -> None:
    query = governed_query(
        QueryTemplate.MERCHANT_ORDER_COUNT,
        {"normalized_name": "sample kitchen", "limit": 20},
    )

    assert "$normalized_name" in query.cypher
    assert "sample kitchen" not in query.cypher
    assert query.parameters["normalized_name"] == "sample kitchen"
    assert query.parameters["limit"] == 20
    assert not {"CREATE", "MERGE", "DELETE", "SET"} & set(query.cypher.upper().split())
    with pytest.raises(ValueError, match="unexpected parameters"):
        governed_query(
            QueryTemplate.MERCHANT_ORDER_COUNT,
            {"normalized_name": "sample kitchen", "limit": 20, "cypher": "DELETE n"},
        )
    with pytest.raises(ValueError, match="row limit"):
        governed_query(
            QueryTemplate.MERCHANT_ORDER_COUNT,
            {"normalized_name": "sample kitchen", "limit": 5000},
        )


def test_reciprocal_rank_fusion_rewards_independent_retrieval_agreement() -> None:
    lexical = (
        RetrievalCandidate(candidate_id="chunk:a", channel="lexical", rank=1),
        RetrievalCandidate(candidate_id="chunk:b", channel="lexical", rank=2),
    )
    dense = (
        RetrievalCandidate(candidate_id="chunk:b", channel="dense", rank=1),
        RetrievalCandidate(candidate_id="chunk:c", channel="dense", rank=2),
    )

    fused = reciprocal_rank_fusion((lexical, dense), rank_constant=60)

    assert [candidate.candidate_id for candidate in fused] == [
        "chunk:b",
        "chunk:a",
        "chunk:c",
    ]
    assert fused[0].channels == ("dense", "lexical")
    assert fused[0].score > fused[1].score


def test_evidence_verifier_accepts_covered_claims_and_abstains_on_conflict() -> None:
    citation = EvidenceCitation(
        citation_id="citation:1",
        chunk_node_id="chunk:1",
        source_node_id="document:1",
        source_hash="a" * 64,
        authority_score=Decimal("0.95"),
        supports_claim_ids=("claim:1",),
        quality_flags=(),
    )
    accepted = verify_evidence_pack(EvidencePack(claim_ids=("claim:1",), citations=(citation,)))
    conflicting = verify_evidence_pack(
        EvidencePack(
            claim_ids=("claim:1",),
            citations=(citation.model_copy(update={"quality_flags": ("conflicting",)}),),
        )
    )
    missing = verify_evidence_pack(
        EvidencePack(claim_ids=("claim:1", "claim:2"), citations=(citation,))
    )

    assert accepted.status is VerificationStatus.VERIFIED
    assert conflicting.status is VerificationStatus.ABSTAINED
    assert conflicting.abstention_reason == "conflicting_evidence"
    assert missing.status is VerificationStatus.ABSTAINED
    assert missing.abstention_reason == "incomplete_evidence_coverage"


def test_graph_reasoning_is_bounded_by_actions_depth_and_relationship_allowlist() -> None:
    policy = TraversalPolicy(
        maximum_depth=4,
        candidate_paths_per_step=2,
        maximum_actions=5,
        row_limit=30,
        relationship_allowlist=(
            RelationshipType.ORDERED_FROM,
            RelationshipType.HAS_COMPONENT,
            RelationshipType.EVIDENCED_BY,
        ),
    )
    valid = (
        TraversalStep(action=TraversalAction.RESOLVE_ENTITY, depth=0),
        TraversalStep(
            action=TraversalAction.EXPAND_NEIGHBORS,
            depth=1,
            relationship_type=RelationshipType.ORDERED_FROM,
        ),
        TraversalStep(action=TraversalAction.VERIFY_PATH, depth=1),
        TraversalStep(action=TraversalAction.FINISH_ANSWER, depth=1),
    )

    assert validate_traversal(valid, policy) == valid
    with pytest.raises(ValueError, match="relationship allowlist"):
        validate_traversal(
            (
                TraversalStep(
                    action=TraversalAction.EXPAND_NEIGHBORS,
                    depth=1,
                    relationship_type=RelationshipType.HAS_DELIVERY_MENTION,
                ),
            ),
            policy,
        )
    with pytest.raises(ValueError, match="action budget"):
        validate_traversal(valid + valid[:2], policy)


def test_source_authority_depends_on_the_claimed_fact_family() -> None:
    summary_for_total = authority_score(FactFamily.CUSTOMER_PAYABLE_TOTAL, "order_summary")
    invoice_for_total = authority_score(
        FactFamily.CUSTOMER_PAYABLE_TOTAL,
        "restaurant_invoice",
    )
    invoice_for_supply = authority_score(
        FactFamily.RESTAURANT_TAXABLE_SUPPLY,
        "restaurant_invoice",
    )

    assert summary_for_total > invoice_for_total
    assert invoice_for_supply > invoice_for_total
    assert authority_score(FactFamily.ACTUAL_BANK_DEBIT, "order_summary") == Decimal("0")
