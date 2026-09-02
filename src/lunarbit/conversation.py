"""Bounded, private conversational state for governed GraphRAG answers."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from lunarbit.runtime import QuerySlots


class SessionNotFoundError(LookupError):
    """Raised when a client refers to an expired or unknown conversation."""


@dataclass(frozen=True, slots=True)
class SessionTurn:
    question: str
    slots: QuerySlots
    status: str


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    session_id: str
    contextual_question: str
    slots: QuerySlots
    turn_index: int
    context_reused: bool


@dataclass(slots=True)
class _SessionState:
    session_id: str
    created_at: float
    updated_at: float
    next_turn_index: int = 1
    turns: list[SessionTurn] = field(default_factory=list)


def merge_query_slots(previous: QuerySlots | None, current: QuerySlots | None) -> QuerySlots:
    """Overlay only explicitly supplied slots onto the previous turn."""
    values = previous.model_dump(mode="python") if previous is not None else {}
    if current is not None:
        values.update(current.model_dump(mode="python", exclude_unset=True))
    return QuerySlots.model_validate(values)


def infer_query_slots(question: str) -> QuerySlots:
    """Extract only high-precision slots; names and identities remain explicit."""
    normalized = re.sub(r"\s+", " ", question.casefold()).strip()
    values: dict[str, str] = {}
    merchant_match = re.search(
        r"\b(?:from|at|with)\s+([a-z0-9][a-z0-9 &'()./-]{1,158}?)"
        r"(?=\s*[?.!,;]|\s+(?:in|on|during|between|for)\b|$)",
        normalized,
    )
    if merchant_match:
        merchant_name = merchant_match.group(1).strip(" .,-")
        # Platform names are not merchant identities. Without this guard,
        # “orders on Swiggy” becomes merchant=swiggy.
        if merchant_name not in {"swiggy", "zomato"}:
            values["merchant_name"] = merchant_name
    for platform in ("swiggy", "zomato"):
        if re.search(rf"\b{platform}\b", normalized):
            values["platform"] = platform
            break
    component_terms = (
        ("platform_fee", ("platform fee", "platform-fee")),
        ("delivery_charge", ("delivery fee", "delivery charge")),
        ("packing_charge", ("packing fee", "packing charge")),
        ("handling_fee", ("handling fee", "handling charge")),
        ("discount", ("discount", "promotion", "coupon")),
        ("tax", ("tax", "gst")),
        ("refund", ("refund", "refunded")),
    )
    for component_type, terms in component_terms:
        if any(term in normalized for term in terms):
            values["component_type"] = component_type
            break
    if re.search(r"\b(?:show|list|find|search)\b.*\b(?:orders?|dishes?|items?)\b", normalized):
        values["lexical_query"] = normalized[:300]
    return QuerySlots.model_validate(values)


def _contextual_question(previous: str | None, current: str) -> str:
    if previous is None:
        return current[:500]
    marker = " Follow-up: "
    if len(current) >= 500:
        return current[:500]
    available = max(0, 500 - len(marker) - len(current))
    # Keep the complete new question and only the necessary prefix of the
    # previous turn so RuntimeRequest's bounded question contract still holds.
    return f"{previous[:available]}{marker}{current}"


@dataclass(slots=True)
class ConversationStore:
    """Process-local, TTL-bound session memory for the authenticated API.

    State is intentionally ephemeral: a restart drops conversational context,
    and no raw evidence, answer text, or credentials are stored here. A
    multi-replica deployment should replace this with an authenticated shared
    store that preserves the same bounded contract and TTL semantics.
    """

    ttl_seconds: float = 1_800
    max_sessions: int = 1_000
    max_turns: int = 8
    clock: Callable[[], float] = monotonic
    _sessions: dict[str, _SessionState] = field(default_factory=dict, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        if not 1 <= self.ttl_seconds <= 86_400:
            raise ValueError("conversation TTL must be between 1 and 86400 seconds")
        if self.max_sessions < 1:
            raise ValueError("conversation session limit must be positive")
        if self.max_turns < 1:
            raise ValueError("conversation turn limit must be positive")

    def _purge_expired(self, now: float) -> None:
        expired = tuple(
            session_id
            for session_id, state in self._sessions.items()
            if now - state.updated_at >= self.ttl_seconds
        )
        for session_id in expired:
            del self._sessions[session_id]

    def _require(self, session_id: str) -> _SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise SessionNotFoundError(session_id)
        return state

    def create(self) -> str:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda item: item.updated_at)
                del self._sessions[oldest.session_id]
            session_id = f"session:{uuid4()}"
            self._sessions[session_id] = _SessionState(
                session_id=session_id,
                created_at=now,
                updated_at=now,
            )
            return session_id

    def prepare(
        self,
        session_id: str,
        *,
        question: str,
        slots: QuerySlots | None,
    ) -> PreparedTurn:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            state = self._require(session_id)
            previous = state.turns[-1] if state.turns else None
            return PreparedTurn(
                session_id=session_id,
                contextual_question=_contextual_question(
                    previous.question if previous is not None else None,
                    question,
                ),
                slots=merge_query_slots(previous.slots if previous is not None else None, slots),
                turn_index=state.next_turn_index,
                context_reused=previous is not None,
            )

    def append(
        self,
        session_id: str,
        *,
        question: str,
        slots: QuerySlots,
        status: str,
    ) -> int:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            state = self._require(session_id)
            turn_index = state.next_turn_index
            state.turns.append(SessionTurn(question=question, slots=slots, status=status))
            state.turns = state.turns[-self.max_turns :]
            state.next_turn_index += 1
            state.updated_at = now
            return turn_index

    def contextual_question(self, session_id: str, question: str) -> str:
        """Return a bounded follow-up question for planner/runtime context."""
        return self.prepare(session_id, question=question, slots=None).contextual_question

    def history(self, session_id: str) -> tuple[SessionTurn, ...]:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            return tuple(self._require(session_id).turns)


class SQLiteConversationStore:
    """Durable bounded session store for single-node or shared-volume deploys."""

    def __init__(
        self,
        path: str,
        *,
        ttl_seconds: float = 1_800,
        max_sessions: int = 1_000,
        max_turns: int = 8,
    ) -> None:
        if not path.strip():
            raise ValueError("conversation database path cannot be empty")
        self._memory = ConversationStore(
            ttl_seconds=ttl_seconds, max_sessions=max_sessions, max_turns=max_turns
        )
        database_path = Path(path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = Lock()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL);"
            "CREATE TABLE IF NOT EXISTS turns ("
            "session_id TEXT NOT NULL, turn_index INTEGER NOT NULL, "
            "question TEXT NOT NULL, slots TEXT NOT NULL, status TEXT NOT NULL, "
            "PRIMARY KEY(session_id, turn_index));"
        )
        self._db.commit()

    def _load(self, session_id: str) -> None:
        rows = self._db.execute(
            "SELECT question, slots, status FROM turns WHERE session_id = ? ORDER BY turn_index",
            (session_id,),
        ).fetchall()
        if session_id not in self._memory._sessions:
            if not self._db.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone():
                raise SessionNotFoundError(session_id)
            now = self._memory.clock()
            self._memory._sessions[session_id] = _SessionState(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                next_turn_index=len(rows) + 1,
                turns=[],
            )
        state = self._memory._sessions[session_id]
        state.turns = [
            SessionTurn(
                question=q, slots=QuerySlots.model_validate(json.loads(slots)), status=status
            )
            for q, slots, status in rows
        ]
        state.next_turn_index = len(state.turns) + 1

    def create(self) -> str:
        with self._lock:
            session_id = self._memory.create()
            self._db.execute(
                "INSERT INTO sessions(id, created, updated) VALUES (?, ?, ?)", (session_id, 0, 0)
            )
            self._db.commit()
            return session_id

    def prepare(self, session_id: str, *, question: str, slots: QuerySlots | None) -> PreparedTurn:
        with self._lock:
            self._load(session_id)
            return self._memory.prepare(session_id, question=question, slots=slots)

    def append(self, session_id: str, *, question: str, slots: QuerySlots, status: str) -> int:
        with self._lock:
            self._load(session_id)
            index = self._memory.append(session_id, question=question, slots=slots, status=status)
            self._db.execute(
                "INSERT INTO turns(session_id, turn_index, question, slots, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, index, question, slots.model_dump_json(), status),
            )
            self._db.commit()
            return index

    def history(self, session_id: str) -> tuple[SessionTurn, ...]:
        with self._lock:
            self._load(session_id)
            return self._memory.history(session_id)

    def close(self) -> None:
        """Release the SQLite connection during graceful service shutdown."""
        with self._lock:
            self._db.close()
