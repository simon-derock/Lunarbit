from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lunarbit.retrieval import GovernedQuery
from lunarbit.runtime import GraphReader, QuerySlots, RuntimeRequest
from lunarbit.service import GovernedAnswerBackend


class StubReader(GraphReader):
    def run(self, query: GovernedQuery) -> tuple[Mapping[str, Any], ...]:
        return (
            {
                "component_id": "money:1",
                "amount": "10.30",
                "currency": "INR",
                "chunk_id": "chunk:1",
                "source_id": "document:1",
                "source_hash": "a" * 64,
            },
        )


def test_governed_answer_backend_exposes_only_verified_answer_contract() -> None:
    backend = GovernedAnswerBackend(StubReader())

    answer = backend.answer(
        RuntimeRequest(
            question="How much platform fee did I pay?",
            slots=QuerySlots(platform="swiggy", component_type="platform_fee"),
        )
    )

    assert answer.status == "verified"
    assert answer.direct_answer == (
        "The evidence-backed platform fee total for Swiggy is INR 10.30 "
        "across 1 distinct component."
    )
    assert answer.citation_ids == ("runtime:citation:1",)
    assert answer.verification_status == "verified"
