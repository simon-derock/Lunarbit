from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarbit.agent import build_query_plan
from lunarbit.api import (
    DEFAULT_PUBLIC_ORIGINS,
    PrivateGroundedAnswer,
    PrivateRetrievalTrace,
    create_app,
    parse_public_origins,
)
from lunarbit.langgraph_workflow import LangGraphExecutionError
from lunarbit.observability import InMemoryTraceSink
from lunarbit.public import PublicMetric, PublicSnapshot, assert_public_payload, build_demo_snapshot
from lunarbit.retrieval import EvidenceVerification, VerificationStatus
from lunarbit.runtime import GroundedContext, QuerySlots, RuntimeRequest, RuntimeStatus


def _client() -> TestClient:
    snapshot = build_demo_snapshot(
        metrics=(
            PublicMetric(label="Orders reconstructed", value="454"),
            PublicMetric(label="Graph relationships", value="70,010"),
        )
    )
    return TestClient(create_app(snapshot=snapshot))


def test_health_and_snapshot_endpoints_publish_only_reviewed_state() -> None:
    client = _client()

    health = client.get("/health")
    snapshot = client.get("/v1/public/snapshot")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "lunarbit-api", "version": "1.0.0"}
    assert snapshot.status_code == 200
    assert snapshot.json()["mode"] == "synthetic_mirror"
    assert_public_payload(snapshot.json())


def test_readiness_distinguishes_synthetic_and_configured_graphs() -> None:
    response = _client().get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["graph"] == "synthetic"


def test_default_snapshot_uses_the_current_private_corpus_rollup() -> None:
    response = TestClient(create_app()).get("/v1/public/snapshot")
    metrics = {item["label"]: item["value"] for item in response.json()["metrics"]}

    assert metrics["Orders reconstructed"] == "454"
    assert metrics["Evidence chunks"] == "24,675"
    assert metrics["Graph nodes"] == "53,983"
    assert metrics["Graph relationships"] == "85,607"


def test_api_emits_a_request_id_and_privacy_safe_plan_trace() -> None:
    traces = InMemoryTraceSink()
    response = TestClient(create_app(trace_sink=traces)).post(
        "/v1/query/plan",
        json={"question": "How much platform fee did I pay?"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"].startswith("trace:")
    events = traces.snapshot()
    assert len(events) == 1
    assert events[0].event_type == "query.plan"
    assert events[0].attributes["intent"] == "financial_aggregation"
    assert "question" not in events[0].attributes


def test_public_api_allows_the_local_nexus_development_origin() -> None:
    response = _client().get(
        "/v1/public/snapshot",
        headers={"Origin": "http://127.0.0.1:5173"},
    )

    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_public_cors_origins_are_explicit_and_never_wildcarded() -> None:
    assert parse_public_origins(None) == DEFAULT_PUBLIC_ORIGINS
    assert parse_public_origins("https://demo.example, https://staging.example ") == (
        "https://demo.example",
        "https://staging.example",
    )
    with pytest.raises(ValueError, match="at least one origin"):
        parse_public_origins(" , ")
    with pytest.raises(ValueError, match="cannot contain a wildcard"):
        parse_public_origins("https://demo.example, *")


def test_public_snapshot_endpoint_refreshes_the_configured_safe_projection() -> None:
    expected = build_demo_snapshot(
        metrics=(PublicMetric(label="Graph nodes", value="18"),)
    ).model_copy(update={"mode": "neo4j_aggregate_projection"})

    class Source:
        def snapshot(self) -> PublicSnapshot:
            return expected

    response = TestClient(create_app(public_snapshot_source=Source())).get("/v1/public/snapshot")

    assert response.status_code == 200
    assert response.json()["mode"] == "neo4j_aggregate_projection"
    assert response.json()["metrics"] == [{"label": "Graph nodes", "value": "18", "detail": None}]


def test_live_public_snapshot_does_not_fallback_to_synthetic_data() -> None:
    from lunarbit.public_projection import PublicProjectionUnavailable

    class Unavailable:
        def snapshot(self) -> PublicSnapshot:
            raise PublicProjectionUnavailable("neo4j unavailable")

    response = TestClient(create_app(public_snapshot_source=Unavailable())).get(
        "/v1/public/snapshot"
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "live public graph projection is unavailable"}


def test_query_plan_does_not_echo_user_input_or_expose_cypher() -> None:
    client = _client()
    sensitive_question = "What did my meal cost three years ago?"

    response = client.post("/v1/query/plan", json={"question": sensitive_question})
    payload = response.json()

    assert response.status_code == 200
    assert sensitive_question not in response.text
    assert "cypher" not in response.text.casefold()
    assert payload["intent"] == "exact_graph"
    assert payload["selected_tools"] == ["merchant_item_price_history"]
    assert payload["action_budget"] == 12
    assert_public_payload(payload)


def test_demo_answer_returns_calculation_path_and_public_evidence() -> None:
    client = _client()

    response = client.get("/v1/demo/answers/price-history")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "verified"
    assert payload["calculation"]
    assert len(payload["graph_path"]) >= 4
    assert payload["evidence"]
    assert_public_payload(payload)


def test_public_showcase_answer_returns_only_a_reviewed_synthetic_scenario() -> None:
    client = _client()
    question = "Did discounts offset the rise in platform and delivery fees?"

    response = client.post("/v1/public/showcase-answer", json={"question": question})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "verified"
    assert payload["answer"]["direct_answer"].startswith("The synthetic INR 80.00 promotion")
    assert payload["plan"]["verification_required"] is True
    assert question not in response.text
    assert "cypher" not in response.text.casefold()
    assert_public_payload(payload)


def test_public_showcase_answer_abstains_outside_the_reviewed_scope() -> None:
    question = "Which restaurant should I order from tomorrow?"

    response = _client().post("/v1/public/showcase-answer", json={"question": question})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "abstained"
    assert payload["answer"] is None
    assert "reviewed synthetic showcase scenarios" in payload["limitations"][0]
    assert question not in response.text
    assert_public_payload(payload)


def test_unknown_demo_answer_is_a_stable_not_found_contract() -> None:
    response = _client().get("/v1/demo/answers/not-a-query")

    assert response.status_code == 404
    assert response.json() == {"detail": "demo answer not found"}


class StubPrivateBackend:
    def retrieve(self, question: str) -> PrivateRetrievalTrace:
        assert question == "historic meal price"
        return PrivateRetrievalTrace(
            status="verified",
            dense_candidates=30,
            lexical_candidates=30,
            evidence_count=10,
            citation_count=10,
            reranking_status="applied",
            verification_status="verified",
            degradations=(),
        )


def test_private_retrieval_requires_constant_time_bearer_authentication() -> None:
    client = TestClient(
        create_app(
            private_backend=StubPrivateBackend(),
            private_api_token="local-secret-token",
        )
    )

    missing = client.post("/v1/private/retrieval", json={"question": "historic meal price"})
    wrong = client.post(
        "/v1/private/retrieval",
        json={"question": "historic meal price"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    accepted = client.post(
        "/v1/private/retrieval",
        json={"question": "historic meal price"},
        headers={"Authorization": "Bearer local-secret-token"},
    )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["verification_status"] == "verified"
    assert "historic meal price" not in accepted.text


def test_private_retrieval_is_unavailable_without_server_side_configuration() -> None:
    response = _client().post(
        "/v1/private/retrieval",
        json={"question": "historic meal price"},
        headers={"Authorization": "Bearer anything"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "private retrieval is not configured"}


def test_public_only_api_does_not_mount_private_graphrag_routes() -> None:
    client = TestClient(create_app(include_private_routes=False))

    retrieval = client.post("/v1/private/retrieval", json={"question": "historic meal price"})
    answer = client.post("/v1/private/answer", json={"question": "How much?", "slots": {}})
    showcase = client.post(
        "/v1/public/showcase-answer",
        json={"question": "Did discounts offset delivery fees?"},
    )

    assert retrieval.status_code == 404
    assert answer.status_code == 404
    assert showcase.status_code == 200
    assert "/v1/private/retrieval" not in client.get("/openapi.json").json()["paths"]


class StubPrivateAnswerBackend:
    def answer(self, request: RuntimeRequest) -> PrivateGroundedAnswer:
        assert request.slots.component_type == "platform_fee"
        assert request.slots.platform == "swiggy"
        return PrivateGroundedAnswer(
            status="verified",
            direct_answer="The evidence-backed total is INR 10.30.",
            calculation="INR 10.10 + INR 0.20 = INR 10.30",
            fact_count=2,
            citation_ids=("runtime:citation:1", "runtime:citation:2"),
            verification_status="verified",
            limitations=("Not a bank-confirmed debit.",),
            abstention_reason=None,
        )


def test_private_answer_returns_verified_calculation_without_raw_evidence() -> None:
    client = TestClient(
        create_app(
            private_answer_backend=StubPrivateAnswerBackend(),
            private_api_token="local-secret-token",
        )
    )

    response = client.post(
        "/v1/private/answer",
        headers={"Authorization": "Bearer local-secret-token"},
        json={
            "question": "How much platform fee did I pay?",
            "slots": {"platform": "swiggy", "component_type": "platform_fee"},
        },
    )

    assert response.status_code == 200
    assert response.json()["direct_answer"] == "The evidence-backed total is INR 10.30."
    assert response.json()["citation_ids"] == [
        "runtime:citation:1",
        "runtime:citation:2",
    ]
    assert "source_hash" not in response.text
    assert "evidence_text" not in response.text


class StubPrivateWorkflow:
    def invoke(self, question: str, *, slots: QuerySlots, thread_id: str) -> GroundedContext:
        assert slots.platform == "swiggy"
        assert thread_id.startswith("session:") or thread_id.startswith("answer:")
        return GroundedContext(
            status=RuntimeStatus.VERIFIED,
            question=question,
            plan=build_query_plan(question),
            fact_count=1,
            direct_answer="The workflow found one source-backed order.",
            calculation=None,
            limitations=(),
            citations=(),
            verification=EvidenceVerification(
                status=VerificationStatus.VERIFIED,
                covered_claim_ids=("claim:one",),
                missing_claim_ids=(),
                citation_ids=("runtime:citation:1",),
            ),
            abstention_reason=None,
        )


def test_private_chat_uses_checkpointed_langgraph_workflow() -> None:
    client = TestClient(
        create_app(
            private_workflow=StubPrivateWorkflow(),
            private_api_token="local-secret-token",
        )
    )

    response = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={
            "question": "How many orders came from Ember Kitchen on Swiggy?",
            "slots": {"platform": "swiggy", "merchant_name": "ember kitchen"},
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"]["direct_answer"] == (
        "The workflow found one source-backed order."
    )


class FailingPrivateWorkflow:
    def invoke(self, question: str, *, slots: QuerySlots, thread_id: str) -> GroundedContext:
        raise LangGraphExecutionError("workflow execution failed")


def test_private_chat_maps_langgraph_failures_to_safe_http_status() -> None:
    client = TestClient(
        create_app(
            private_workflow=FailingPrivateWorkflow(),
            private_api_token="local-secret-token",
        )
    )

    response = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={"question": "How many orders came from Ember Kitchen?"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "private workflow execution failed"}


def test_private_answer_uses_the_same_bearer_security_boundary() -> None:
    client = TestClient(
        create_app(
            private_answer_backend=StubPrivateAnswerBackend(),
            private_api_token="local-secret-token",
        )
    )

    missing = client.post(
        "/v1/private/answer",
        json={"question": "How much?", "slots": {}},
    )
    wrong = client.post(
        "/v1/private/answer",
        headers={"Authorization": "Bearer wrong-token"},
        json={"question": "How much?", "slots": {}},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 403
