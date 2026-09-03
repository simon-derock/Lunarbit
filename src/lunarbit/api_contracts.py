from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import Field

from lunarbit.models import ContractModel
from lunarbit.public import PublicSnapshot
from lunarbit.runtime import GroundedContext, QuerySlots, RuntimeRequest

API_VERSION = "1.0.0"


class HealthResponse(ContractModel):
    status: str = "ok"
    service: str = "lunarbit-api"
    version: str = API_VERSION


class ReadinessResponse(ContractModel):
    status: Literal["ready"]
    service: str = "lunarbit-api"
    graph: Literal["configured", "synthetic"]


class QueryPlanRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)


class PrivateRetrievalTrace(ContractModel):
    status: str
    dense_candidates: int = Field(ge=0)
    lexical_candidates: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    reranking_status: str | None
    verification_status: str
    degradations: tuple[str, ...]


class PrivateRetrievalBackend(Protocol):
    def retrieve(self, question: str) -> PrivateRetrievalTrace: ...


class PrivateAnswerRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)
    slots: QuerySlots


type ConversationSessionId = Annotated[
    str,
    Field(pattern=r"^session:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]


class PrivateChatRequest(ContractModel):
    session_id: ConversationSessionId | None = None
    question: str = Field(min_length=3, max_length=500)
    slots: QuerySlots | None = None


type RuntimeCitationId = Annotated[
    str,
    Field(pattern=r"^(?:runtime:)?citation:[1-9][0-9]*$"),
]


class PrivateGroundedAnswer(ContractModel):
    status: str
    direct_answer: str | None
    calculation: str | None = Field(default=None, max_length=2_000)
    fact_count: int = Field(ge=0)
    citation_ids: tuple[RuntimeCitationId, ...]
    citations: tuple[PrivateCitation, ...] = ()
    verification_status: str
    limitations: tuple[str, ...]
    abstention_reason: str | None


class PrivateCitation(ContractModel):
    """Safe provenance envelope; source text and private identifiers never cross it."""

    citation_id: RuntimeCitationId
    chunk_node_id: str = Field(min_length=1, max_length=200)
    source_node_id: str = Field(min_length=1, max_length=200)
    authority_score: float = Field(ge=0.0, le=1.0)
    supports_claim_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...]


class PrivateChatResponse(ContractModel):
    session_id: ConversationSessionId
    turn_index: int = Field(ge=1)
    context_reused: bool
    answer: PrivateGroundedAnswer


class PrivateSessionTurn(ContractModel):
    turn_index: int = Field(ge=1)
    question: str = Field(min_length=3, max_length=500)
    status: str


class PrivateSessionHistory(ContractModel):
    session_id: ConversationSessionId
    turns: tuple[PrivateSessionTurn, ...]


class PrivateAnswerBackend(Protocol):
    def answer(self, request: RuntimeRequest) -> PrivateGroundedAnswer: ...


class PrivateWorkflowBackend(Protocol):
    def invoke(
        self,
        question: str,
        *,
        slots: QuerySlots,
        thread_id: str,
    ) -> GroundedContext: ...


class PublicSnapshotSource(Protocol):
    """Produce a browser-safe snapshot without exposing canonical graph records."""

    def snapshot(self) -> PublicSnapshot: ...


class PublicQueryPlan(ContractModel):
    intent: str
    disposition: str = "supported"
    disposition_reason: str | None = None
    selected_tools: tuple[str, ...]
    actions: tuple[str, ...]
    action_budget: int
    maximum_depth: int
    candidate_paths_per_step: int
    verification_required: bool = True


class PublicEvidenceCard(ContractModel):
    id: str = Field(pattern=r"^pub:evidence:[a-z0-9-]+$")
    title: str
    authority: str
    truth_scope: str
    disclosure: str


class PublicDemoAnswer(ContractModel):
    status: str = "verified"
    direct_answer: str
    calculation: str
    confidence_scope: str
    graph_path: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[PublicEvidenceCard, ...] = Field(min_length=1)
    limitations: tuple[str, ...]


class PublicShowcaseAnswer(ContractModel):
    """A bounded, public-only answer for one reviewed synthetic scenario."""

    status: Literal["verified", "abstained"]
    plan: PublicQueryPlan
    answer: PublicDemoAnswer | None = None
    limitations: tuple[str, ...]
