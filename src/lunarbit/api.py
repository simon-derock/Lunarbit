from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from secrets import compare_digest
from time import monotonic, sleep
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from neo4j.exceptions import Neo4jError
from starlette.responses import Response

from lunarbit.agent import build_query_plan
from lunarbit.api_contracts import (
    API_VERSION,
    HealthResponse,
    PrivateAnswerBackend,
    PrivateAnswerRequest,
    PrivateChatRequest,
    PrivateChatResponse,
    PrivateGroundedAnswer,
    PrivateRetrievalBackend,
    PrivateRetrievalTrace,
    PrivateWorkflowBackend,
    PublicDemoAnswer,
    PublicEvidenceCard,
    PublicQueryPlan,
    PublicShowcaseAnswer,
    PublicSnapshotSource,
    QueryPlanRequest,
)
from lunarbit.conversation import (
    ConversationStore,
    SessionNotFoundError,
    infer_query_slots,
    merge_query_slots,
)
from lunarbit.guardrails import (
    InMemoryRateLimiter,
    QuestionGuardrailError,
    RateLimitDecision,
    validate_slot_text,
    validate_user_question,
)
from lunarbit.langgraph_workflow import (
    LangGraphCheckpointError,
    LangGraphExecutionError,
    LangGraphGuardrailError,
    LangGraphInputError,
    LangGraphStateError,
)
from lunarbit.observability import InMemoryTraceSink, TraceSink, elapsed_milliseconds, new_trace_id
from lunarbit.public import (
    PublicMetric,
    PublicSnapshot,
    assert_public_payload,
    build_demo_snapshot,
)
from lunarbit.public_projection import PublicProjectionUnavailable
from lunarbit.runtime import QuerySlots, RuntimeRequest

__all__ = [
    "PrivateGroundedAnswer",
    "PrivateRetrievalTrace",
    "create_app",
    "parse_public_origins",
    "validate_public_origins",
]

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
            PublicMetric(label="Graph nodes", value="53,983"),
            PublicMetric(label="Graph relationships", value="85,607"),
        )
    )


def create_app(
    *,
    snapshot: PublicSnapshot | None = None,
    public_snapshot_source: PublicSnapshotSource | None = None,
    allowed_origins: Sequence[str] = DEFAULT_PUBLIC_ORIGINS,
    private_backend: PrivateRetrievalBackend | None = None,
    private_answer_backend: PrivateAnswerBackend | None = None,
    private_workflow: PrivateWorkflowBackend | None = None,
    private_api_token: str | None = None,
    include_private_routes: bool = True,
    public_rate_limiter: InMemoryRateLimiter | None = None,
    private_rate_limiter: InMemoryRateLimiter | None = None,
    conversation_store: ConversationStore | None = None,
    trace_sink: TraceSink | None = None,
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
    sessions = conversation_store or ConversationStore()
    traces = trace_sink or InMemoryTraceSink()

    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.trace_id = new_trace_id()
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Request-ID"] = request.state.trace_id
        return response

    def record_trace(
        request: Request,
        event_type: str,
        attributes: dict[str, str | int | bool],
    ) -> None:
        try:
            traces.record(
                event_type,
                trace_id=request.state.trace_id,
                attributes=attributes,
            )
        except ValueError:
            # Diagnostics must never turn a verified answer into an API error.
            return

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

    def run_private_workflow(
        question: str,
        *,
        slots: QuerySlots,
        thread_id: str,
    ) -> PrivateGroundedAnswer:
        if private_workflow is None:
            raise HTTPException(status_code=503, detail="private workflow is not configured")
        try:
            context = private_workflow.invoke(question, slots=slots, thread_id=thread_id)
        except LangGraphGuardrailError as error:
            raise HTTPException(
                status_code=400,
                detail="question rejected by input guardrail",
            ) from error
        except LangGraphInputError as error:
            raise HTTPException(
                status_code=422,
                detail="invalid private workflow request",
            ) from error
        except LangGraphCheckpointError as error:
            raise HTTPException(
                status_code=404,
                detail="conversation checkpoint not found",
            ) from error
        except LangGraphExecutionError as error:
            raise HTTPException(
                status_code=503,
                detail="private workflow execution failed",
            ) from error
        except LangGraphStateError as error:
            raise HTTPException(
                status_code=500,
                detail="private workflow returned invalid state",
            ) from error
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
        except Neo4jError as error:
            sleep(0.25)
            try:
                projected = public_snapshot_source.snapshot()
            except Neo4jError as retry_error:
                raise HTTPException(
                    status_code=503,
                    detail="live public graph projection is temporarily unavailable",
                ) from retry_error
        except PublicProjectionUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail="live public graph projection is unavailable",
            ) from error
        assert_public_payload(projected.model_dump(mode="json"))
        return projected

    @app.post("/v1/query/plan", response_model=PublicQueryPlan)
    def query_plan(request: QueryPlanRequest, http_request: Request) -> PublicQueryPlan:
        enforce_rate_limit(http_request, public_limiter)
        started = monotonic()
        question = enforce_question_guardrail(request.question)
        response = _public_query_plan(question)
        record_trace(
            http_request,
            "query.plan",
            {
                "intent": response.intent,
                "action_count": len(response.actions),
                "duration_ms": elapsed_milliseconds(started),
            },
        )
        assert_public_payload(response.model_dump(mode="json"))
        return response

    @app.post("/v1/public/showcase-answer", response_model=PublicShowcaseAnswer)
    def public_showcase_answer(
        request: QueryPlanRequest,
        http_request: Request,
    ) -> PublicShowcaseAnswer:
        """Return a reviewed synthetic answer or abstain without invoking private retrieval."""
        enforce_rate_limit(http_request, public_limiter)
        started = monotonic()
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
        record_trace(
            http_request,
            "public.showcase",
            {
                "status": response.status,
                "intent": response.plan.intent,
                "duration_ms": elapsed_milliseconds(started),
            },
        )
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
            started = monotonic()
            result = private_backend.retrieve(question)
            record_trace(
                http_request,
                "private.retrieval",
                {
                    "status": result.status,
                    "dense_candidates": result.dense_candidates,
                    "lexical_candidates": result.lexical_candidates,
                    "evidence_count": result.evidence_count,
                    "citation_count": result.citation_count,
                    "duration_ms": elapsed_milliseconds(started),
                },
            )
            return result

        @app.post("/v1/private/answer", response_model=PrivateGroundedAnswer)
        def private_answer(
            request: PrivateAnswerRequest,
            http_request: Request,
            authorization: Annotated[str | None, Header()] = None,
        ) -> PrivateGroundedAnswer:
            enforce_rate_limit(http_request, private_limiter)
            if (
                private_answer_backend is None and private_workflow is None
            ) or private_api_token is None:
                raise HTTPException(status_code=503, detail="private answer is not configured")
            authorize_private(authorization)
            question = enforce_question_guardrail(request.question)
            enforce_slot_guardrail(request.slots)
            started = monotonic()
            if private_workflow is not None:
                result = run_private_workflow(
                    question,
                    slots=request.slots,
                    thread_id=f"answer:{http_request.state.trace_id}",
                )
            else:
                assert private_answer_backend is not None
                result = private_answer_backend.answer(
                    RuntimeRequest(question=question, slots=request.slots)
                )
            record_trace(
                http_request,
                "private.answer",
                {
                    "status": result.status,
                    "fact_count": result.fact_count,
                    "citation_count": len(result.citation_ids),
                    "verification_status": result.verification_status,
                    "duration_ms": elapsed_milliseconds(started),
                },
            )
            return result

        @app.post("/v1/private/chat", response_model=PrivateChatResponse)
        def private_chat(
            request: PrivateChatRequest,
            http_request: Request,
            authorization: Annotated[str | None, Header()] = None,
        ) -> PrivateChatResponse:
            enforce_rate_limit(http_request, private_limiter)
            if (
                private_answer_backend is None and private_workflow is None
            ) or private_api_token is None:
                raise HTTPException(status_code=503, detail="private answer is not configured")
            authorize_private(authorization)
            question = enforce_question_guardrail(request.question)
            if request.slots is not None:
                enforce_slot_guardrail(request.slots)
            session_id = request.session_id or sessions.create()
            try:
                inferred = infer_query_slots(question)
                inferred_slots = merge_query_slots(
                    inferred if inferred.model_fields_set else None,
                    request.slots,
                )
                prepared = sessions.prepare(
                    session_id,
                    question=question,
                    slots=inferred_slots,
                )
            except SessionNotFoundError as error:
                raise HTTPException(
                    status_code=404,
                    detail="conversation session not found",
                ) from error
            if private_workflow is not None:
                answer = run_private_workflow(
                    prepared.contextual_question,
                    slots=prepared.slots,
                    thread_id=session_id,
                )
            else:
                assert private_answer_backend is not None
                answer = private_answer_backend.answer(
                    RuntimeRequest(question=prepared.contextual_question, slots=prepared.slots)
                )
            turn_index = sessions.append(
                session_id,
                question=question,
                slots=prepared.slots,
                status=answer.status,
            )
            record_trace(
                http_request,
                "private.chat",
                {
                    "status": answer.status,
                    "turn_index": turn_index,
                    "context_reused": prepared.context_reused,
                    "fact_count": answer.fact_count,
                    "citation_count": len(answer.citation_ids),
                },
            )
            return PrivateChatResponse(
                session_id=session_id,
                turn_index=turn_index,
                context_reused=prepared.context_reused,
                answer=answer,
            )

    return app


app = create_app()
