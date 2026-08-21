from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from secrets import compare_digest
from typing import Annotated, Literal, Protocol

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from starlette.responses import Response

from lunarbit.agent import build_query_plan
from lunarbit.guardrails import (
    InMemoryRateLimiter,
    QuestionGuardrailError,
    RateLimitDecision,
    validate_slot_text,
    validate_user_question,
)
from lunarbit.models import ContractModel
from lunarbit.public import (
    PublicMetric,
    PublicSnapshot,
    assert_public_payload,
    build_demo_snapshot,
)
from lunarbit.public_projection import PublicProjectionUnavailable
from lunarbit.runtime import QuerySlots, RuntimeRequest

API_VERSION = "1.0.0"
DEFAULT_PUBLIC_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def parse_public_origins(value: str | None) -> tuple[str, ...]:
    """Parse an explicit public CORS allowlist and reject wildcard deployment."""
    if value is None:
        return DEFAULT_PUBLIC_ORIGINS
    origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
    return validate_public_origins(origins)


def validate_public_origins(origins: Sequence[str]) -> tuple[str, ...]:
    """Validate CORS at the app boundary, not only in the launcher."""
    normalized = tuple(origin.strip() for origin in origins if origin.strip())
    if not normalized:
        raise ValueError("LUNARBIT_PUBLIC_ALLOWED_ORIGINS must contain at least one origin")
    if "*" in normalized:
        raise ValueError("LUNARBIT_PUBLIC_ALLOWED_ORIGINS cannot contain a wildcard")
    return normalized


class HealthResponse(ContractModel):
    status: str = "ok"
    service: str = "lunarbit-api"
    version: str = API_VERSION


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
    verification_status: str
    limitations: tuple[str, ...]
    abstention_reason: str | None


class PrivateAnswerBackend(Protocol):
    def answer(self, request: RuntimeRequest) -> PrivateGroundedAnswer: ...


class PublicSnapshotSource(Protocol):
    """Produce a browser-safe snapshot without exposing canonical graph records."""

    def snapshot(self) -> PublicSnapshot: ...


class PublicQueryPlan(ContractModel):
    intent: str
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
    """A bounded, public-only answer for one reviewed synthetic scenario.

    This intentionally is not a general-purpose answer surface.  It keeps the
    public demonstration honest: a question either maps to a reviewed scenario
    with a deterministic calculation and evidence path, or it abstains.
    """

    status: Literal["verified", "abstained"]
    plan: PublicQueryPlan
    answer: PublicDemoAnswer | None = None
    limitations: tuple[str, ...]


_DEMO_ANSWERS: dict[str, PublicDemoAnswer] = {
    "price-history": PublicDemoAnswer(
        direct_answer=(
            "In the synthetic mirror, the comparable meal rose from INR 320.00 to "
            "INR 420.00 before fees and promotions."
        ),
        calculation="INR 420.00 - INR 320.00 = INR 100.00; change = 31.25%",
        confidence_scope=(
            "Verified only for the synthetic comparable-meal group and its displayed period."
        ),
        graph_path=(
            "pub:platform:z",
            "pub:order:alpha",
            "pub:merchant:ember",
            "pub:item:biryani",
            "pub:money:item",
            "pub:evidence:summary",
        ),
        evidence=(
            PublicEvidenceCard(
                id="pub:evidence:summary",
                title="Synthetic order-summary evidence",
                authority="Primary for customer-payable and listed-item facts",
                truth_scope="Synthetic transaction mirror",
                disclosure="No private source text or identifiers are published.",
            ),
        ),
        limitations=(
            "This public trace demonstrates the production schema using synthetic values.",
            "Cross-merchant identity is not inferred without reviewed comparability evidence.",
        ),
    ),
    "fee-offset": PublicDemoAnswer(
        direct_answer=(
            "The synthetic INR 80.00 promotion more than offsets the INR 12.00 platform fee."
        ),
        calculation="INR 80.00 - INR 12.00 = INR 68.00 net synthetic benefit",
        confidence_scope="Verified for the displayed scoped components only.",
        graph_path=(
            "pub:order:alpha",
            "pub:money:discount",
            "pub:reconciliation:alpha",
            "pub:money:fee",
            "pub:evidence:fee",
        ),
        evidence=(
            PublicEvidenceCard(
                id="pub:evidence:fee",
                title="Synthetic fee evidence",
                authority="Primary for the displayed platform-fee claim",
                truth_scope="Synthetic transaction mirror",
                disclosure="No private source text or identifiers are published.",
            ),
        ),
        limitations=("The equation does not claim a bank-settled amount.",),
    ),
}


def _public_query_plan(question: str) -> PublicQueryPlan:
    plan = build_query_plan(question)
    return PublicQueryPlan(
        intent=plan.classification.intent.value,
        selected_tools=tuple(template.value for template in plan.selected_templates),
        actions=tuple(step.action.value for step in plan.traversal),
        action_budget=plan.policy.maximum_actions,
        maximum_depth=plan.policy.maximum_depth,
        candidate_paths_per_step=plan.policy.candidate_paths_per_step,
    )


def _showcase_answer_key(question: str) -> str | None:
    """Match only the two reviewed public scenarios; everything else abstains."""
    normalized = question.casefold()

    def has_any(terms: tuple[str, ...]) -> bool:
        return any(term in normalized for term in terms)

    if has_any(("discount", "promotion")) and has_any(("fee", "delivery")):
        return "fee-offset"
    if has_any(("price", "cost", "amount")) and has_any(
        ("change", "history", "historic", "year", "period", "comparable")
    ):
        return "price-history"
    return None


def _default_snapshot() -> PublicSnapshot:
    return build_demo_snapshot(
        metrics=(
            PublicMetric(label="Orders reconstructed", value="454"),
            PublicMetric(label="Evidence chunks", value="24,675"),
            PublicMetric(label="Graph nodes", value="48,784"),
            PublicMetric(label="Graph relationships", value="70,010"),
        )
    )


def create_app(
    *,
    snapshot: PublicSnapshot | None = None,
    public_snapshot_source: PublicSnapshotSource | None = None,
    allowed_origins: Sequence[str] = DEFAULT_PUBLIC_ORIGINS,
    private_backend: PrivateRetrievalBackend | None = None,
    private_answer_backend: PrivateAnswerBackend | None = None,
    private_api_token: str | None = None,
    include_private_routes: bool = True,
    public_rate_limiter: InMemoryRateLimiter | None = None,
    private_rate_limiter: InMemoryRateLimiter | None = None,
) -> FastAPI:
    cors_origins = validate_public_origins(allowed_origins)
    public_snapshot = snapshot or _default_snapshot()
    assert_public_payload(public_snapshot.model_dump(mode="json"))
    app = FastAPI(
        title="Lunarbit API",
        summary="Privacy-safe evidence-verifiable commerce GraphRAG",
        version=API_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    public_limiter = public_rate_limiter or InMemoryRateLimiter(limit=60, window_seconds=60)
    private_limiter = private_rate_limiter or InMemoryRateLimiter(limit=30, window_seconds=60)

    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    def enforce_rate_limit(request: Request, limiter: InMemoryRateLimiter) -> None:
        client_host = request.client.host if request.client is not None else "unknown"
        decision: RateLimitDecision = limiter.allow(client_host)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="request rate limit exceeded",
                headers={
                    "Retry-After": str(decision.retry_after_seconds),
                    "Cache-Control": "no-store",
                },
            )

    def enforce_question_guardrail(question: str) -> str:
        try:
            return validate_user_question(question)
        except QuestionGuardrailError as error:
            raise HTTPException(
                status_code=400,
                detail="question rejected by input guardrail",
            ) from error

    def enforce_slot_guardrail(slots: QuerySlots) -> None:
        try:
            for value in slots.model_dump(mode="python").values():
                if isinstance(value, str):
                    validate_slot_text(value)
        except QuestionGuardrailError as error:
            raise HTTPException(
                status_code=400,
                detail="slot rejected by input guardrail",
            ) from error

    def authorize_private(authorization: str | None) -> None:
        prefix = "Bearer "
        if authorization is None or not authorization.startswith(prefix):
            raise HTTPException(
                status_code=401,
                detail="bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        supplied = authorization.removeprefix(prefix)
        if (
            not supplied
            or private_api_token is None
            or not compare_digest(supplied, private_api_token)
        ):
            raise HTTPException(status_code=403, detail="invalid bearer token")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/v1/public/snapshot", response_model=PublicSnapshot)
    def public_snapshot_endpoint(request: Request) -> PublicSnapshot:
        enforce_rate_limit(request, public_limiter)
        if public_snapshot_source is None:
            return public_snapshot
        try:
            projected = public_snapshot_source.snapshot()
        except PublicProjectionUnavailable:
            # A safe demo projection is preferable to exposing partial private topology.
            projected = public_snapshot
        assert_public_payload(projected.model_dump(mode="json"))
        return projected

    @app.post("/v1/query/plan", response_model=PublicQueryPlan)
    def query_plan(request: QueryPlanRequest, http_request: Request) -> PublicQueryPlan:
        enforce_rate_limit(http_request, public_limiter)
        question = enforce_question_guardrail(request.question)
        response = _public_query_plan(question)
        assert_public_payload(response.model_dump(mode="json"))
        return response

    @app.post("/v1/public/showcase-answer", response_model=PublicShowcaseAnswer)
    def public_showcase_answer(
        request: QueryPlanRequest,
        http_request: Request,
    ) -> PublicShowcaseAnswer:
        """Return a reviewed synthetic answer or abstain without invoking private retrieval."""
        enforce_rate_limit(http_request, public_limiter)
        question = enforce_question_guardrail(request.question)
        plan = _public_query_plan(question)
        answer_key = _showcase_answer_key(question)
        if answer_key is None:
            response = PublicShowcaseAnswer(
                status="abstained",
                plan=plan,
                limitations=(
                    "This public console answers only reviewed synthetic showcase scenarios.",
                    (
                        "Private GraphRAG retrieval and source records are never available "
                        "in the browser."
                    ),
                ),
            )
        else:
            response = PublicShowcaseAnswer(
                status="verified",
                plan=plan,
                answer=_DEMO_ANSWERS[answer_key],
                limitations=(
                    (
                        "The result is a reviewed synthetic demonstration, not a query over "
                        "personal records."
                    ),
                    (
                        "Private GraphRAG retrieval and source records are never available "
                        "in the browser."
                    ),
                ),
            )
        assert_public_payload(response.model_dump(mode="json"))
        return response

    @app.get("/v1/demo/answers/{answer_key}", response_model=PublicDemoAnswer)
    def demo_answer(answer_key: str, request: Request) -> PublicDemoAnswer:
        enforce_rate_limit(request, public_limiter)
        answer = _DEMO_ANSWERS.get(answer_key)
        if answer is None:
            raise HTTPException(status_code=404, detail="demo answer not found")
        assert_public_payload(answer.model_dump(mode="json"))
        return answer

    if include_private_routes:

        @app.post("/v1/private/retrieval", response_model=PrivateRetrievalTrace)
        def private_retrieval(
            request: QueryPlanRequest,
            http_request: Request,
            authorization: Annotated[str | None, Header()] = None,
        ) -> PrivateRetrievalTrace:
            enforce_rate_limit(http_request, private_limiter)
            if private_backend is None or private_api_token is None:
                raise HTTPException(status_code=503, detail="private retrieval is not configured")
            authorize_private(authorization)
            question = enforce_question_guardrail(request.question)
            return private_backend.retrieve(question)

        @app.post("/v1/private/answer", response_model=PrivateGroundedAnswer)
        def private_answer(
            request: PrivateAnswerRequest,
            http_request: Request,
            authorization: Annotated[str | None, Header()] = None,
        ) -> PrivateGroundedAnswer:
            enforce_rate_limit(http_request, private_limiter)
            if private_answer_backend is None or private_api_token is None:
                raise HTTPException(status_code=503, detail="private answer is not configured")
            authorize_private(authorization)
            question = enforce_question_guardrail(request.question)
            enforce_slot_guardrail(request.slots)
            return private_answer_backend.answer(
                RuntimeRequest(question=question, slots=request.slots)
            )

    return app


app = create_app()
