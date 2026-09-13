from __future__ import annotations

from typing import Any

from lunarbit.query_planner import (
    _PLANNER_MAX_OUTPUT_TOKENS,
    GeminiPlanner,
    MistralPlanner,
)


def test_gemini_planner_uses_bounded_deterministic_structured_generation(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self, url, payload, key):
        captured.update(payload)
        return {
            "candidates": [
                {"content": {"parts": [{"text": '{"operations":["merchant_order_ranking"]}'}]}}
            ]
        }

    monkeypatch.setattr(GeminiPlanner, "_post", fake_post)
    proposal = GeminiPlanner("test-key").plan("rank my restaurants")

    assert proposal.operations
    assert captured["contents"][0]["parts"][0]["text"] == (
        "<user_question>\nrank my restaurants\n</user_question>"
    )
    assert captured["generationConfig"] == {
        "temperature": 0,
        "topP": 1,
        "candidateCount": 1,
        "maxOutputTokens": _PLANNER_MAX_OUTPUT_TOKENS,
        "responseMimeType": "application/json",
    }


def test_mistral_planner_uses_bounded_deterministic_structured_generation(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_post(self, url, payload, key):
        captured.update(payload)
        return {"choices": [{"message": {"content": '{"operations":["fulltext_evidence"]}'}}]}

    monkeypatch.setattr(MistralPlanner, "_post", fake_post)
    proposal = MistralPlanner("test-key").plan("show my biryani orders")

    assert proposal.operations
    assert captured["messages"][1]["content"] == (
        "<user_question>\nshow my biryani orders\n</user_question>"
    )
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == _PLANNER_MAX_OUTPUT_TOKENS
    assert captured["response_format"] == {"type": "json_object"}
