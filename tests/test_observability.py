from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lunarbit.observability import InMemoryTraceSink, elapsed_milliseconds, new_trace_id


def test_trace_sink_keeps_bounded_scalar_metadata_only() -> None:
    sink = InMemoryTraceSink(max_events=1, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    trace_id = new_trace_id()

    sink.record(
        "answer.verified",
        trace_id=trace_id,
        attributes={"status": "verified", "fact_count": 2, "citation_count": 2},
    )
    sink.record(
        "answer.abstained",
        trace_id=trace_id,
        attributes={"status": "abstained", "reason": "no_graph_facts"},
    )

    events = sink.snapshot()
    assert len(events) == 1
    assert events[0].event_type == "answer.abstained"
    assert events[0].attributes == {"status": "abstained", "reason": "no_graph_facts"}
    assert events[0].occurred_at.tzinfo is not None


@pytest.mark.parametrize(
    "attributes",
    (
        {"question": "private text"},
        {"query": "MATCH (n) RETURN n"},
        {"status": "contains spaces"},
    ),
)
def test_trace_sink_rejects_private_or_unbounded_attributes(
    attributes: dict[str, str],
) -> None:
    sink = InMemoryTraceSink()

    with pytest.raises(ValueError, match="privacy-safe"):
        sink.record("request.received", trace_id=new_trace_id(), attributes=attributes)


def test_elapsed_milliseconds_never_returns_a_negative_duration() -> None:
    assert elapsed_milliseconds(10.0, clock=lambda: 9.0) == 0
