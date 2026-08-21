"""Small, dependency-free request guardrails for the FastAPI boundary."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(slots=True)
class InMemoryRateLimiter:
    """Process-local fixed-window limiter for one API process.

    A distributed deployment should put a shared limiter at its edge; this
    class still protects a standalone process and is deterministic in tests.
    """

    limit: int
    window_seconds: float
    clock: Callable[[], float] = monotonic
    _events: dict[str, deque[float]] = field(default_factory=dict, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("rate limit must be positive")
        if not 0 < self.window_seconds <= 3_600:
            raise ValueError("rate-limit window must be between 0 and 3600 seconds")

    def allow(self, key: str) -> RateLimitDecision:
        if not key:
            key = "unknown"
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, ceil(events[0] + self.window_seconds - now))
                return RateLimitDecision(False, retry_after)
            events.append(now)
            return RateLimitDecision(True)
