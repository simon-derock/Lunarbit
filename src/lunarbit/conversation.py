"""Bounded, private conversational state for governed GraphRAG answers."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Lock
from time import monotonic, time
from typing import Literal
from uuid import uuid4

from lunarbit.runtime import QuerySlots


class SessionNotFoundError(LookupError):
    """Raised when a client refers to an expired or unknown conversation."""


class ReviewStateError(ValueError):
    """Raised when an invalid human-review transition is requested."""


ReviewStatus = Literal["not_required", "pending", "approved", "rejected"]


@dataclass(frozen=True, slots=True)
class SessionTurn:
    question: str
    slots: QuerySlots
    status: str
    turn_index: int = 0
    review_required: bool = False
    review_reason: str | None = None
    review_status: ReviewStatus = "not_required"


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
        r"(?=\s*[?.!,;]|\s+(?:in|on|during|between|for|ago)\b|"
        r"\s+(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+)?"
        r"(?:years?|months?)\b|$)",
        normalized,
    )
    if merchant_match:
        merchant_name = merchant_match.group(1).strip(" .,-")
        # Platform names are not merchant identities. Without this guard,
        # “orders on Swiggy” becomes merchant=swiggy.
        if merchant_name not in {"swiggy", "zomato"}:
            values["merchant_name"] = merchant_name
    item_match = re.search(
        r"\b(?:same|item|dish|food)\s+"
        r"([a-z0-9][a-z0-9 &'()./-]{1,78}?)"
        r"(?=\s+(?:cost|price|at|from|three|two|one)\b|[?.!,;]|$)",
        normalized,
    )
    if item_match:
        values["item_name"] = item_match.group(1).strip(" .,-")
    delivery_match = re.search(
        r"\b(?:delivery\s+(?:person|partner|agent)|driver)\s*[:=-]?\s*"
        r"([a-z][a-z .'-]{1,78}?)(?=\s+(?:deliver|delivered|bring|brought)\b|[?.!,;]|$)",
        normalized,
    ) or re.search(r"\b(?:did|by|for)\s+([a-z][a-z .'-]{1,78}?)\s+deliver(?:ed)?\b", normalized)
    if delivery_match:
        values["delivery_name"] = delivery_match.group(1).strip(" .,-")
    component_match = re.search(
        r"\b(?:money|fee|charge)\s+component\s+([a-z0-9][a-z0-9:._-]{1,159})\b",
        normalized,
    )
    if component_match:
        values["component_id"] = component_match.group(1)
    order_match = re.search(
        r"\b(?:reconstruct\s+order|order)\s+(ord(?:er)?[- :_]?[a-z0-9-]+)\b",
        normalized,
    )
    if order_match:
        values["order_id"] = order_match.group(1)
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
        review_required: bool = False,
        review_reason: str | None = None,
    ) -> int:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            state = self._require(session_id)
            turn_index = state.next_turn_index
            state.turns.append(
                SessionTurn(
                    question=question,
                    slots=slots,
                    status=status,
                    turn_index=turn_index,
                    review_required=review_required,
                    review_reason=review_reason,
                    review_status="pending" if review_required else "not_required",
                )
            )
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

    def turn(self, session_id: str, turn_index: int) -> SessionTurn:
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            for turn in self._require(session_id).turns:
                if turn.turn_index == turn_index:
                    return turn
            raise ReviewStateError("review turn not found")

    def resolve_review(
        self,
        session_id: str,
        turn_index: int,
        decision: Literal["approved", "rejected"],
    ) -> SessionTurn:
        if decision not in {"approved", "rejected"}:
            raise ReviewStateError("review decision must be approved or rejected")
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            state = self._require(session_id)
            for index, turn in enumerate(state.turns):
                if turn.turn_index != turn_index:
                    continue
                if not turn.review_required or turn.review_status != "pending":
                    raise ReviewStateError("review is not pending")
                updated = replace(turn, review_status=decision)
                state.turns[index] = updated
                state.updated_at = now
                return updated
            raise ReviewStateError("review turn not found")


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
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._max_turns = max_turns
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
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(turns)").fetchall()}
        if "review_required" not in columns:
            self._db.execute(
                "ALTER TABLE turns ADD COLUMN review_required INTEGER NOT NULL DEFAULT 0"
            )
        if "review_reason" not in columns:
            self._db.execute("ALTER TABLE turns ADD COLUMN review_reason TEXT")
        if "review_status" not in columns:
            self._db.execute(
                "ALTER TABLE turns ADD COLUMN review_status TEXT NOT NULL DEFAULT 'not_required'"
            )
        self._db.commit()

    def _purge_database(self, now: float) -> None:
        """Expire durable sessions before they are admitted into memory."""
        expired = self._db.execute(
            "SELECT id FROM sessions WHERE ? - updated >= ?",
            (now, self._ttl_seconds),
        ).fetchall()
        for (session_id,) in expired:
            self._db.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        count = self._db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        while count >= self._max_sessions:
            oldest = self._db.execute(
                "SELECT id FROM sessions ORDER BY updated ASC LIMIT 1"
            ).fetchone()
            if oldest is None:
                break
            self._db.execute("DELETE FROM turns WHERE session_id = ?", (oldest[0],))
            self._db.execute("DELETE FROM sessions WHERE id = ?", (oldest[0],))
            count -= 1
        self._db.commit()

    def _load(self, session_id: str) -> None:
        session = self._db.execute(
            "SELECT created, updated FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None:
            raise SessionNotFoundError(session_id)
        if time() - float(session[1]) >= self._ttl_seconds:
            self._db.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._db.commit()
            raise SessionNotFoundError(session_id)
        rows = self._db.execute(
            "SELECT turn_index, question, slots, status, review_required, review_reason, "
            "review_status "
            "FROM turns WHERE session_id = ? ORDER BY turn_index DESC LIMIT ?",
            (session_id, self._max_turns),
        ).fetchall()
        rows.reverse()
        if session_id not in self._memory._sessions:
            now = self._memory.clock()
            self._memory._sessions[session_id] = _SessionState(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                next_turn_index=(int(rows[-1][0]) + 1) if rows else 1,
                turns=[],
            )
        state = self._memory._sessions[session_id]
        state.turns = [
            SessionTurn(
                question=row[1],
                slots=QuerySlots.model_validate(json.loads(row[2])),
                status=row[3],
                turn_index=int(row[0]),
                review_required=bool(row[4]),
                review_reason=row[5],
                review_status=("pending" if bool(row[4]) and row[6] == "not_required" else row[6]),
            )
            for row in rows
        ]
        state.next_turn_index = (int(rows[-1][0]) + 1) if rows else 1

    def create(self) -> str:
        with self._lock:
            self._purge_database(time())
            session_id = self._memory.create()
            now = time()
            self._db.execute(
                "INSERT INTO sessions(id, created, updated) VALUES (?, ?, ?)",
                (session_id, now, now),
            )
            self._db.commit()
            return session_id

    def prepare(self, session_id: str, *, question: str, slots: QuerySlots | None) -> PreparedTurn:
        with self._lock:
            self._load(session_id)
            return self._memory.prepare(session_id, question=question, slots=slots)

    def append(
        self,
        session_id: str,
        *,
        question: str,
        slots: QuerySlots,
        status: str,
        review_required: bool = False,
        review_reason: str | None = None,
    ) -> int:
        with self._lock:
            self._load(session_id)
            index = self._memory.append(
                session_id,
                question=question,
                slots=slots,
                status=status,
                review_required=review_required,
                review_reason=review_reason,
            )
            self._db.execute(
                "INSERT INTO turns(session_id, turn_index, question, slots, status, "
                "review_required, review_reason, review_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    index,
                    question,
                    slots.model_dump_json(),
                    status,
                    int(review_required),
                    review_reason,
                    "pending" if review_required else "not_required",
                ),
            )
            self._db.execute("UPDATE sessions SET updated = ? WHERE id = ?", (time(), session_id))
            self._db.commit()
            return index

    def history(self, session_id: str) -> tuple[SessionTurn, ...]:
        with self._lock:
            self._load(session_id)
            return self._memory.history(session_id)

    def turn(self, session_id: str, turn_index: int) -> SessionTurn:
        with self._lock:
            self._load(session_id)
            return self._memory.turn(session_id, turn_index)

    def resolve_review(
        self,
        session_id: str,
        turn_index: int,
        decision: Literal["approved", "rejected"],
    ) -> SessionTurn:
        with self._lock:
            self._load(session_id)
            updated = self._memory.resolve_review(session_id, turn_index, decision)
            self._db.execute(
                "UPDATE turns SET review_status = ? WHERE session_id = ? AND turn_index = ?",
                (decision, session_id, turn_index),
            )
            self._db.execute("UPDATE sessions SET updated = ? WHERE id = ?", (time(), session_id))
            self._db.commit()
            return updated

    def close(self) -> None:
        """Release the SQLite connection during graceful service shutdown."""
        with self._lock:
            self._db.close()
