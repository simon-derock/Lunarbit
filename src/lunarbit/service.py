from __future__ import annotations

from lunarbit.api import PrivateGroundedAnswer, PrivateRetrievalTrace
from lunarbit.hybrid import HybridRetriever
from lunarbit.runtime import (
    GraphReader,
    MissingQuerySlotError,
    RuntimeRequest,
    retrieve_grounded_context,
)


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


class GovernedAnswerBackend:
    """Run allowlisted graph queries and expose only evidence-verified answers."""

    def __init__(self, reader: GraphReader) -> None:
        self._reader = reader

    def answer(self, request: RuntimeRequest) -> PrivateGroundedAnswer:
        try:
            context = retrieve_grounded_context(request, self._reader)
        except MissingQuerySlotError as error:
            return PrivateGroundedAnswer(
                status="abstained",
                direct_answer=None,
                calculation=None,
                fact_count=0,
                citation_ids=(),
                verification_status="abstained",
                limitations=("The request needs a more specific governed scope or slot.",),
                abstention_reason=f"missing_query_slot:{str(error).split()[0]}",
            )
        return PrivateGroundedAnswer(
            status=context.status.value,
            direct_answer=context.direct_answer,
            calculation=context.calculation,
            fact_count=context.fact_count,
            citation_ids=context.verification.citation_ids,
            verification_status=context.verification.status.value,
            limitations=context.limitations,
            abstention_reason=context.abstention_reason,
        )
