from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from lunarbit.cohere import RerankResult
from lunarbit.models import ContractModel
from lunarbit.retrieval import FusedCandidate

MAX_RERANK_CANDIDATES = 60


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]: ...


class RerankStatus(StrEnum):
    APPLIED = "applied"
    FALLBACK_RRF = "fallback_rrf"


class RankedEvidence(ContractModel):
    candidate_id: str = Field(min_length=1)
    rrf_rank: int = Field(ge=1)
    rrf_score: Decimal = Field(gt=Decimal("0"))
    rerank_score: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    channels: tuple[str, ...] = Field(min_length=1)


class RerankOutcome(ContractModel):
    status: RerankStatus
    candidates: tuple[RankedEvidence, ...] = Field(min_length=1)
    degradation_reason: str | None = None


def _fallback(
    selected: tuple[tuple[FusedCandidate, str, int], ...],
    *,
    top_n: int,
) -> RerankOutcome:
    return RerankOutcome(
        status=RerankStatus.FALLBACK_RRF,
        candidates=tuple(
            RankedEvidence(
                candidate_id=candidate.candidate_id,
                rrf_rank=rrf_rank,
                rrf_score=candidate.score,
                channels=candidate.channels,
            )
            for candidate, _, rrf_rank in selected[:top_n]
        ),
        degradation_reason="cohere_unavailable",
    )


def rerank_fused_candidates(
    question: str,
    fused: Sequence[FusedCandidate],
    documents: Mapping[str, str],
    reranker: Reranker,
    *,
    top_n: int = 10,
    candidate_limit: int = MAX_RERANK_CANDIDATES,
) -> RerankOutcome:
    if not question.strip():
        raise ValueError("rerank question cannot be empty")
    if not 1 <= candidate_limit <= MAX_RERANK_CANDIDATES:
        raise ValueError(f"candidate_limit must be between 1 and {MAX_RERANK_CANDIDATES}")
    selected = tuple(
        (candidate, text, rank)
        for rank, candidate in enumerate(fused, start=1)
        if (text := documents.get(candidate.candidate_id)) is not None and text.strip()
    )[:candidate_limit]
    if not selected:
        raise ValueError("no fused candidate has rerankable evidence text")
    if not 1 <= top_n <= len(selected):
        raise ValueError("top_n must be between one and the rerankable candidate count")
    try:
        results = reranker.rerank(
            question,
            tuple(text for _, text, _ in selected),
            top_n=top_n,
        )
    except RuntimeError:
        return _fallback(selected, top_n=top_n)
    if len(results) != top_n or len({result.index for result in results}) != len(results):
        raise ValueError("rerank response coverage changed")
    ranked: list[RankedEvidence] = []
    for result in results:
        candidate, _, rrf_rank = selected[result.index]
        ranked.append(
            RankedEvidence(
                candidate_id=candidate.candidate_id,
                rrf_rank=rrf_rank,
                rrf_score=candidate.score,
                rerank_score=Decimal(str(result.score)),
                channels=candidate.channels,
            )
        )
    return RerankOutcome(
        status=RerankStatus.APPLIED,
        candidates=tuple(ranked),
    )
