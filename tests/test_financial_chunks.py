from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.economic import FinancialEvent, FinancialEventType, financial_event_id
from lunarbit.finance import EpistemicMode, FinancialScope, TruthScope
from lunarbit.financial_chunks import (
    EvidenceCellInput,
    FinancialChunkLevel,
    ResearchWindow,
    compile_financial_intelligence_chunks,
)


def _time(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def _event(suffix: int, amount: str) -> FinancialEvent:
    component_id = UUID(f"10000000-0000-0000-0000-{suffix:012d}")
    occurred_at = _time(suffix)
    return FinancialEvent(
        event_id=financial_event_id(
            component_ids=(component_id,),
            event_type=FinancialEventType.CHARGE_ASSESSED,
            occurred_at=occurred_at,
        ),
        event_type=FinancialEventType.CHARGE_ASSESSED,
        component_ids=(component_id,),
        order_ids=(UUID("20000000-0000-0000-0000-000000000001"),),
        amount=Decimal(amount),
        currency="INR",
        scope=FinancialScope.ORDER,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        occurred_at=occurred_at,
        observed_at=_time(suffix + 1),
        valid_from=occurred_at,
        valid_to=None,
        source_chunk_ids=(UUID(f"30000000-0000-0000-0000-{suffix:012d}"),),
        source_hashes=(f"{suffix:x}" * 64,),
    )


def test_compiler_builds_all_five_linked_financial_resolutions() -> None:
    events = (_event(1, "10.00"), _event(2, "12.00"))
    cells = tuple(
        EvidenceCellInput(
            event_id=event.event_id,
            component_id=event.component_ids[0],
            source_chunk_id=event.source_chunk_ids[0],
            source_hash=event.source_hashes[0],
            source_text_private=f"Observed charge {event.amount}",
        )
        for event in events
    )

    archive = compile_financial_intelligence_chunks(
        events,
        cells,
        entity_event_ids={"merchant:sample": tuple(event.event_id for event in events)},
        research_windows=(
            ResearchWindow(
                research_id="research:fee-history",
                title_private="Fee history during the reviewed period",
                period_start=_time(1),
                period_end=_time(4),
                event_ids=tuple(event.event_id for event in events),
            ),
        ),
    )

    counts = {level: 0 for level in FinancialChunkLevel}
    for chunk in archive.chunks:
        counts[chunk.level] += 1
    assert counts == {
        FinancialChunkLevel.EVIDENCE_CELL: 2,
        FinancialChunkLevel.FINANCIAL_EVENT: 2,
        FinancialChunkLevel.TRANSACTION_BUNDLE: 1,
        FinancialChunkLevel.ENTITY_HISTORY: 1,
        FinancialChunkLevel.TEMPORAL_RESEARCH: 1,
    }
    assert archive.summary.source_components == 2
    assert archive.summary.orphan_chunks == 0


def test_higher_resolution_chunks_reference_existing_lower_resolution_children() -> None:
    event = _event(1, "10.00")
    archive = compile_financial_intelligence_chunks(
        (event,),
        (
            EvidenceCellInput(
                event_id=event.event_id,
                component_id=event.component_ids[0],
                source_chunk_id=event.source_chunk_ids[0],
                source_hash=event.source_hashes[0],
                source_text_private="Observed charge 10.00",
            ),
        ),
    )
    known = {chunk.chunk_id for chunk in archive.chunks}

    assert all(set(chunk.child_chunk_ids) <= known for chunk in archive.chunks)
    event_chunk = next(
        chunk for chunk in archive.chunks if chunk.level is FinancialChunkLevel.FINANCIAL_EVENT
    )
    assert len(event_chunk.child_chunk_ids) == 1


def test_compiler_rejects_duplicate_or_missing_component_coverage() -> None:
    event = _event(1, "10.00")
    cell = EvidenceCellInput(
        event_id=event.event_id,
        component_id=event.component_ids[0],
        source_chunk_id=event.source_chunk_ids[0],
        source_hash=event.source_hashes[0],
        source_text_private="Observed charge 10.00",
    )

    with pytest.raises(ValueError, match="exactly once"):
        compile_financial_intelligence_chunks((event,), (cell, cell))
    with pytest.raises(ValueError, match="exactly once"):
        compile_financial_intelligence_chunks((event,), ())


def test_compiler_is_byte_stable_for_reordered_inputs() -> None:
    first, second = _event(1, "10.00"), _event(2, "12.00")
    cells = tuple(
        EvidenceCellInput(
            event_id=event.event_id,
            component_id=event.component_ids[0],
            source_chunk_id=event.source_chunk_ids[0],
            source_hash=event.source_hashes[0],
            source_text_private=f"Observed charge {event.amount}",
        )
        for event in (first, second)
    )

    left = compile_financial_intelligence_chunks((first, second), cells)
    right = compile_financial_intelligence_chunks((second, first), tuple(reversed(cells)))

    assert left.model_dump_json() == right.model_dump_json()
