from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarbit.api import PrivateGroundedAnswer, create_app
from lunarbit.conversation import (
    ConversationStore,
    SessionNotFoundError,
    SQLiteConversationStore,
    infer_query_slots,
    merge_query_slots,
)
from lunarbit.runtime import QuerySlots, RuntimeRequest


def test_session_store_keeps_bounded_follow_up_context_and_merges_only_explicit_slots() -> None:
    store = ConversationStore(max_turns=2)
    session_id = store.create()
    first_slots = QuerySlots(platform="swiggy", component_type="platform_fee", limit=20)
    store.append(
        session_id,
        question="How much platform fee did I pay?",
        slots=first_slots,
        status="verified",
    )

    follow_up_slots = QuerySlots(component_type="delivery_charge")
    merged = merge_query_slots(first_slots, follow_up_slots)
    contextual = store.contextual_question(session_id, "What about last month?")

    assert merged.platform == "swiggy"
    assert merged.component_type == "delivery_charge"
    assert merged.limit == 20
    assert "How much platform fee did I pay?" in contextual
    assert contextual.endswith("Follow-up: What about last month?")


def test_session_store_evicts_expired_state_without_leaking_previous_turns() -> None:
    now = [100.0]
    store = ConversationStore(ttl_seconds=10, clock=lambda: now[0])
    session_id = store.create()
    store.append(
        session_id,
        question="How much did I spend?",
        slots=QuerySlots(),
        status="verified",
    )
    now[0] = 111.0

    with pytest.raises(SessionNotFoundError):
        store.contextual_question(session_id, "What about last month?")


def test_slot_inference_only_extracts_high_precision_financial_terms() -> None:
    slots = infer_query_slots("How much platform fee did I pay on Swiggy?")

    assert slots.platform == "swiggy"
    assert slots.component_type == "platform_fee"
    assert slots.merchant_name is None


def test_slot_inference_binds_bounded_lexical_queries_for_order_lists() -> None:
    slots = infer_query_slots("Show all my biryani orders")

    assert slots.lexical_query == "show all my biryani orders"
    assert slots.merchant_name is None


def test_slot_inference_extracts_temporal_item_and_delivery_entities() -> None:
    price = infer_query_slots("What did the same biryani cost at KMS Hakkim three years ago?")
    delivery = infer_query_slots("How many times did Ram deliver my orders?")

    assert price.item_name == "biryani"
    assert price.merchant_name == "kms hakkim"
    assert delivery.delivery_name == "ram"


def test_slot_inference_extracts_explicit_component_and_order_ids() -> None:
    component = infer_query_slots("Show evidence for money component MC-123")
    order = infer_query_slots("Reconstruct order ORD-4821")

    assert component.component_id == "mc-123"
    assert order.order_id == "ord-4821"


def test_sqlite_store_recovers_bounded_history_after_reopen(tmp_path) -> None:
    database = tmp_path / "sessions.sqlite3"
    first = SQLiteConversationStore(str(database))
    session_id = first.create()
    first.append(
        session_id, question="How much did I spend?", slots=QuerySlots(), status="verified"
    )

    reopened = SQLiteConversationStore(str(database))
    history = reopened.history(session_id)
    assert len(history) == 1
    assert history[0].question == "How much did I spend?"
    assert history[0].status == "verified"


def test_sqlite_store_creates_explicit_persistent_parent_directory(tmp_path) -> None:
    database = tmp_path / "persistent" / "sessions.sqlite3"

    store = SQLiteConversationStore(str(database))
    session_id = store.create()

    assert database.exists()
    assert session_id.startswith("session:")


def test_sqlite_store_uses_durable_concurrency_pragmas(tmp_path) -> None:
    store = SQLiteConversationStore(str(tmp_path / "sessions.sqlite3"))

    assert store._db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert store._db.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_sqlite_store_can_be_reopened_after_explicit_close(tmp_path) -> None:
    database = tmp_path / "sessions.sqlite3"
    first = SQLiteConversationStore(str(database))
    session_id = first.create()
    first.close()

    reopened = SQLiteConversationStore(str(database))
    assert reopened.history(session_id) == ()


class StubConversationBackend:
    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []

    def answer(self, request: RuntimeRequest) -> PrivateGroundedAnswer:
        self.requests.append(request)
        return PrivateGroundedAnswer(
            status="verified",
            direct_answer="Verified answer.",
            calculation="INR 10.00",
            fact_count=1,
            citation_ids=("runtime:citation:1",),
            verification_status="verified",
            limitations=(),
            abstention_reason=None,
        )


def test_private_chat_carries_context_and_slots_across_follow_up_turns() -> None:
    backend = StubConversationBackend()
    client = TestClient(
        create_app(
            private_answer_backend=backend,
            private_api_token="local-secret-token",
        )
    )

    first = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={
            "question": "How much platform fee did I pay?",
            "slots": {"platform": "swiggy", "component_type": "platform_fee"},
        },
    )
    session_id = first.json()["session_id"]
    second = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={"session_id": session_id, "question": "What about last month?"},
    )

    assert first.status_code == 200
    assert first.json()["turn_index"] == 1
    assert first.json()["context_reused"] is False
    assert second.status_code == 200
    assert second.json()["turn_index"] == 2
    assert second.json()["context_reused"] is True
    assert "How much platform fee did I pay?" in backend.requests[1].question
    assert backend.requests[1].slots.platform == "swiggy"
    assert backend.requests[1].slots.component_type == "platform_fee"


def test_private_chat_infers_only_high_precision_slots_when_none_are_supplied() -> None:
    backend = StubConversationBackend()
    client = TestClient(
        create_app(
            private_answer_backend=backend,
            private_api_token="local-secret-token",
        )
    )

    response = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={"question": "How much platform fee did I pay on Swiggy?"},
    )

    assert response.status_code == 200
    assert backend.requests[0].slots.platform == "swiggy"
    assert backend.requests[0].slots.component_type == "platform_fee"


def test_private_chat_rejects_unknown_session_without_echoing_identifier() -> None:
    client = TestClient(
        create_app(
            private_answer_backend=StubConversationBackend(),
            private_api_token="local-secret-token",
        )
    )
    unknown = "session:00000000-0000-0000-0000-000000000000"

    response = client.post(
        "/v1/private/chat",
        headers={"Authorization": "Bearer local-secret-token"},
        json={"session_id": unknown, "question": "How much did I spend?"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "conversation session not found"}
    assert unknown not in response.text
