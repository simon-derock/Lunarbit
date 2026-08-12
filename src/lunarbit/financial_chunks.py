from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.economic import FinancialEvent
from lunarbit.finance import EpistemicMode, TruthScope
from lunarbit.models import ContractModel

FINANCIAL_CHUNK_POLICY_VERSION = "financial-intelligence-chunks-v1.0.0"


class FinancialChunkLevel(StrEnum):
    EVIDENCE_CELL = "evidence_cell"
    FINANCIAL_EVENT = "financial_event"
    TRANSACTION_BUNDLE = "transaction_bundle"
    ENTITY_HISTORY = "entity_history"
    TEMPORAL_RESEARCH = "temporal_research"


class EvidenceCellInput(ContractModel):
    event_id: UUID
    component_id: UUID
    source_chunk_id: UUID
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_text_private: str = Field(repr=False, min_length=1, max_length=4_000)


class ResearchWindow(ContractModel):
    research_id: str = Field(pattern=r"^research:[a-z0-9][a-z0-9-]*$")
    title_private: str = Field(repr=False, min_length=12, max_length=300)
    period_start: datetime
    period_end: datetime
    event_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def period_and_events_are_valid(self) -> ResearchWindow:
        for value, name in (
            (self.period_start, "period_start"),
            (self.period_end, "period_end"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.period_end <= self.period_start:
            raise ValueError("research period_end must be later than period_start")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("research event IDs must be unique")
        return self


class FinancialIntelligenceChunk(ContractModel):
    chunk_id: UUID
    level: FinancialChunkLevel
    title_private: str = Field(repr=False, min_length=1, max_length=300)
    retrieval_text_private: str = Field(repr=False, min_length=1, max_length=8_000)
    event_ids: tuple[UUID, ...] = Field(min_length=1)
    component_ids: tuple[UUID, ...] = Field(min_length=1)
    source_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    source_hashes: tuple[str, ...] = Field(min_length=1)
    order_ids: tuple[UUID, ...]
    entity_ids: tuple[str, ...]
    child_chunk_ids: tuple[UUID, ...]
    period_start: datetime
    period_end: datetime
    currencies: tuple[str, ...] = Field(min_length=1)
    observed_amounts: tuple[Decimal, ...] = Field(min_length=1)
    epistemic_modes: tuple[EpistemicMode, ...] = Field(min_length=1)
    truth_scopes: tuple[TruthScope, ...] = Field(min_length=1)
    policy_version: str = FINANCIAL_CHUNK_POLICY_VERSION

    @model_validator(mode="after")
    def shape_and_time_are_valid(self) -> FinancialIntelligenceChunk:
        if self.period_start.tzinfo is None or self.period_start.utcoffset() is None:
            raise ValueError("chunk period_start must be timezone-aware")
        if self.period_end.tzinfo is None or self.period_end.utcoffset() is None:
            raise ValueError("chunk period_end must be timezone-aware")
        if self.period_end < self.period_start:
            raise ValueError("chunk period_end cannot precede period_start")
        if len(self.source_chunk_ids) != len(self.source_hashes):
            raise ValueError("every source chunk must retain one source hash")
        repeated = (
            self.event_ids,
            self.component_ids,
            self.source_chunk_ids,
            self.order_ids,
            self.entity_ids,
            self.child_chunk_ids,
            self.currencies,
            self.epistemic_modes,
            self.truth_scopes,
        )
        if any(len(set(values)) != len(values) for values in repeated):
            raise ValueError("financial chunk references must be unique")
        if self.level is FinancialChunkLevel.EVIDENCE_CELL:
            if (
                not (
                    len(self.event_ids)
                    == len(self.component_ids)
                    == len(self.source_chunk_ids)
                    == 1
                )
                or self.child_chunk_ids
            ):
                raise ValueError(
                    "evidence cells require one event, component, source, and no child"
                )
        elif not self.child_chunk_ids:
            raise ValueError("higher-resolution financial chunks require child chunks")
        return self


class FinancialChunkSummary(ContractModel):
    source_events: int = Field(ge=0)
    source_components: int = Field(ge=0)
    source_evidence_cells: int = Field(ge=0)
    compiled_chunks: int = Field(ge=0)
    orphan_chunks: int = Field(ge=0)


class FinancialChunkArchive(ContractModel):
    policy_version: str = FINANCIAL_CHUNK_POLICY_VERSION
    chunks: tuple[FinancialIntelligenceChunk, ...]
    summary: FinancialChunkSummary
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def graph_is_closed(self) -> FinancialChunkArchive:
        ids = tuple(chunk.chunk_id for chunk in self.chunks)
        if len(set(ids)) != len(ids):
            raise ValueError("financial chunk IDs must be unique")
        known = set(ids)
        if any(not set(chunk.child_chunk_ids) <= known for chunk in self.chunks):
            raise ValueError("financial chunk references an unknown child")
        return self


def _chunk_id(level: FinancialChunkLevel, identity: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lunarbit-financial-chunk-v1:{level.value}:{identity}")


def _sorted_uuids(values: set[UUID] | tuple[UUID, ...]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _aggregate_chunk(
    *,
    level: FinancialChunkLevel,
    identity: str,
    title: str,
    retrieval_text: str,
    events: tuple[FinancialEvent, ...],
    children: tuple[FinancialIntelligenceChunk, ...],
    entity_ids: tuple[str, ...] = (),
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> FinancialIntelligenceChunk:
    ordered_events = tuple(sorted(events, key=lambda item: (item.occurred_at, str(item.event_id))))
    starts = tuple(event.occurred_at for event in ordered_events)
    source_pairs = sorted(
        {
            (source_id, source_hash)
            for event in ordered_events
            for source_id, source_hash in zip(
                event.source_chunk_ids, event.source_hashes, strict=True
            )
        },
        key=lambda pair: str(pair[0]),
    )
    return FinancialIntelligenceChunk(
        chunk_id=_chunk_id(level, identity),
        level=level,
        title_private=title,
        retrieval_text_private=retrieval_text,
        event_ids=tuple(event.event_id for event in ordered_events),
        component_ids=_sorted_uuids(
            tuple(component for event in ordered_events for component in event.component_ids)
        ),
        source_chunk_ids=tuple(pair[0] for pair in source_pairs),
        source_hashes=tuple(pair[1] for pair in source_pairs),
        order_ids=_sorted_uuids(
            tuple(order_id for event in ordered_events for order_id in event.order_ids)
        ),
        entity_ids=tuple(sorted(set(entity_ids))),
        child_chunk_ids=_sorted_uuids(tuple(child.chunk_id for child in children)),
        period_start=period_start or min(starts),
        period_end=period_end or max(starts),
        currencies=tuple(sorted({event.currency for event in ordered_events})),
        observed_amounts=tuple(event.amount for event in ordered_events),
        epistemic_modes=tuple(sorted({event.epistemic_mode for event in ordered_events})),
        truth_scopes=tuple(sorted({event.truth_scope for event in ordered_events})),
    )


def _validate_inputs(
    events: tuple[FinancialEvent, ...],
    cells: tuple[EvidenceCellInput, ...],
) -> dict[UUID, FinancialEvent]:
    by_id = {event.event_id: event for event in events}
    if len(by_id) != len(events):
        raise ValueError("financial events must be unique")
    expected = Counter(
        (event.event_id, component_id) for event in events for component_id in event.component_ids
    )
    observed = Counter((cell.event_id, cell.component_id) for cell in cells)
    if expected != observed or any(count != 1 for count in observed.values()):
        raise ValueError(
            "every financial event component must have exactly once evidence-cell coverage"
        )
    for cell in cells:
        event = by_id.get(cell.event_id)
        if event is None:
            raise ValueError("evidence cell references an unknown financial event")
        evidence = dict(zip(event.source_chunk_ids, event.source_hashes, strict=True))
        if evidence.get(cell.source_chunk_id) != cell.source_hash:
            raise ValueError("evidence cell provenance differs from its financial event")
    return by_id


def compile_financial_intelligence_chunks(
    events: tuple[FinancialEvent, ...],
    evidence_cells: tuple[EvidenceCellInput, ...],
    *,
    entity_event_ids: Mapping[str, tuple[UUID, ...]] | None = None,
    research_windows: tuple[ResearchWindow, ...] = (),
) -> FinancialChunkArchive:
    by_id = _validate_inputs(events, evidence_cells)
    if not events:
        raise ValueError("financial chunk compilation requires at least one event")
    chunks: list[FinancialIntelligenceChunk] = []
    cells_by_event: dict[UUID, list[FinancialIntelligenceChunk]] = defaultdict(list)
    for cell in sorted(
        evidence_cells,
        key=lambda item: (str(item.event_id), str(item.component_id), str(item.source_chunk_id)),
    ):
        event = by_id[cell.event_id]
        chunk = FinancialIntelligenceChunk(
            chunk_id=_chunk_id(
                FinancialChunkLevel.EVIDENCE_CELL,
                f"{cell.event_id}:{cell.component_id}:{cell.source_chunk_id}",
            ),
            level=FinancialChunkLevel.EVIDENCE_CELL,
            title_private=f"Evidence cell for {event.event_type.value}",
            retrieval_text_private=cell.source_text_private,
            event_ids=(event.event_id,),
            component_ids=(cell.component_id,),
            source_chunk_ids=(cell.source_chunk_id,),
            source_hashes=(cell.source_hash,),
            order_ids=_sorted_uuids(event.order_ids),
            entity_ids=(),
            child_chunk_ids=(),
            period_start=event.occurred_at,
            period_end=event.occurred_at,
            currencies=(event.currency,),
            observed_amounts=(event.amount,),
            epistemic_modes=(event.epistemic_mode,),
            truth_scopes=(event.truth_scope,),
        )
        cells_by_event[event.event_id].append(chunk)
        chunks.append(chunk)
    event_chunks: dict[UUID, FinancialIntelligenceChunk] = {}
    for event in sorted(events, key=lambda item: (item.occurred_at, str(item.event_id))):
        chunk = _aggregate_chunk(
            level=FinancialChunkLevel.FINANCIAL_EVENT,
            identity=str(event.event_id),
            title=f"Financial event: {event.event_type.value}",
            retrieval_text=(
                f"{event.event_type.value} {event.currency} {event.amount} "
                f"at {event.occurred_at.isoformat()} within {event.scope.value}."
            ),
            events=(event,),
            children=tuple(cells_by_event[event.event_id]),
        )
        event_chunks[event.event_id] = chunk
        chunks.append(chunk)
    order_events: dict[UUID, list[FinancialEvent]] = defaultdict(list)
    for event in events:
        for order_id in event.order_ids:
            order_events[order_id].append(event)
    for order_id, order_values in sorted(order_events.items(), key=lambda item: str(item[0])):
        ordered = tuple(order_values)
        chunks.append(
            _aggregate_chunk(
                level=FinancialChunkLevel.TRANSACTION_BUNDLE,
                identity=str(order_id),
                title="Transaction bundle financial history",
                retrieval_text=(
                    "Source-backed transaction events: "
                    + "; ".join(
                        f"{event.event_type.value} {event.currency} {event.amount}"
                        for event in sorted(
                            ordered, key=lambda item: (item.occurred_at, str(item.event_id))
                        )
                    )
                ),
                events=ordered,
                children=tuple(event_chunks[event.event_id] for event in ordered),
            )
        )
    for entity_id, event_ids in sorted((entity_event_ids or {}).items()):
        if not entity_id.strip() or not event_ids or len(set(event_ids)) != len(event_ids):
            raise ValueError("entity history requires one entity and unique events")
        try:
            entity_values = tuple(by_id[event_id] for event_id in event_ids)
        except KeyError as error:
            raise ValueError("entity history references an unknown financial event") from error
        chunks.append(
            _aggregate_chunk(
                level=FinancialChunkLevel.ENTITY_HISTORY,
                identity=entity_id,
                title="Entity financial history",
                retrieval_text=(
                    f"Chronological financial event history for {entity_id}: "
                    + "; ".join(
                        f"{event.occurred_at.date()} {event.event_type.value} "
                        f"{event.currency} {event.amount}"
                        for event in sorted(entity_values, key=lambda item: item.occurred_at)
                    )
                ),
                events=entity_values,
                children=tuple(event_chunks[event.event_id] for event in entity_values),
                entity_ids=(entity_id,),
            )
        )
    for window in sorted(research_windows, key=lambda item: item.research_id):
        try:
            research_values = tuple(by_id[event_id] for event_id in window.event_ids)
        except KeyError as error:
            raise ValueError("research window references an unknown financial event") from error
        if any(
            not window.period_start <= event.occurred_at < window.period_end
            for event in research_values
        ):
            raise ValueError("research window does not contain every referenced event")
        chunks.append(
            _aggregate_chunk(
                level=FinancialChunkLevel.TEMPORAL_RESEARCH,
                identity=window.research_id,
                title=window.title_private,
                retrieval_text=(
                    f"Temporal research evidence from {window.period_start.isoformat()} to "
                    f"{window.period_end.isoformat()}: "
                    + "; ".join(
                        f"{event.event_type.value} {event.currency} {event.amount}"
                        for event in sorted(research_values, key=lambda item: item.occurred_at)
                    )
                ),
                events=research_values,
                children=tuple(event_chunks[event.event_id] for event in research_values),
                period_start=window.period_start,
                period_end=window.period_end,
            )
        )
    ordered_chunks = tuple(sorted(chunks, key=lambda item: (item.level.value, str(item.chunk_id))))
    content = "\n".join(chunk.model_dump_json() for chunk in ordered_chunks)
    archive_hash = sha256(content.encode()).hexdigest()
    return FinancialChunkArchive(
        chunks=ordered_chunks,
        summary=FinancialChunkSummary(
            source_events=len(events),
            source_components=sum(len(event.component_ids) for event in events),
            source_evidence_cells=len(evidence_cells),
            compiled_chunks=len(ordered_chunks),
            orphan_chunks=0,
        ),
        archive_sha256=archive_hash,
    )
