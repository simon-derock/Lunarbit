"""Privacy-safe structured trace events for the API and GraphRAG runtime."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Protocol
from uuid import uuid4

from pydantic import Field

from lunarbit.models import ContractModel


class TraceEvent(ContractModel):
    trace_id: str = Field(
        pattern=r"^trace:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    occurred_at: datetime
    attributes: dict[str, str | int | bool]


class TraceSink(Protocol):
    def record(
        self,
        event_type: str,
        *,
        trace_id: str,
        attributes: Mapping[str, str | int | bool],
    ) -> None: ...


_SAFE_ATTRIBUTE_KEY = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_PRIVATE_ATTRIBUTE_KEY = re.compile(
    r"(?:question|prompt|answer|raw|text|secret|token|password|email|address|phone|cypher|query)",
    re.IGNORECASE,
)
_SAFE_ATTRIBUTE_VALUE = re.compile(r"^[A-Za-z0-9_.:/-]{1,96}$")


def new_trace_id() -> str:
    return f"trace:{uuid4()}"


def _validate_attributes(attributes: Mapping[str, str | int | bool]) -> dict[str, str | int | bool]:
    safe: dict[str, str | int | bool] = {}
    for key, value in attributes.items():
        if not _SAFE_ATTRIBUTE_KEY.fullmatch(key) or _PRIVATE_ATTRIBUTE_KEY.search(key):
            raise ValueError("trace attribute key is not privacy-safe")
        if isinstance(value, str) and not _SAFE_ATTRIBUTE_VALUE.fullmatch(value):
            raise ValueError("trace attribute string is not privacy-safe")
        if not isinstance(value, (str, int, bool)):
            raise ValueError("trace attribute value must be scalar")
        safe[key] = value
    return safe


@dataclass(slots=True)
class InMemoryTraceSink:
    """Bounded process-local trace buffer for diagnostics and tests.

    Production deployments can adapt the same protocol to an OTEL exporter or
    structured log sink after applying the same attribute validation.
    """

    max_events: int = 10_000
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    _events: deque[TraceEvent] = field(default_factory=deque, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        if self.max_events < 1:
            raise ValueError("trace event limit must be positive")

    def record(
        self,
        event_type: str,
        *,
        trace_id: str,
        attributes: Mapping[str, str | int | bool],
    ) -> None:
        event = TraceEvent(
            trace_id=trace_id,
            event_type=event_type,
            occurred_at=self.clock(),
            attributes=_validate_attributes(attributes),
        )
        with self._lock:
            self._events.append(event)
            while len(self._events) > self.max_events:
                self._events.popleft()

    def snapshot(self) -> tuple[TraceEvent, ...]:
        with self._lock:
            return tuple(self._events)


def elapsed_milliseconds(start: float, *, clock: Callable[[], float] = monotonic) -> int:
    """Return a non-negative integer duration for safe trace attributes."""
    return max(0, round((clock() - start) * 1_000))
