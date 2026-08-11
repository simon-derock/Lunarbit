from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field

from lunarbit.agent import build_query_plan
from lunarbit.models import ContractModel
from lunarbit.public import (
    PublicMetric,
    PublicSnapshot,
    assert_public_payload,
    build_demo_snapshot,
)

API_VERSION = "1.0.0"


class HealthResponse(ContractModel):
    status: str = "ok"
    service: str = "lunarbit-api"
    version: str = API_VERSION


class QueryPlanRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)


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
    allowed_origins: Sequence[str] = ("http://localhost:3000",),
) -> FastAPI:
    public_snapshot = snapshot or _default_snapshot()
    assert_public_payload(public_snapshot.model_dump(mode="json"))
    app = FastAPI(
        title="Lunarbit API",
        summary="Privacy-safe evidence-verifiable commerce GraphRAG",
        version=API_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/v1/public/snapshot", response_model=PublicSnapshot)
    def public_snapshot_endpoint() -> PublicSnapshot:
        return public_snapshot

    @app.post("/v1/query/plan", response_model=PublicQueryPlan)
    def query_plan(request: QueryPlanRequest) -> PublicQueryPlan:
        plan = build_query_plan(request.question)
        response = PublicQueryPlan(
            intent=plan.classification.intent.value,
            selected_tools=tuple(template.value for template in plan.selected_templates),
            actions=tuple(step.action.value for step in plan.traversal),
            action_budget=plan.policy.maximum_actions,
            maximum_depth=plan.policy.maximum_depth,
            candidate_paths_per_step=plan.policy.candidate_paths_per_step,
        )
        assert_public_payload(response.model_dump(mode="json"))
        return response

    @app.get("/v1/demo/answers/{answer_key}", response_model=PublicDemoAnswer)
    def demo_answer(answer_key: str) -> PublicDemoAnswer:
        answer = _DEMO_ANSWERS.get(answer_key)
        if answer is None:
            raise HTTPException(status_code=404, detail="demo answer not found")
        assert_public_payload(answer.model_dump(mode="json"))
        return answer

    return app


app = create_app()
