"""Small, dependency-free request guardrails for the FastAPI boundary."""

from __future__ import annotations

import re
import unicodedata
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from time import monotonic
from typing import Final


class QuestionGuardrailError(ValueError):
    """Raised when a request is not safe for the Lunarbit question surface."""


_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"\s+")

# These patterns deliberately describe *intent*, not one exact jailbreak string.
# They catch case, punctuation, and whitespace variants while leaving normal
# commerce questions to the governed planner.
_PROMPT_EXTRACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:give|show|reveal|print|display|share|provide|output|repeat|recite|tell\s+me)"
        r"\b.{0,60}\b(?:your|the)\b.{0,30}\b(?:full|complete|entire|exact|verbatim|hidden|internal)?"
        r"\s*(?:system|developer|assistant|hidden|internal)\s*"
        r"(?:prompt|instructions?|message|policy|policies|rules?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:what|where|which)\b.{0,40}\b(?:system|developer|hidden|internal)\s*"
        r"(?:prompt|instructions?|message|policy|policies|rules?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ignore|disregard|forget|override|bypass|replace|jailbreak)\b"
        r".{0,100}\b(?:previous|prior|above|system|developer|assistant|instruction|policy|rule)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:repeat|quote|recite|copy|print)\b.{0,60}\b(?:above|hidden|system|developer|prompt|instructions?)\b"
        r".{0,30}\b(?:verbatim|exactly|word[- ]for[- ]word)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reveal|show|give|print|list|expose|dump|tell\s+me)\b.{0,70}\b"
        r"(?:api\s*keys?|access\s*tokens?|secret(?:s|\s+keys?)?|credentials?|"
        r"environment\s+variables?|tool\s+definitions?|function\s+schemas?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:dan\s+mode|developer\s+mode|unfiltered|uncensored|unrestricted|"
        r"no\s+guardrails?|without\s+(?:limits|restrictions))\b",
        re.IGNORECASE,
    ),
)

_ARBITRARY_QUERY_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:MATCH|MERGE|CREATE)\s*\(", re.IGNORECASE),
    re.compile(r"\bCALL\s+(?:DBMS|APOC|DB)\.", re.IGNORECASE),
    re.compile(r"\b(?:DETACH\s+)?DELETE\s+[A-Za-z_]", re.IGNORECASE),
    re.compile(r"\b(?:DROP|TRUNCATE|ALTER)\s+(?:DATABASE|TABLE|INDEX|CONSTRAINT)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b.{0,100}\b(?:FROM|INTO|SET|WHERE)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:run|execute|perform|send)\b.{0,40}\b(?:cypher|neo4j|sql|database)\b",
        re.IGNORECASE,
    ),
)

_OFF_SCOPE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:write|draft|create|generate|improve|edit|rewrite|review|tailor|format)\b"
        r".{0,60}\b(?:resume|curriculum\s+vitae|cv|cover\s+letter|linkedin)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:resume|curriculum\s+vitae|cv|cover\s+letter|linkedin)\b"
        r".{0,60}\b(?:write|draft|create|generate|improve|edit|rewrite|review|tailor)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:write|generate|create|build|debug|fix|review|refactor|implement|explain)\b"
        r".{0,60}\b(?:code|script|program|python|javascript|typescript|react|sql|api|"
        r"function|class|software|application|website)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:code|programming|software\s+development)\b.{0,60}\b"
        r"(?:write|generate|create|build|debug|fix|review|refactor|implement)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:write|draft|compose|generate|create)\b.{0,50}\b"
        r"(?:essay|story|poem|song|email|letter|blog\s+post)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:translate|translation|paraphrase)\b.{0,50}\b"
        r"(?:this|text|paragraph|document|sentence|into|from)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:plan|book|recommend|organize)\b.{0,60}\b"
        r"(?:trip|travel|vacation|flight|hotel|itinerary)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:solve|answer|do|complete|write)\b.{0,50}\b"
        r"(?:homework|exam|assignment|quiz|thesis)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:give|provide|offer|seek|need|want|request)\b.{0,50}\b"
        r"(?:medical|health|symptom|diagnos|treatment|medication|legal|lawyer|lawsuit|"
        r"contract\s+advice|tax\s+advice)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:medical|health|symptom|diagnos|treatment|medication|legal|lawyer|lawsuit|"
        r"contract\s+advice|tax\s+advice)\b.{0,50}\b(?:advice|help|diagnos|treatment)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:give|provide|write|create|recommend|suggest)\b.{0,40}\b"
        r"(?:recipe|cooking|meal\s+plan|workout|fitness\s+plan)\b",
        re.IGNORECASE,
    ),
)

_IN_SCOPE_TERMS: Final[re.Pattern[str]] = re.compile(
    r"\b(?:order|invoice|receipt|meal|food|restaurant|merchant|outlet|item|price|cost|"
    r"fee|delivery|discount|promotion|tax|payment|refund|spend(?:ing)?|membership|"
    r"subscription|platform|swiggy|zomato|biryani|grocery|instamart|history|reconcile|"
    r"reconciliation|elasticity|substitution|anomaly|financial|economic|evidence|"
    r"document|transaction|charge|tip|coupon|total)\b",
    re.IGNORECASE,
)


def _normalise_text(text: str) -> str:
    normalised = unicodedata.normalize("NFKC", text)
    if any(
        unicodedata.category(character) in {"Cc", "Cf"}
        and character not in "\t\n\r"
        for character in normalised
    ):
        raise QuestionGuardrailError("control or format character rejected")
    return _WHITESPACE.sub(" ", normalised).strip()


def validate_user_question(question: str) -> str:
    """Return normalized text or reject prompt extraction and off-scope use.

    This is intentionally deterministic and dependency-free. It is the first
    boundary before planning/retrieval; it is not a substitute for model-side
    authorization or a semantic classifier.
    """
    normalized = _normalise_text(question)
    lowered = normalized.casefold()
    if any(pattern.search(normalized) for pattern in _PROMPT_EXTRACTION_PATTERNS):
        raise QuestionGuardrailError("prompt or secret extraction rejected")
    if any(pattern.search(normalized) for pattern in _ARBITRARY_QUERY_PATTERNS):
        raise QuestionGuardrailError("arbitrary query execution rejected")
    off_scope = any(pattern.search(normalized) for pattern in _OFF_SCOPE_PATTERNS)
    # Explicit code/resume/writing requests are never made in-scope by adding
    # a food term (for example, “write Python to calculate my fees”). For less
    # specific categories, an economic term keeps ordinary summarisation safe.
    if off_scope and (
        any(pattern.search(normalized) for pattern in _OFF_SCOPE_PATTERNS[:5])
        or not _IN_SCOPE_TERMS.search(normalized)
    ):
        raise QuestionGuardrailError("off-scope task rejected")
    if not lowered:
        raise QuestionGuardrailError("empty question rejected")
    return normalized


def validate_slot_text(value: str) -> str:
    """Reject control/format characters in identifiers without limiting names."""
    return _normalise_text(value)


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
