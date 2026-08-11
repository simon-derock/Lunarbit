from __future__ import annotations

from fastapi.testclient import TestClient

from lunarbit.api import create_app
from lunarbit.public import PublicMetric, assert_public_payload, build_demo_snapshot


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


def test_unknown_demo_answer_is_a_stable_not_found_contract() -> None:
    response = _client().get("/v1/demo/answers/not-a-query")

    assert response.status_code == 404
    assert response.json() == {"detail": "demo answer not found"}
