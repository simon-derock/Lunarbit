from __future__ import annotations

from decimal import Decimal

from lunarbit.cohere import RerankResult
from lunarbit.reranking import RerankStatus, rerank_fused_candidates
from lunarbit.retrieval import FusedCandidate


def _fused(candidate_id: str, score: str) -> FusedCandidate:
    return FusedCandidate(
        candidate_id=candidate_id,
        score=Decimal(score),
        channels=("dense", "lexical"),
        channel_ranks={"dense": 1, "lexical": 2},
    )


class SuccessfulReranker:
    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        assert query == "historic biryani price"
        assert documents == ("new evidence", "old evidence")
        assert top_n == 2
        return (
            RerankResult(index=1, document="old evidence", score=0.93),
            RerankResult(index=0, document="new evidence", score=0.51),
        )


class UnavailableReranker:
    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        raise RuntimeError("cohere_http_429")


def test_reranker_reorders_rrf_candidates_without_losing_provenance() -> None:
    result = rerank_fused_candidates(
        "historic biryani price",
        (_fused("chunk:new", "0.04"), _fused("chunk:old", "0.03")),
        {"chunk:new": "new evidence", "chunk:old": "old evidence"},
        SuccessfulReranker(),
        top_n=2,
    )

    assert result.status is RerankStatus.APPLIED
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "chunk:old",
        "chunk:new",
    ]
    assert result.candidates[0].rerank_score == Decimal("0.93")
    assert result.candidates[0].rrf_rank == 2
    assert result.candidates[0].channels == ("dense", "lexical")
    assert result.degradation_reason is None


def test_provider_failure_falls_back_to_deterministic_rrf_order() -> None:
    result = rerank_fused_candidates(
        "historic biryani price",
        (_fused("chunk:new", "0.04"), _fused("chunk:old", "0.03")),
        {"chunk:new": "new evidence", "chunk:old": "old evidence"},
        UnavailableReranker(),
        top_n=2,
    )

    assert result.status is RerankStatus.FALLBACK_RRF
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "chunk:new",
        "chunk:old",
    ]
    assert all(candidate.rerank_score is None for candidate in result.candidates)
    assert result.degradation_reason == "cohere_unavailable"
