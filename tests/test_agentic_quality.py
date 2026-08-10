from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5

from lunarbit.agentic import (
    AgenticBatchResult,
    AgenticConflictFlag,
    AgenticEntityCandidate,
    AgenticFactCandidate,
    AgenticRegionProposal,
)
from lunarbit.agentic_quality import (
    AgenticQualityIssue,
    AgenticRegionOrigin,
    agentic_quality_score,
    agentic_region_id,
    audit_agentic_region,
    compile_agentic_region_records,
    repair_agentic_result,
    select_agentic_region_retries,
)
from lunarbit.models import (
    BoundingBox,
    CandidateAssertion,
    CandidateFactType,
    ChunkType,
    EntityMention,
    EntityType,
    EvidenceChunk,
    EvidenceSourceKind,
    ExtractionMethod,
    FinancialRole,
    PrivacyStatus,
    QueryFamily,
    SemanticRole,
    ValidationStatus,
)


def _evidence_chunk() -> EvidenceChunk:
    text = "Order ORD-42 from Sample Kitchen"
    order_start = text.index("ORD-42")
    merchant_start = text.index("Sample Kitchen")
    source_id = "doc_0000000000000042"
    return EvidenceChunk(
        chunk_id=uuid5(NAMESPACE_URL, "quality-source-chunk"),
        source_kind=EvidenceSourceKind.DOCUMENT,
        source_id=source_id,
        document_id=source_id,
        page_number=1,
        chunk_type=ChunkType.ORDER_HEADER,
        semantic_role=SemanticRole.ORDER_IDENTITY,
        financial_role=FinancialRole.NONE,
        raw_text_private=text,
        normalized_text_private=text.lower(),
        semantic_summary_private="Order identity from Sample Kitchen.",
        embedding_text_private="Sample Kitchen order ORD-42.",
        bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=20),
        reading_order=1,
        source_region_ids=("region-1",),
        entity_mentions=(
            EntityMention(
                mention_id=uuid5(NAMESPACE_URL, "quality-merchant-mention"),
                entity_type=EntityType.MERCHANT,
                raw_value_private="Sample Kitchen",
                normalized_value_private="sample kitchen",
                source_span_start=merchant_start,
                source_span_end=merchant_start + len("Sample Kitchen"),
                confidence=Decimal("1"),
            ),
        ),
        candidate_assertions=(
            CandidateAssertion(
                assertion_id=uuid5(NAMESPACE_URL, "quality-order-assertion"),
                fact_type=CandidateFactType.ORDER_ID,
                raw_value_private="ORD-42",
                normalized_value_private="ord-42",
                source_span_start=order_start,
                source_span_end=order_start + len("ORD-42"),
                confidence=Decimal("1"),
            ),
        ),
        query_families=(QueryFamily.ORDER_LOOKUP, QueryFamily.EVIDENCE_REPLAY),
        source_hash=sha256(text.encode()).hexdigest(),
        extraction_method=ExtractionMethod.NATIVE,
        extraction_confidence=Decimal("1"),
        chunk_completeness=Decimal("1"),
        validation_status=ValidationStatus.ACCEPTED,
        privacy_class=PrivacyStatus.PRIVATE,
    )


def _region(chunk: EvidenceChunk) -> AgenticRegionProposal:
    return AgenticRegionProposal(
        bundle_id="msg_0000000000000042",
        source_chunk_ids=(chunk.chunk_id,),
        chunk_type=ChunkType.ORDER_HEADER,
        semantic_role=SemanticRole.ORDER_IDENTITY,
        financial_role=FinancialRole.NONE,
        region_title_private="Order identity",
        semantic_summary_private="Order identity from c0001.",
        embedding_text_private="Order identity from c0001.",
        query_families=(QueryFamily.ORDER_LOOKUP, QueryFamily.EVIDENCE_REPLAY),
        candidate_facts=(),
        entity_candidates=(),
        money_interpretations=(),
        relation_candidates=(),
        conflict_flags=(),
        uncertainty_notes_private=(),
    )


def test_audit_detects_actionable_content_quality_issues() -> None:
    chunk = _evidence_chunk()

    audit = audit_agentic_region(_region(chunk), {str(chunk.chunk_id): chunk})

    assert audit.issues == (
        AgenticQualityIssue.TEMPORARY_SOURCE_ALIAS,
        AgenticQualityIssue.MISSING_FACT_CANDIDATE,
        AgenticQualityIssue.MISSING_ENTITY_CANDIDATE,
        AgenticQualityIssue.DUPLICATE_RETRIEVAL_TEXT,
        AgenticQualityIssue.SHORT_STRUCTURALLY_SPARSE,
    )
    assert audit.missing_fact_candidates == 1
    assert audit.missing_entity_candidates == 1


def test_deterministic_repair_removes_aliases_and_restores_source_candidates() -> None:
    chunk = _evidence_chunk()
    result = AgenticBatchResult(
        batch_id=uuid4(),
        model="test-model",
        response_sha256="a" * 64,
        regions=(_region(chunk),),
        validation_status=ValidationStatus.ACCEPTED,
    )

    repaired, report = repair_agentic_result(result, {str(chunk.chunk_id): chunk})
    region = repaired.regions[0]

    assert "c0001" not in region.semantic_summary_private
    assert "c0001" not in region.embedding_text_private
    assert region.semantic_summary_private != region.embedding_text_private
    assert [fact.fact_type for fact in region.candidate_facts] == [CandidateFactType.ORDER_ID]
    assert region.entity_candidates == (
        AgenticEntityCandidate(
            entity_type=EntityType.MERCHANT,
            raw_value_private="Sample Kitchen",
            source_chunk_id=chunk.chunk_id,
        ),
    )
    assert report.changed_regions == 1
    assert report.restored_fact_candidates == 1
    assert report.restored_entity_candidates == 1
    assert report.removed_temporary_aliases == 2
    assert audit_agentic_region(region, {str(chunk.chunk_id): chunk}).issues == ()


def test_source_authored_c_reference_is_not_removed() -> None:
    chunk = _evidence_chunk().model_copy(
        update={"raw_text_private": "Product code c0001 is printed in the source"}
    )
    region = _region(chunk).model_copy(
        update={
            "semantic_summary_private": "Product code c0001 is printed in the source.",
            "embedding_text_private": "Find source product code c0001.",
            "candidate_facts": (),
            "entity_candidates": (),
        }
    )

    audit = audit_agentic_region(region, {str(chunk.chunk_id): chunk})

    assert AgenticQualityIssue.TEMPORARY_SOURCE_ALIAS not in audit.issues


def test_repair_removes_grounded_candidates_not_supplied_by_deterministic_extraction() -> None:
    chunk = _evidence_chunk()
    region = _region(chunk).model_copy(
        update={
            "candidate_facts": (
                AgenticFactCandidate(
                    fact_type=CandidateFactType.INVOICE_NUMBER,
                    raw_value_private="ORD-42",
                    normalized_value_private="ord-42",
                    source_chunk_id=chunk.chunk_id,
                    source_span_start=6,
                    source_span_end=12,
                ),
            ),
            "entity_candidates": (
                AgenticEntityCandidate(
                    entity_type=EntityType.LEGAL_ENTITY,
                    raw_value_private="Sample Kitchen",
                    source_chunk_id=chunk.chunk_id,
                ),
            ),
        }
    )
    result = AgenticBatchResult(
        batch_id=uuid4(),
        model="test-model",
        response_sha256="b" * 64,
        regions=(region,),
        validation_status=ValidationStatus.ACCEPTED,
    )

    audit = audit_agentic_region(region, {str(chunk.chunk_id): chunk})
    repaired, report = repair_agentic_result(result, {str(chunk.chunk_id): chunk})

    assert AgenticQualityIssue.UNSUPPORTED_FACT_CANDIDATE in audit.issues
    assert AgenticQualityIssue.UNSUPPORTED_ENTITY_CANDIDATE in audit.issues
    assert report.removed_unsupported_fact_candidates == 1
    assert report.removed_unsupported_entity_candidates == 1
    assert [candidate.fact_type for candidate in repaired.regions[0].candidate_facts] == [
        CandidateFactType.ORDER_ID
    ]
    assert [candidate.entity_type for candidate in repaired.regions[0].entity_candidates] == [
        EntityType.MERCHANT
    ]


def test_compile_region_records_replaces_selected_baseline_coverage_deterministically() -> None:
    first = _evidence_chunk()
    second = first.model_copy(
        update={
            "chunk_id": uuid5(NAMESPACE_URL, "quality-source-chunk-two"),
            "source_id": "doc_0000000000000043",
            "document_id": "doc_0000000000000043",
        }
    )
    chunks = {str(first.chunk_id): first, str(second.chunk_id): second}
    baseline = AgenticBatchResult(
        batch_id=uuid5(NAMESPACE_URL, "quality-baseline-batch"),
        model="baseline-model",
        response_sha256="c" * 64,
        regions=(_region(first), _region(second)),
        validation_status=ValidationStatus.ACCEPTED,
    )
    retry = AgenticBatchResult(
        batch_id=uuid5(NAMESPACE_URL, "quality-retry-batch"),
        model="retry-model",
        response_sha256="d" * 64,
        regions=(
            _region(first).model_copy(
                update={
                    "semantic_summary_private": "Improved order identity from source evidence.",
                    "embedding_text_private": "Find the improved Sample Kitchen order identity.",
                }
            ),
        ),
        validation_status=ValidationStatus.ACCEPTED,
    )
    repaired_baseline, _ = repair_agentic_result(baseline, chunks)
    repaired_retry, _ = repair_agentic_result(retry, chunks)

    records = compile_agentic_region_records(
        (repaired_baseline,),
        (repaired_retry,),
        retry_chunk_ids=frozenset({str(first.chunk_id)}),
        chunks_by_id=chunks,
    )

    assert len(records) == 2
    by_chunk = {str(record.region.source_chunk_ids[0]): record for record in records}
    assert by_chunk[str(first.chunk_id)].origin is AgenticRegionOrigin.SEMANTIC_RETRY
    assert by_chunk[str(second.chunk_id)].origin is AgenticRegionOrigin.REPAIRED_BASELINE
    assert by_chunk[str(first.chunk_id)].model == "retry-model"
    assert by_chunk[str(first.chunk_id)].region_id == agentic_region_id(
        by_chunk[str(first.chunk_id)].region
    )


def test_agentic_quality_score_prioritizes_evidence_risk_over_fallback_prose() -> None:
    assert agentic_quality_score((AgenticQualityIssue.UNCITED_AMOUNT_CONFLICT,)) > (
        agentic_quality_score(
            (
                AgenticQualityIssue.DETERMINISTIC_FALLBACK,
                AgenticQualityIssue.DETERMINISTIC_FALLBACK,
                AgenticQualityIssue.DETERMINISTIC_FALLBACK,
                AgenticQualityIssue.DETERMINISTIC_FALLBACK,
            )
        )
    )
    assert agentic_quality_score((AgenticQualityIssue.SHORT_STRUCTURALLY_SPARSE,)) > (
        agentic_quality_score((AgenticQualityIssue.DETERMINISTIC_FALLBACK,))
    )


def test_retry_selection_improves_bundles_without_accepting_higher_evidence_risk() -> None:
    first = _evidence_chunk()
    second = first.model_copy(
        update={
            "chunk_id": uuid5(NAMESPACE_URL, "quality-source-chunk-two"),
            "source_id": "doc_0000000000000043",
            "document_id": "doc_0000000000000043",
        }
    )
    chunks = {str(first.chunk_id): first, str(second.chunk_id): second}
    baseline_result = AgenticBatchResult(
        batch_id=uuid5(NAMESPACE_URL, "quality-selection-baseline"),
        model="baseline-model",
        response_sha256="e" * 64,
        regions=(
            _region(first).model_copy(update={"bundle_id": "bundle-one"}),
            _region(second).model_copy(update={"bundle_id": "bundle-two"}),
        ),
        validation_status=ValidationStatus.ACCEPTED,
    )
    repaired_baseline, _ = repair_agentic_result(baseline_result, chunks)
    baseline_records = compile_agentic_region_records(
        (),
        (repaired_baseline,),
        retry_chunk_ids=frozenset({str(first.chunk_id), str(second.chunk_id)}),
        chunks_by_id=chunks,
    )
    baseline_records = tuple(
        record.model_copy(
            update={
                "origin": AgenticRegionOrigin.REPAIRED_BASELINE,
                "quality_issues": (AgenticQualityIssue.DETERMINISTIC_FALLBACK,),
            }
        )
        for record in baseline_records
    )
    retry_result = AgenticBatchResult(
        batch_id=uuid5(NAMESPACE_URL, "quality-selection-retry"),
        model="retry-model",
        response_sha256="f" * 64,
        regions=(
            _region(first).model_copy(
                update={
                    "bundle_id": "bundle-one",
                    "semantic_summary_private": "Improved order identity from source evidence.",
                    "embedding_text_private": "Find the improved Sample Kitchen order identity.",
                }
            ),
            _region(second).model_copy(
                update={
                    "bundle_id": "bundle-two",
                    "semantic_summary_private": "Order identity with an uncertain amount conflict.",
                    "embedding_text_private": "Find the uncertain Sample Kitchen order identity.",
                    "conflict_flags": (AgenticConflictFlag.AMOUNT_SCOPE_CONFLICT,),
                    "uncertainty_notes_private": (
                        "The conflicting amount 999 is not present in cited evidence.",
                    ),
                }
            ),
        ),
        validation_status=ValidationStatus.ACCEPTED,
    )
    repaired_retry, _ = repair_agentic_result(retry_result, chunks)

    records = select_agentic_region_retries(
        baseline_records,
        (repaired_retry,),
        retry_chunk_ids=frozenset(chunks),
        chunks_by_id=chunks,
    )

    by_bundle = {record.region.bundle_id: record for record in records}
    assert by_bundle["bundle-one"].origin is AgenticRegionOrigin.SEMANTIC_RETRY
    assert by_bundle["bundle-one"].quality_issues == ()
    assert by_bundle["bundle-two"].origin is AgenticRegionOrigin.REPAIRED_BASELINE
    assert by_bundle["bundle-two"].quality_issues == (
        AgenticQualityIssue.DETERMINISTIC_FALLBACK,
    )
