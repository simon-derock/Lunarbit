from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from lunarbit.economic import FinancialEvent, FinancialEventType, financial_event_id
from lunarbit.finance import FinancialComponentType, MoneyComponent
from lunarbit.financial_chunks import (
    EvidenceCellInput,
    FinancialChunkArchive,
    ResearchWindow,
    compile_financial_intelligence_chunks,
)
from lunarbit.graph import CanonicalGraph, NodeLabel, RelationshipType
from lunarbit.models import ContractModel, SourceDocument, SourceMessage
from lunarbit.temporal_graph import extend_graph_with_financial_events

ECONOMIC_PIPELINE_VERSION = "economic-corpus-v1.0.0"


class ObservationClockPolicy(StrEnum):
    LATEST_REFERENCED_SOURCE = "latest_referenced_source"


class EconomicPipelineSummary(ContractModel):
    source_messages: int = Field(ge=0)
    source_documents: int = Field(ge=0)
    source_components: int = Field(ge=1)
    financial_events: int = Field(ge=1)
    evidence_cells: int = Field(ge=1)
    entity_histories: int = Field(ge=0)
    research_windows: int = Field(ge=1)
    financial_chunks: int = Field(ge=1)
    graph_event_nodes: int = Field(ge=1)
    graph_event_relationships: int = Field(ge=1)


class EconomicIntelligenceCorpus(ContractModel):
    pipeline_version: str = ECONOMIC_PIPELINE_VERSION
    observation_clock_policy: ObservationClockPolicy
    observed_at: datetime
    events: tuple[FinancialEvent, ...]
    evidence_cells: tuple[EvidenceCellInput, ...]
    chunk_archive: FinancialChunkArchive
    graph: CanonicalGraph
    summary: EconomicPipelineSummary

    @model_validator(mode="after")
    def coverage_is_exact(self) -> EconomicIntelligenceCorpus:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("corpus observed_at must be timezone-aware")
        if self.summary.financial_events != len(self.events):
            raise ValueError("financial event summary must match the corpus")
        if self.summary.evidence_cells != len(self.evidence_cells):
            raise ValueError("evidence-cell summary must match the corpus")
        component_ids = tuple(
            component_id for event in self.events for component_id in event.component_ids
        )
        if len(component_ids) != self.summary.source_components:
            raise ValueError("every source component must compile into one event")
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("a source component cannot occur in multiple events")
        return self


_PURCHASE_TYPES = {
    FinancialComponentType.ITEM_GROSS,
    FinancialComponentType.ITEM_NET,
    FinancialComponentType.SUBTOTAL,
    FinancialComponentType.INVOICE_TOTAL,
    FinancialComponentType.CUSTOMER_TOTAL,
}
_CHARGE_TYPES = {
    FinancialComponentType.PACKING_CHARGE,
    FinancialComponentType.HANDLING_FEE,
    FinancialComponentType.DELIVERY_CHARGE,
    FinancialComponentType.PLATFORM_FEE,
    FinancialComponentType.OTHER_CHARGE,
}
_DISCOUNT_TYPES = {
    FinancialComponentType.ITEM_DISCOUNT,
    FinancialComponentType.COUPON_DISCOUNT,
}
_TAX_TYPES = {
    FinancialComponentType.CGST,
    FinancialComponentType.SGST,
    FinancialComponentType.IGST,
    FinancialComponentType.CESS,
    FinancialComponentType.TAX,
}


def _event_type(component_type: FinancialComponentType) -> FinancialEventType:
    if component_type in _PURCHASE_TYPES:
        return FinancialEventType.PURCHASE_ASSERTED
    if component_type in _CHARGE_TYPES:
        return FinancialEventType.CHARGE_ASSESSED
    if component_type in _DISCOUNT_TYPES:
        return FinancialEventType.DISCOUNT_APPLIED
    if component_type is FinancialComponentType.MEMBERSHIP_BENEFIT:
        return FinancialEventType.MEMBERSHIP_BENEFIT_REALIZED
    if component_type in _TAX_TYPES:
        return FinancialEventType.TAX_ASSESSED
    if component_type is FinancialComponentType.PAYMENT_ASSERTION:
        return FinancialEventType.PAYMENT_ASSERTED
    if component_type is FinancialComponentType.REFUND:
        return FinancialEventType.REFUND_ASSERTED
    return FinancialEventType.RECONCILIATION_RESIDUAL


def _source_occurrence(
    component: MoneyComponent,
    *,
    messages: dict[str, SourceMessage],
    documents: dict[str, SourceDocument],
) -> datetime:
    message_id = component.source_id
    if component.source_id.startswith("doc_"):
        try:
            message_id = documents[component.source_id].message_id
        except KeyError as error:
            raise ValueError("money component references an unknown source document") from error
    try:
        occurred_at = messages[message_id].occurred_at
    except KeyError as error:
        raise ValueError("money component references an unknown source message") from error
    if occurred_at is None:
        raise ValueError("referenced source message requires occurred_at")
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("referenced source message occurred_at must be timezone-aware")
    return occurred_at


def _evidence_text(properties: dict[str, object]) -> str:
    summary = properties.get("semantic_summary_private")
    normalized = properties.get("normalized_text_private")
    parts = tuple(
        value.strip() for value in (summary, normalized) if isinstance(value, str) and value.strip()
    )
    unique_parts = tuple(dict.fromkeys(parts))
    if not unique_parts:
        raise ValueError("financial evidence chunk has no private retrieval text")
    if len(unique_parts) == 1:
        return unique_parts[0][:4_000]
    return f"{unique_parts[0]}\n\nSource evidence:\n{unique_parts[1]}"[:4_000]


def _entity_event_map(
    graph: CanonicalGraph,
    events: tuple[FinancialEvent, ...],
) -> dict[str, tuple[UUID, ...]]:
    outlet_to_merchants: dict[str, set[str]] = defaultdict(set)
    order_to_outlets: dict[str, set[str]] = defaultdict(set)
    for relationship in graph.relationships:
        if relationship.relationship_type is RelationshipType.OUTLET_OF:
            outlet_to_merchants[relationship.source_node_id].add(relationship.target_node_id)
        elif relationship.relationship_type is RelationshipType.ORDERED_FROM:
            order_to_outlets[relationship.source_node_id].add(relationship.target_node_id)
    result: dict[str, set[UUID]] = defaultdict(set)
    for event in events:
        for order_id in event.order_ids:
            for outlet_id in order_to_outlets.get(f"order:{order_id}", set()):
                result[outlet_id].add(event.event_id)
                for merchant_id in outlet_to_merchants.get(outlet_id, set()):
                    result[merchant_id].add(event.event_id)
    return {
        entity_id: tuple(sorted(event_ids, key=str))
        for entity_id, event_ids in sorted(result.items())
    }


def _research_windows(events: tuple[FinancialEvent, ...]) -> tuple[ResearchWindow, ...]:
    by_year: dict[int, list[UUID]] = defaultdict(list)
    for event in events:
        year = event.occurred_at.astimezone(UTC).year
        by_year[year].append(event.event_id)
    return tuple(
        ResearchWindow(
            research_id=f"research:annual-{year}",
            title_private=f"Annual financial intelligence evidence for {year}",
            period_start=datetime(year, 1, 1, tzinfo=UTC),
            period_end=datetime(year + 1, 1, 1, tzinfo=UTC),
            event_ids=tuple(sorted(event_ids, key=str)),
        )
        for year, event_ids in sorted(by_year.items())
    )


def compile_economic_intelligence(
    messages: tuple[SourceMessage, ...],
    documents: tuple[SourceDocument, ...],
    components: tuple[MoneyComponent, ...],
    graph: CanonicalGraph,
) -> EconomicIntelligenceCorpus:
    if not components:
        raise ValueError("economic intelligence compilation requires money components")
    messages_by_id = {message.message_id: message for message in messages}
    documents_by_id = {document.document_id: document for document in documents}
    if len(messages_by_id) != len(messages):
        raise ValueError("source message IDs must be unique")
    if len(documents_by_id) != len(documents):
        raise ValueError("source document IDs must be unique")
    component_ids = tuple(component.component_id for component in components)
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("money component IDs must be unique")

    graph_nodes = {node.node_id: node for node in graph.nodes}
    occurrences = {
        component.component_id: _source_occurrence(
            component,
            messages=messages_by_id,
            documents=documents_by_id,
        )
        for component in components
    }
    observed_at = max(occurrences.values())
    events: list[FinancialEvent] = []
    cells: list[EvidenceCellInput] = []
    for component in sorted(components, key=lambda value: str(value.component_id)):
        chunk_node_id = f"chunk:{component.source_chunk_id}"
        node = graph_nodes.get(chunk_node_id)
        if node is None or NodeLabel.EVIDENCE_CHUNK not in node.labels:
            raise ValueError("money component references an unknown evidence chunk")
        source_hash = node.properties.get("source_hash")
        if not isinstance(source_hash, str):
            raise ValueError("financial evidence chunk requires a source hash")
        event_type = _event_type(component.component_type)
        occurred_at = occurrences[component.component_id]
        event = FinancialEvent(
            event_id=financial_event_id(
                component_ids=(component.component_id,),
                event_type=event_type,
                occurred_at=occurred_at,
            ),
            event_type=event_type,
            component_ids=(component.component_id,),
            order_ids=tuple(sorted(set(component.order_ids), key=str)),
            amount=component.amount,
            currency=component.currency,
            scope=component.scope,
            epistemic_mode=component.epistemic_mode,
            truth_scope=component.truth_scope,
            occurred_at=occurred_at,
            observed_at=observed_at,
            valid_from=occurred_at,
            valid_to=None,
            source_chunk_ids=(component.source_chunk_id,),
            source_hashes=(source_hash,),
        )
        events.append(event)
        cells.append(
            EvidenceCellInput(
                event_id=event.event_id,
                component_id=component.component_id,
                source_chunk_id=component.source_chunk_id,
                source_hash=source_hash,
                source_text_private=_evidence_text(dict(node.properties)),
            )
        )
    event_values = tuple(events)
    cell_values = tuple(cells)
    entity_events = _entity_event_map(graph, event_values)
    windows = _research_windows(event_values)
    chunks = compile_financial_intelligence_chunks(
        event_values,
        cell_values,
        entity_event_ids=entity_events,
        research_windows=windows,
    )
    extended_graph = extend_graph_with_financial_events(graph, event_values)
    return EconomicIntelligenceCorpus(
        observation_clock_policy=ObservationClockPolicy.LATEST_REFERENCED_SOURCE,
        observed_at=observed_at,
        events=event_values,
        evidence_cells=cell_values,
        chunk_archive=chunks,
        graph=extended_graph,
        summary=EconomicPipelineSummary(
            source_messages=len(messages),
            source_documents=len(documents),
            source_components=len(components),
            financial_events=len(event_values),
            evidence_cells=len(cell_values),
            entity_histories=len(entity_events),
            research_windows=len(windows),
            financial_chunks=len(chunks.chunks),
            graph_event_nodes=len(extended_graph.nodes) - len(graph.nodes),
            graph_event_relationships=(
                len(extended_graph.relationships) - len(graph.relationships)
            ),
        ),
    )
