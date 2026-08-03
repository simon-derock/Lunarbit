from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from lunarbit.agentic import (
    CLOUDFLARE_MODEL,
    AgenticBatchPolicy,
    AgenticEvidenceBundle,
    CloudflareWorkersAIClient,
    TransportResponse,
    plan_agentic_batches,
    render_agentic_user_prompt,
)

from lunarbit.models import (
    BoundingBox,
    ChunkType,
    EvidenceChunk,
    EvidenceSourceKind,
    ExtractionMethod,
    FinancialRole,
    PrivacyStatus,
    QueryFamily,
    SemanticRole,
    ValidationStatus,
)


def _source_id(number: int) -> str:
    return f"doc_{number:016x}"


def _chunk(
    number: int,
    *,
    source_number: int,
    text: str,
    chunk_type: ChunkType = ChunkType.OTHER_EVIDENCE,
    semantic_role: SemanticRole = SemanticRole.GENERAL_EVIDENCE,
    financial_role: FinancialRole = FinancialRole.NONE,
    table_id: str | None = None,
    parent_region_id: str | None = None,
) -> EvidenceChunk:
    source_id = _source_id(source_number)
    return EvidenceChunk(
        chunk_id=uuid5(NAMESPACE_URL, f"test-chunk:{number}"),
        source_kind=EvidenceSourceKind.DOCUMENT,
        source_id=source_id,
        document_id=source_id,
        page_number=1,
        chunk_type=chunk_type,
        semantic_role=semantic_role,
        financial_role=financial_role,
        raw_text_private=text,
        normalized_text_private=text,
        semantic_summary_private=text,
        embedding_text_private=text,
        bounding_box=BoundingBox(x0=0, y0=float(number), x1=100, y1=float(number + 1)),
        reading_order=number,
        table_id=table_id,
        parent_region_id=parent_region_id,
        source_region_ids=(f"region_{number}",),
        query_families=(QueryFamily.EVIDENCE_REPLAY,),
        source_hash=sha256(text.encode()).hexdigest(),
        extraction_method=ExtractionMethod.NATIVE,
        extraction_confidence=Decimal("1"),
        chunk_completeness=Decimal("1"),
        validation_status=ValidationStatus.ACCEPTED,
        privacy_class=PrivacyStatus.PRIVATE,
    )


def _bundle(
    bundle_id: str,
    chunks: tuple[EvidenceChunk, ...],
    *,
    cohort: str = "zomato:food:mail-only",
    mail_only: bool = False,
) -> AgenticEvidenceBundle:
    return AgenticEvidenceBundle(
        bundle_id=bundle_id,
        cohort_key=cohort,
        mail_only=mail_only,
        chunks=chunks,
    )


def test_batch_plan_is_medium_sized_relevant_and_deterministic() -> None:
    attached = _bundle(
        "order-attached",
        tuple(
            _chunk(index, source_number=1, text=f"invoice evidence {index} " * 18)
            for index in range(1, 7)
        ),
        cohort="zomato:food:pdf-backed",
    )
    mail_one = _bundle(
        "mail-one",
        (_chunk(20, source_number=20, text="complete mail order one " * 12),),
        mail_only=True,
    )
    mail_two = _bundle(
        "mail-two",
        (_chunk(21, source_number=21, text="complete mail order two " * 12),),
        mail_only=True,
    )
    policy = AgenticBatchPolicy(
        target_prompt_characters=2_500,
        max_prompt_characters=4_500,
        max_chunks=4,
        max_bundles=4,
        minimum_chunks=2,
    )

    first = plan_agentic_batches((attached, mail_one, mail_two), policy=policy)
    second = plan_agentic_batches((attached, mail_one, mail_two), policy=policy)

    assert first == second
    assert first.quarantined_chunk_ids == ()
    assert {item.chunk_id for batch in first.batches for item in batch.chunks} == {
        chunk.chunk_id for bundle in (attached, mail_one, mail_two) for chunk in bundle.chunks
    }
    chunk_counts = tuple(len(batch.chunks) for batch in first.batches)
    assert all(policy.minimum_chunks <= count <= policy.max_chunks for count in chunk_counts)
    assert all(
        len(render_agentic_user_prompt(batch)) <= policy.max_prompt_characters
        for batch in first.batches
    )
    assert all(
        batch.bundle_ids == ("order-attached",)
        for batch in first.batches
        if "order-attached" in batch.bundle_ids
    )
    mail_batch = next(batch for batch in first.batches if "mail-one" in batch.bundle_ids)
    assert mail_batch.bundle_ids == ("mail-one", "mail-two")


def test_table_parent_and_rows_stay_in_one_batch_when_the_table_fits() -> None:
    table_id = "table_001_000"
    bundle = _bundle(
        "order-table",
        (
            _chunk(
                1,
                source_number=1,
                text="Item | Amount",
                chunk_type=ChunkType.ITEM_TABLE,
                semantic_role=SemanticRole.ITEM_DETAIL,
                table_id=table_id,
            ),
            _chunk(
                2,
                source_number=1,
                text="Meal | 120.00",
                chunk_type=ChunkType.ITEM_ROW,
                semantic_role=SemanticRole.ITEM_DETAIL,
                financial_role=FinancialRole.ITEM,
                parent_region_id=table_id,
            ),
            _chunk(
                3,
                source_number=1,
                text="Tax | 6.00",
                chunk_type=ChunkType.ITEM_ROW,
                semantic_role=SemanticRole.ITEM_DETAIL,
                financial_role=FinancialRole.TAX,
                parent_region_id=table_id,
            ),
        ),
        cohort="swiggy:food:pdf-backed",
    )

    plan = plan_agentic_batches(
        (bundle,),
        policy=AgenticBatchPolicy(
            target_prompt_characters=4_000,
            max_prompt_characters=6_000,
            max_chunks=8,
            max_bundles=1,
            minimum_chunks=2,
        ),
    )

    assert len(plan.batches) == 1
    assert tuple(item.chunk_id for item in plan.batches[0].chunks) == tuple(
        chunk.chunk_id for chunk in bundle.chunks
    )


class _FakeTransport:
    def __init__(self, response: TransportResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> TransportResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def _one_batch() -> tuple[object, tuple[UUID, UUID]]:
    bundle = _bundle(
        "order-client",
        (
            _chunk(1, source_number=1, text="Order ID: 1234567890"),
            _chunk(2, source_number=1, text="Restaurant: Test Kitchen"),
        ),
        cohort="zomato:food:pdf-backed",
    )
    plan = plan_agentic_batches(
        (bundle,),
        policy=AgenticBatchPolicy(
            target_prompt_characters=4_000,
            max_prompt_characters=6_000,
            max_chunks=8,
            max_bundles=1,
            minimum_chunks=2,
        ),
    )
    batch = plan.batches[0]
    return batch, tuple(item.chunk_id for item in batch.chunks)  # type: ignore[return-value]


def test_cloudflare_client_uses_selected_model_and_validates_complete_output() -> None:
    batch, chunk_ids = _one_batch()
    model_output = {
        "batch_id": str(batch.batch_id),  # type: ignore[attr-defined]
        "regions": [
            {
                "source_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
                "chunk_type": "ORDER_HEADER",
                "semantic_role": "order_identity",
                "financial_role": "none",
                "semantic_summary_private": "Order identity and merchant evidence.",
                "embedding_text_private": "Order 1234567890 from Test Kitchen.",
                "entity_candidates": [
                    {
                        "entity_type": "merchant",
                        "raw_value_private": "Test Kitchen",
                        "source_chunk_id": str(chunk_ids[1]),
                    }
                ],
                "relation_candidates": [
                    {
                        "relation_type": "ORDERED_FROM",
                        "subject_private": "ORDER",
                        "object_private": "Test Kitchen",
                        "evidence_chunk_ids": [str(chunk_ids[1])],
                    }
                ],
            }
        ],
    }
    transport = _FakeTransport(
        TransportResponse(
            status_code=200,
            headers={"cf-ray": "safe-request-id"},
            body={
                "success": True,
                "result": {"response": f"```json\n{json.dumps(model_output)}\n```"},
                "errors": [],
                "messages": [],
            },
        )
    )
    client = CloudflareWorkersAIClient(
        account_id="0123456789abcdef0123456789abcdef",
        auth_token="private-token",
        transport=transport,
    )

    result = client.propose(batch)  # type: ignore[arg-type]

    assert result.validation_status is ValidationStatus.ACCEPTED
    assert len(result.regions) == 1
    assert result.quarantine_reasons == ()
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"].endswith(f"/ai/run/{CLOUDFLARE_MODEL}")
    assert call["headers"] == {
        "Authorization": "Bearer private-token",
        "Content-Type": "application/json",
    }
    payload = call["payload"]
    assert payload["store"] is False
    assert payload["stream"] is False
    assert payload["temperature"] == 0
    assert payload["seed"] == 42
    assert payload["messages"][1]["content"] == render_agentic_user_prompt(batch)  # type: ignore[index]
    assert "response_format" not in payload
    assert "private-token" not in repr(client)


def test_invalid_model_batch_is_quarantined_without_partial_acceptance() -> None:
    batch, chunk_ids = _one_batch()
    incomplete_output = {
        "batch_id": str(batch.batch_id),  # type: ignore[attr-defined]
        "regions": [
            {
                "source_chunk_ids": [str(chunk_ids[0])],
                "chunk_type": "ORDER_HEADER",
                "semantic_role": "order_identity",
                "financial_role": "none",
                "semantic_summary_private": "Only one source was covered.",
                "embedding_text_private": "Incomplete evidence.",
                "entity_candidates": [],
                "relation_candidates": [],
            }
        ],
    }
    transport = _FakeTransport(
        TransportResponse(
            status_code=200,
            headers={},
            body={"success": True, "result": {"response": json.dumps(incomplete_output)}},
        )
    )
    client = CloudflareWorkersAIClient(
        account_id="0123456789abcdef0123456789abcdef",
        auth_token="private-token",
        transport=transport,
    )

    result = client.propose(batch)  # type: ignore[arg-type]

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.regions == ()
    assert result.quarantine_reasons == ("incomplete_batch_coverage",)
