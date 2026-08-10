from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from lunarbit.agentic import (
    AgenticBatchResult,
    AgenticConflictFlag,
    AgenticEntityCandidate,
    AgenticFactCandidate,
    AgenticRegionProposal,
)
from lunarbit.models import ContractModel, EvidenceChunk, ValidationStatus

_TEMPORARY_SOURCE_ALIAS = re.compile(r"\bc\d{4}\b")
_NUMBER_TOKEN = re.compile(r"(?<![A-Za-z])\d+(?:[,.]\d+)*")


class AgenticQualityIssue(StrEnum):
    TEMPORARY_SOURCE_ALIAS = "temporary_source_alias"
    MISSING_FACT_CANDIDATE = "missing_fact_candidate"
    MISSING_ENTITY_CANDIDATE = "missing_entity_candidate"
    UNSUPPORTED_FACT_CANDIDATE = "unsupported_fact_candidate"
    UNSUPPORTED_ENTITY_CANDIDATE = "unsupported_entity_candidate"
    DUPLICATE_RETRIEVAL_TEXT = "duplicate_retrieval_text"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    SHORT_STRUCTURALLY_SPARSE = "short_structurally_sparse"
    UNCITED_AMOUNT_CONFLICT = "uncited_amount_conflict"


class AgenticRegionOrigin(StrEnum):
    REPAIRED_BASELINE = "repaired_baseline"
    SEMANTIC_RETRY = "semantic_retry"


class AgenticRegionRecord(ContractModel):
    region_id: UUID
    origin: AgenticRegionOrigin
    source_batch_id: UUID
    model: str
    response_sha256: str
    quality_issues: tuple[AgenticQualityIssue, ...]
    region: AgenticRegionProposal


@dataclass(frozen=True, slots=True)
class AgenticRegionQualityAudit:
    issues: tuple[AgenticQualityIssue, ...]
    missing_fact_candidates: int
    missing_entity_candidates: int
    unsupported_fact_candidates: int
    unsupported_entity_candidates: int
    temporary_source_aliases: int


@dataclass(frozen=True, slots=True)
class AgenticResultRepairReport:
    changed_regions: int
    restored_fact_candidates: int
    restored_entity_candidates: int
    removed_unsupported_fact_candidates: int
    removed_unsupported_entity_candidates: int
    removed_temporary_aliases: int
    recomposed_embedding_texts: int
    enriched_sparse_regions: int


def agentic_region_id(region: AgenticRegionProposal) -> UUID:
    source_ids = ",".join(sorted(str(value) for value in region.source_chunk_ids))
    identity = ":".join(
        (
            "lunarbit-agentic-region-v1",
            region.bundle_id,
            source_ids,
            region.chunk_type.value,
            region.semantic_role.value,
            region.financial_role.value,
        )
    )
    return uuid5(NAMESPACE_URL, identity)


def _region_sources(
    region: AgenticRegionProposal,
    chunks_by_id: Mapping[str, EvidenceChunk],
) -> tuple[EvidenceChunk, ...]:
    sources: list[EvidenceChunk] = []
    for chunk_id in region.source_chunk_ids:
        source = chunks_by_id.get(str(chunk_id))
        if source is None:
            raise ValueError("agentic region references an unknown source chunk")
        sources.append(source)
    return tuple(sources)


def _fact_key(candidate: AgenticFactCandidate) -> tuple[object, ...]:
    return (
        candidate.fact_type,
        candidate.raw_value_private,
        candidate.normalized_value_private,
        candidate.source_chunk_id,
        candidate.source_span_start,
        candidate.source_span_end,
    )


def _source_fact_candidates(sources: Sequence[EvidenceChunk]) -> tuple[AgenticFactCandidate, ...]:
    return tuple(
        AgenticFactCandidate(
            fact_type=assertion.fact_type,
            raw_value_private=assertion.raw_value_private,
            normalized_value_private=assertion.normalized_value_private,
            source_chunk_id=source.chunk_id,
            source_span_start=assertion.source_span_start,
            source_span_end=assertion.source_span_end,
        )
        for source in sources
        for assertion in source.candidate_assertions
    )


def _entity_key(candidate: AgenticEntityCandidate) -> tuple[object, ...]:
    return candidate.entity_type, candidate.raw_value_private, candidate.source_chunk_id


def _source_entity_candidates(
    sources: Sequence[EvidenceChunk],
) -> tuple[AgenticEntityCandidate, ...]:
    candidates = (
        AgenticEntityCandidate(
            entity_type=mention.entity_type,
            raw_value_private=mention.raw_value_private,
            source_chunk_id=source.chunk_id,
        )
        for source in sources
        for mention in source.entity_mentions
    )
    return tuple(dict.fromkeys(candidates))


def _temporary_aliases(text: str, raw_source_text: str) -> tuple[str, ...]:
    return tuple(
        alias for alias in _TEMPORARY_SOURCE_ALIAS.findall(text) if alias not in raw_source_text
    )


def _is_structurally_sparse(region: AgenticRegionProposal) -> bool:
    return (
        not (
            region.candidate_facts
            or region.entity_candidates
            or region.money_interpretations
            or region.relation_candidates
            or region.conflict_flags
            or region.uncertainty_notes_private
        )
        and len(region.semantic_summary_private.split()) < 8
    )


def _has_uncited_amount_conflict(
    region: AgenticRegionProposal,
    raw_source_text: str,
) -> bool:
    if AgenticConflictFlag.AMOUNT_SCOPE_CONFLICT not in region.conflict_flags:
        return False
    source_numbers = {token.replace(",", "") for token in _NUMBER_TOKEN.findall(raw_source_text)}
    note_numbers = {
        token.replace(",", "")
        for token in _NUMBER_TOKEN.findall(" ".join(region.uncertainty_notes_private))
    }
    return bool(note_numbers - source_numbers)


def audit_agentic_region(
    region: AgenticRegionProposal,
    chunks_by_id: Mapping[str, EvidenceChunk],
) -> AgenticRegionQualityAudit:
    sources = _region_sources(region, chunks_by_id)
    raw_source_text = "\n".join(source.raw_text_private for source in sources)
    retrieval_texts = (
        region.region_title_private,
        region.semantic_summary_private,
        region.embedding_text_private,
    )
    aliases = tuple(
        alias for text in retrieval_texts for alias in _temporary_aliases(text, raw_source_text)
    )
    actual_facts = {_fact_key(candidate) for candidate in region.candidate_facts}
    expected_facts = {_fact_key(candidate) for candidate in _source_fact_candidates(sources)}
    actual_entities = {_entity_key(candidate) for candidate in region.entity_candidates}
    expected_entities = {_entity_key(candidate) for candidate in _source_entity_candidates(sources)}
    missing_facts = expected_facts - actual_facts
    missing_entities = expected_entities - actual_entities
    unsupported_facts = actual_facts - expected_facts
    unsupported_entities = actual_entities - expected_entities

    issues: list[AgenticQualityIssue] = []
    if aliases:
        issues.append(AgenticQualityIssue.TEMPORARY_SOURCE_ALIAS)
    if missing_facts:
        issues.append(AgenticQualityIssue.MISSING_FACT_CANDIDATE)
    if missing_entities:
        issues.append(AgenticQualityIssue.MISSING_ENTITY_CANDIDATE)
    if unsupported_facts:
        issues.append(AgenticQualityIssue.UNSUPPORTED_FACT_CANDIDATE)
    if unsupported_entities:
        issues.append(AgenticQualityIssue.UNSUPPORTED_ENTITY_CANDIDATE)
    if region.semantic_summary_private.strip() == region.embedding_text_private.strip():
        issues.append(AgenticQualityIssue.DUPLICATE_RETRIEVAL_TEXT)
    if region.region_title_private.startswith("Preserved ") or any(
        "Deterministic fallback" in interpretation.interpretation_private
        for interpretation in region.money_interpretations
    ):
        issues.append(AgenticQualityIssue.DETERMINISTIC_FALLBACK)
    if _is_structurally_sparse(region):
        issues.append(AgenticQualityIssue.SHORT_STRUCTURALLY_SPARSE)
    if _has_uncited_amount_conflict(region, raw_source_text):
        issues.append(AgenticQualityIssue.UNCITED_AMOUNT_CONFLICT)
    return AgenticRegionQualityAudit(
        issues=tuple(issues),
        missing_fact_candidates=len(missing_facts),
        missing_entity_candidates=len(missing_entities),
        unsupported_fact_candidates=len(unsupported_facts),
        unsupported_entity_candidates=len(unsupported_entities),
        temporary_source_aliases=len(aliases),
    )


def _clean_temporary_aliases(text: str, raw_source_text: str) -> tuple[str, int]:
    aliases = _temporary_aliases(text, raw_source_text)
    cleaned = text
    for alias in aliases:
        escaped = re.escape(alias)
        cleaned = re.sub(
            rf"\s*\(?\b(?:source(?:\s+chunk)?|evidence\s+from(?:\s+chunk)?|"
            rf"from(?:\s+chunk)?)\s*[:#]?\s*{escaped}\)?[.,;:]?",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(rf"\b{escaped}\b", "", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([:;,])\s*([.;,])", r"\2", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:")
    return (cleaned or text), len(aliases)


def _retrieval_embedding(region: AgenticRegionProposal) -> str:
    facets = ", ".join(query.value.replace("_", " ") for query in region.query_families)
    financial = (
        ""
        if region.financial_role.value == "none"
        else f" Financial role: {region.financial_role.value}."
    )
    value = (
        f"{region.region_title_private}. {region.semantic_summary_private} "
        f"Evidence type: {region.chunk_type.value.replace('_', ' ').lower()}."
        f"{financial} Retrieval intents: {facets}."
    )
    return value[:1_600].strip()


def _enrich_sparse_summary(
    region: AgenticRegionProposal,
    sources: Sequence[EvidenceChunk],
) -> str:
    source_summaries = tuple(
        dict.fromkeys(source.semantic_summary_private.strip() for source in sources)
    )
    evidence = " ".join(value for value in source_summaries if value)
    enriched = f"{region.region_title_private}. {evidence}".strip()
    return enriched[:1_200] if len(enriched.split()) >= 8 else region.semantic_summary_private


def repair_agentic_result(
    result: AgenticBatchResult,
    chunks_by_id: Mapping[str, EvidenceChunk],
) -> tuple[AgenticBatchResult, AgenticResultRepairReport]:
    repaired_regions: list[AgenticRegionProposal] = []
    changed_regions = 0
    restored_facts = 0
    restored_entities = 0
    removed_unsupported_facts = 0
    removed_unsupported_entities = 0
    removed_aliases = 0
    recomposed_embeddings = 0
    enriched_sparse_regions = 0

    for region in result.regions:
        sources = _region_sources(region, chunks_by_id)
        raw_source_text = "\n".join(source.raw_text_private for source in sources)
        values = region.model_dump(mode="python")

        for field_name in (
            "region_title_private",
            "semantic_summary_private",
            "embedding_text_private",
        ):
            cleaned, count = _clean_temporary_aliases(str(values[field_name]), raw_source_text)
            values[field_name] = cleaned
            removed_aliases += count

        expected_fact_candidates = _source_fact_candidates(sources)
        expected_fact_keys = {_fact_key(candidate) for candidate in expected_fact_candidates}
        supported_facts = tuple(
            dict.fromkeys(
                candidate
                for candidate in region.candidate_facts
                if _fact_key(candidate) in expected_fact_keys
            )
        )
        removed_unsupported_facts += len(region.candidate_facts) - len(supported_facts)
        actual_fact_keys = {_fact_key(candidate) for candidate in supported_facts}
        missing_facts = tuple(
            candidate
            for candidate in expected_fact_candidates
            if _fact_key(candidate) not in actual_fact_keys
        )
        values["candidate_facts"] = (*supported_facts, *missing_facts)
        restored_facts += len(missing_facts)

        expected_entity_candidates = _source_entity_candidates(sources)
        expected_entity_keys = {_entity_key(candidate) for candidate in expected_entity_candidates}
        supported_entities = tuple(
            dict.fromkeys(
                candidate
                for candidate in region.entity_candidates
                if _entity_key(candidate) in expected_entity_keys
            )
        )
        removed_unsupported_entities += len(region.entity_candidates) - len(supported_entities)
        actual_entity_keys = {_entity_key(candidate) for candidate in supported_entities}
        missing_entities = tuple(
            candidate
            for candidate in expected_entity_candidates
            if _entity_key(candidate) not in actual_entity_keys
        )
        values["entity_candidates"] = (*supported_entities, *missing_entities)
        restored_entities += len(missing_entities)

        candidate = AgenticRegionProposal.model_validate(values)
        if _is_structurally_sparse(candidate):
            enriched_summary = _enrich_sparse_summary(candidate, sources)
            if enriched_summary != candidate.semantic_summary_private:
                values["semantic_summary_private"] = enriched_summary
                candidate = AgenticRegionProposal.model_validate(values)
                enriched_sparse_regions += 1

        if candidate.semantic_summary_private.strip() == candidate.embedding_text_private.strip():
            values["embedding_text_private"] = _retrieval_embedding(candidate)
            candidate = AgenticRegionProposal.model_validate(values)
            recomposed_embeddings += 1

        if candidate != region:
            changed_regions += 1
        repaired_regions.append(candidate)

    repaired_result = AgenticBatchResult.model_validate(
        {**result.model_dump(mode="python"), "regions": tuple(repaired_regions)}
    )
    return repaired_result, AgenticResultRepairReport(
        changed_regions=changed_regions,
        restored_fact_candidates=restored_facts,
        restored_entity_candidates=restored_entities,
        removed_unsupported_fact_candidates=removed_unsupported_facts,
        removed_unsupported_entity_candidates=removed_unsupported_entities,
        removed_temporary_aliases=removed_aliases,
        recomposed_embedding_texts=recomposed_embeddings,
        enriched_sparse_regions=enriched_sparse_regions,
    )


_BLOCKING_ARCHIVE_ISSUES = frozenset(
    {
        AgenticQualityIssue.TEMPORARY_SOURCE_ALIAS,
        AgenticQualityIssue.MISSING_FACT_CANDIDATE,
        AgenticQualityIssue.MISSING_ENTITY_CANDIDATE,
        AgenticQualityIssue.UNSUPPORTED_FACT_CANDIDATE,
        AgenticQualityIssue.UNSUPPORTED_ENTITY_CANDIDATE,
    }
)

_QUALITY_ISSUE_WEIGHTS = {
    AgenticQualityIssue.UNCITED_AMOUNT_CONFLICT: 10,
    AgenticQualityIssue.SHORT_STRUCTURALLY_SPARSE: 5,
    AgenticQualityIssue.DETERMINISTIC_FALLBACK: 2,
    AgenticQualityIssue.DUPLICATE_RETRIEVAL_TEXT: 2,
}


def agentic_quality_score(issues: Iterable[AgenticQualityIssue]) -> tuple[int, int]:
    issue_tuple = tuple(issues)
    return (
        sum(_QUALITY_ISSUE_WEIGHTS.get(issue, 100) for issue in issue_tuple),
        len(issue_tuple),
    )


def compile_agentic_region_records(
    baseline_results: Iterable[AgenticBatchResult],
    retry_results: Iterable[AgenticBatchResult],
    *,
    retry_chunk_ids: frozenset[str],
    chunks_by_id: Mapping[str, EvidenceChunk],
) -> tuple[AgenticRegionRecord, ...]:
    baseline = tuple(baseline_results)
    retries = tuple(retry_results)
    if not retry_chunk_ids:
        raise ValueError("retry chunk IDs cannot be empty")
    if any(
        result.validation_status is not ValidationStatus.ACCEPTED
        for result in (*baseline, *retries)
    ):
        raise ValueError("region archives require accepted batch results")

    retry_counts = Counter(
        str(chunk_id)
        for result in retries
        for region in result.regions
        for chunk_id in region.source_chunk_ids
    )
    if set(retry_counts) != retry_chunk_ids or any(count != 1 for count in retry_counts.values()):
        raise ValueError("retry results must cover every selected source chunk exactly once")

    selected: list[tuple[AgenticBatchResult, AgenticRegionProposal, AgenticRegionOrigin]] = []
    for result in baseline:
        for region in result.regions:
            source_ids = {str(value) for value in region.source_chunk_ids}
            overlap = source_ids & retry_chunk_ids
            if overlap and overlap != source_ids:
                raise ValueError("retry selection cannot split an existing baseline region")
            if not overlap:
                selected.append((result, region, AgenticRegionOrigin.REPAIRED_BASELINE))
    selected.extend(
        (result, region, AgenticRegionOrigin.SEMANTIC_RETRY)
        for result in retries
        for region in result.regions
    )

    selected_counts = Counter(
        str(chunk_id) for _, region, _ in selected for chunk_id in region.source_chunk_ids
    )
    if set(selected_counts) != set(chunks_by_id) or any(
        count != 1 for count in selected_counts.values()
    ):
        raise ValueError(
            "compiled regions must cover every deterministic source chunk exactly once"
        )
    expected_money = Counter(
        str(component.component_id)
        for chunk in chunks_by_id.values()
        for component in chunk.candidate_money_components
    )
    selected_money = Counter(
        str(interpretation.source_component_id)
        for _, region, _ in selected
        for interpretation in region.money_interpretations
    )
    if selected_money != expected_money:
        raise ValueError("compiled regions must cover every money component exactly once")

    records: list[AgenticRegionRecord] = []
    for result, region, origin in selected:
        audit = audit_agentic_region(region, chunks_by_id)
        if set(audit.issues) & _BLOCKING_ARCHIVE_ISSUES:
            raise ValueError("compiled region contains a deterministic quality defect")
        if result.response_sha256 is None:
            raise ValueError("accepted result must retain its response hash")
        records.append(
            AgenticRegionRecord(
                region_id=agentic_region_id(region),
                origin=origin,
                source_batch_id=result.batch_id,
                model=result.model,
                response_sha256=result.response_sha256,
                quality_issues=audit.issues,
                region=region,
            )
        )
    records.sort(
        key=lambda record: (
            record.region.bundle_id,
            tuple(str(value) for value in record.region.source_chunk_ids),
            str(record.region_id),
        )
    )
    if len({record.region_id for record in records}) != len(records):
        raise ValueError("compiled region IDs must be unique")
    return tuple(records)


def select_agentic_region_retries(
    baseline_records: Iterable[AgenticRegionRecord],
    retry_results: Iterable[AgenticBatchResult],
    *,
    retry_chunk_ids: frozenset[str],
    chunks_by_id: Mapping[str, EvidenceChunk],
) -> tuple[AgenticRegionRecord, ...]:
    baseline = tuple(baseline_records)
    retries = tuple(retry_results)
    if not retry_chunk_ids:
        raise ValueError("retry chunk IDs cannot be empty")
    if any(result.validation_status is not ValidationStatus.ACCEPTED for result in retries):
        raise ValueError("region archives require accepted retry results")

    baseline_counts = Counter(
        str(chunk_id) for record in baseline for chunk_id in record.region.source_chunk_ids
    )
    if set(baseline_counts) != set(chunks_by_id) or any(
        count != 1 for count in baseline_counts.values()
    ):
        raise ValueError("baseline records must cover every source chunk exactly once")
    retry_counts = Counter(
        str(chunk_id)
        for result in retries
        for region in result.regions
        for chunk_id in region.source_chunk_ids
    )
    if set(retry_counts) != retry_chunk_ids or any(count != 1 for count in retry_counts.values()):
        raise ValueError("retry results must cover every selected source chunk exactly once")

    retained: list[AgenticRegionRecord] = []
    baseline_by_bundle: dict[str, list[AgenticRegionRecord]] = defaultdict(list)
    for record in baseline:
        source_ids = {str(value) for value in record.region.source_chunk_ids}
        overlap = source_ids & retry_chunk_ids
        if overlap and overlap != source_ids:
            raise ValueError("retry selection cannot split an existing baseline region")
        if overlap:
            baseline_by_bundle[record.region.bundle_id].append(record)
        else:
            retained.append(record)

    retry_by_bundle: dict[str, list[tuple[AgenticBatchResult, AgenticRegionProposal]]] = (
        defaultdict(list)
    )
    for result in retries:
        for region in result.regions:
            retry_by_bundle[region.bundle_id].append((result, region))
    if set(baseline_by_bundle) != set(retry_by_bundle):
        raise ValueError("retry and baseline bundle selections must match")

    for bundle_id in sorted(baseline_by_bundle):
        baseline_candidates = baseline_by_bundle[bundle_id]
        retry_candidates = retry_by_bundle[bundle_id]
        baseline_source_ids = {
            str(value) for record in baseline_candidates for value in record.region.source_chunk_ids
        }
        retry_source_ids = {
            str(value) for _, region in retry_candidates for value in region.source_chunk_ids
        }
        if baseline_source_ids != retry_source_ids:
            raise ValueError("retry candidates must preserve bundle-local source coverage")

        baseline_issues = tuple(
            issue for record in baseline_candidates for issue in record.quality_issues
        )
        retry_audits = tuple(
            (result, region, audit_agentic_region(region, chunks_by_id))
            for result, region in retry_candidates
        )
        retry_issues = tuple(issue for _, _, audit in retry_audits for issue in audit.issues)
        if agentic_quality_score(retry_issues) >= agentic_quality_score(baseline_issues):
            retained.extend(baseline_candidates)
            continue
        for result, region, audit in retry_audits:
            if set(audit.issues) & _BLOCKING_ARCHIVE_ISSUES:
                raise ValueError("retry region contains a deterministic quality defect")
            if result.response_sha256 is None:
                raise ValueError("accepted result must retain its response hash")
            retained.append(
                AgenticRegionRecord(
                    region_id=agentic_region_id(region),
                    origin=AgenticRegionOrigin.SEMANTIC_RETRY,
                    source_batch_id=result.batch_id,
                    model=result.model,
                    response_sha256=result.response_sha256,
                    quality_issues=audit.issues,
                    region=region,
                )
            )

    retained.sort(
        key=lambda record: (
            record.region.bundle_id,
            tuple(str(value) for value in record.region.source_chunk_ids),
            str(record.region_id),
        )
    )
    selected_counts = Counter(
        str(chunk_id) for record in retained for chunk_id in record.region.source_chunk_ids
    )
    if selected_counts != baseline_counts:
        raise ValueError("selected region archive must preserve exact source coverage")
    expected_money = Counter(
        str(component.component_id)
        for chunk in chunks_by_id.values()
        for component in chunk.candidate_money_components
    )
    selected_money = Counter(
        str(interpretation.source_component_id)
        for record in retained
        for interpretation in record.region.money_interpretations
    )
    if selected_money != expected_money:
        raise ValueError("selected region archive must preserve exact money coverage")
    if len({record.region_id for record in retained}) != len(retained):
        raise ValueError("selected region IDs must be unique")
    return tuple(retained)
