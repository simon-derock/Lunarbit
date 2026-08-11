from __future__ import annotations

from lunarbit.api import PrivateRetrievalTrace
from lunarbit.hybrid import HybridRetriever


class HybridRetrievalBackend:
    """Map verified private GraphRAG results to the narrow FastAPI trace contract."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    def retrieve(self, question: str) -> PrivateRetrievalTrace:
        result = self._retriever.retrieve(question)
        return PrivateRetrievalTrace(
            status=result.status.value,
            dense_candidates=result.channel_counts["dense"],
            lexical_candidates=result.channel_counts["lexical"],
            evidence_count=len(result.evidence),
            citation_count=len(result.citations),
            reranking_status=(result.reranking.status.value if result.reranking else None),
            verification_status=result.verification.status.value,
            degradations=result.degradations,
        )
