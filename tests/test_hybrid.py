from __future__ import annotations

from decimal import Decimal

from lunarbit.cohere import EmbedInputType, RerankResult
from lunarbit.hybrid import EvidenceDocument, HybridRetriever, HybridStatus
from lunarbit.retrieval import VerificationStatus


def _document(candidate_id: str, marker: str) -> EvidenceDocument:
    return EvidenceDocument(
        candidate_id=candidate_id,
        text_private=f"evidence {marker}",
        source_node_id=f"source:{marker}",
        source_hash=marker * 64,
        authority_score=Decimal("0.90"),
        quality_flags=(),
    )


class StubGraph:
    def dense_candidates(self, vector: tuple[float, ...], limit: int) -> tuple[str, ...]:
        assert vector == (0.1, 0.2)
        assert limit == 30
        return ("chunk:a", "chunk:b")

    def lexical_candidates(self, query: str, limit: int) -> tuple[str, ...]:
        assert query == "historic biryani price"
        assert limit == 30
        return ("chunk:b", "chunk:c")

    def expand_evidence(
        self, candidate_ids: tuple[str, ...]
    ) -> dict[str, EvidenceDocument]:
        assert candidate_ids == ("chunk:b", "chunk:a", "chunk:c")
        return {
            "chunk:a": _document("chunk:a", "a"),
            "chunk:b": _document("chunk:b", "b"),
            "chunk:c": _document("chunk:c", "c"),
        }


class StubCohere:
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        input_type: EmbedInputType = EmbedInputType.SEARCH_QUERY,
    ) -> tuple[tuple[float, ...], ...]:
        assert texts == ("historic biryani price",)
        assert input_type is EmbedInputType.SEARCH_QUERY
        return ((0.1, 0.2),)

    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        assert documents == ("evidence b", "evidence a", "evidence c")
        assert top_n == 2
        return (
            RerankResult(index=2, document="evidence c", score=0.94),
            RerankResult(index=0, document="evidence b", score=0.90),
        )


def test_hybrid_retrieval_fuses_expands_reranks_and_verifies_evidence() -> None:
    result = HybridRetriever(StubGraph(), StubCohere()).retrieve(
        "historic biryani price",
        top_n=2,
    )

    assert result.status is HybridStatus.VERIFIED
    assert result.channel_counts == {"dense": 2, "lexical": 2}
    assert [item.candidate_id for item in result.evidence] == ["chunk:c", "chunk:b"]
    assert result.reranking.candidates[1].rrf_rank == 1
    assert result.verification.status is VerificationStatus.VERIFIED
    assert len(result.citations) == 2
    assert result.degradations == ()


class UnavailableCohere(StubCohere):
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        input_type: EmbedInputType = EmbedInputType.SEARCH_QUERY,
    ) -> tuple[tuple[float, ...], ...]:
        raise RuntimeError("cohere_http_429")

    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        raise RuntimeError("cohere_http_429")


class LexicalGraph(StubGraph):
    def lexical_candidates(self, query: str, limit: int) -> tuple[str, ...]:
        return ("chunk:b", "chunk:c")

    def expand_evidence(
        self, candidate_ids: tuple[str, ...]
    ) -> dict[str, EvidenceDocument]:
        return {
            "chunk:b": _document("chunk:b", "b"),
            "chunk:c": _document("chunk:c", "c"),
        }


def test_cohere_outage_degrades_to_verified_lexical_rrf_retrieval() -> None:
    result = HybridRetriever(LexicalGraph(), UnavailableCohere()).retrieve(
        "historic biryani price",
        top_n=2,
    )

    assert result.status is HybridStatus.VERIFIED_DEGRADED
    assert result.channel_counts == {"dense": 0, "lexical": 2}
    assert [item.candidate_id for item in result.evidence] == ["chunk:b", "chunk:c"]
    assert result.degradations == ("dense_unavailable", "rerank_unavailable")
    assert result.verification.status is VerificationStatus.VERIFIED
