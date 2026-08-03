from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from lunarbit.agentic import (
    CLOUDFLARE_MODEL,
    GLM_CONTEXT_WINDOW_TOKENS,
    AgenticBatch,
    AgenticBatchPolicy,
    AgenticEvidenceBundle,
    CloudflareWorkersAIClient,
    TransportResponse,
    plan_agentic_batches,
    render_agentic_user_prompt,
    validate_agentic_response,
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


class _CharacterTokenCounter:
    identifier = "test-character-counter"

    def count_messages(self, *, system_prompt: str, user_prompt: str) -> int:
        return len(system_prompt) + len(user_prompt)


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
        target_input_tokens=2_500,
        max_input_tokens=4_500,
        max_completion_tokens=1_000,
        context_window_tokens=8_000,
        max_chunks=4,
        max_bundles=4,
        minimum_chunks=2,
    )

    token_counter = _CharacterTokenCounter()
    first = plan_agentic_batches(
        (attached, mail_one, mail_two), policy=policy, token_counter=token_counter
    )
    second = plan_agentic_batches(
        (attached, mail_one, mail_two), policy=policy, token_counter=token_counter
    )

    assert first == second
    assert first.quarantined_chunk_ids == ()
    assert {item.chunk_id for batch in first.batches for item in batch.chunks} == {
        chunk.chunk_id for bundle in (attached, mail_one, mail_two) for chunk in bundle.chunks
    }
    chunk_counts = tuple(len(batch.chunks) for batch in first.batches)
    assert all(policy.minimum_chunks <= count <= policy.max_chunks for count in chunk_counts)
    assert all(batch.estimated_input_tokens <= policy.max_input_tokens for batch in first.batches)
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
            target_input_tokens=4_000,
            max_input_tokens=6_000,
            max_completion_tokens=1_000,
            context_window_tokens=8_000,
            max_chunks=8,
            max_bundles=1,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )

    assert len(plan.batches) == 1
    assert tuple(item.chunk_id for item in plan.batches[0].chunks) == tuple(
        chunk.chunk_id for chunk in bundle.chunks
    )


def test_final_mail_singleton_is_rebalanced_without_a_one_chunk_call() -> None:
    bundles = tuple(
        _bundle(
            f"mail-{index}",
            (_chunk(index, source_number=index, text=f"complete mail order {index}"),),
            mail_only=True,
        )
        for index in range(1, 8)
    )

    plan = plan_agentic_batches(
        bundles,
        policy=AgenticBatchPolicy(
            target_input_tokens=20_000,
            max_input_tokens=30_000,
            max_completion_tokens=5_000,
            context_window_tokens=40_000,
            max_chunks=6,
            max_bundles=6,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )

    assert plan.quarantined_chunk_ids == ()
    assert tuple(len(batch.chunks) for batch in plan.batches) == (5, 2)


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


def _one_batch() -> tuple[AgenticBatch, tuple[UUID, UUID]]:
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
            target_input_tokens=4_000,
            max_input_tokens=6_000,
            max_completion_tokens=1_000,
            context_window_tokens=8_000,
            max_chunks=8,
            max_bundles=1,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )
    batch = plan.batches[0]
    chunk_ids = tuple(item.chunk_id for item in batch.chunks)
    assert len(chunk_ids) == 2
    return batch, (chunk_ids[0], chunk_ids[1])


def test_cloudflare_client_uses_selected_model_and_validates_complete_output() -> None:
    batch, chunk_ids = _one_batch()
    model_output = {
        "batch_id": str(batch.batch_id),
        "regions": [
            {
                "source_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
                "bundle_id": "order-client",
                "chunk_type": "ORDER_HEADER",
                "semantic_role": "order_identity",
                "financial_role": "none",
                "region_title_private": "Order identity",
                "semantic_summary_private": "Order identity and merchant evidence.",
                "embedding_text_private": "Order 1234567890 from Test Kitchen.",
                "query_families": ["order_lookup", "evidence_replay"],
                "candidate_facts": [],
                "money_interpretations": [],
                "conflict_flags": [],
                "uncertainty_notes_private": [],
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

    result = client.propose(batch)

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
    assert payload["max_completion_tokens"] == 24_000
    messages = payload["messages"]
    assert isinstance(messages, list)
    second_message = messages[1]
    assert isinstance(second_message, dict)
    assert second_message["content"] == render_agentic_user_prompt(batch)
    assert "response_format" not in payload
    assert "private-token" not in repr(client)


def test_invalid_model_batch_is_quarantined_without_partial_acceptance() -> None:
    batch, chunk_ids = _one_batch()
    incomplete_output = {
        "batch_id": str(batch.batch_id),
        "regions": [
            {
                "source_chunk_ids": [str(chunk_ids[0])],
                "bundle_id": "order-client",
                "chunk_type": "ORDER_HEADER",
                "semantic_role": "order_identity",
                "financial_role": "none",
                "region_title_private": "Incomplete order identity",
                "semantic_summary_private": "Only one source was covered.",
                "embedding_text_private": "Incomplete evidence.",
                "query_families": ["order_lookup"],
                "candidate_facts": [],
                "money_interpretations": [],
                "conflict_flags": [],
                "uncertainty_notes_private": [],
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

    result = client.propose(batch)

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.regions == ()
    assert result.quarantine_reasons == ("incomplete_batch_coverage",)


def test_model_cannot_merge_separate_mail_orders_in_a_shared_call() -> None:
    bundles = (
        _bundle(
            "mail-one",
            (_chunk(1, source_number=1, text="Order ID: 1234567890"),),
            mail_only=True,
        ),
        _bundle(
            "mail-two",
            (_chunk(2, source_number=2, text="Order ID: 9876543210"),),
            mail_only=True,
        ),
    )
    plan = plan_agentic_batches(
        bundles,
        policy=AgenticBatchPolicy(
            target_input_tokens=4_000,
            max_input_tokens=6_000,
            max_completion_tokens=1_000,
            context_window_tokens=8_000,
            max_chunks=4,
            max_bundles=4,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )
    batch = plan.batches[0]
    response = {
        "batch_id": str(batch.batch_id),
        "regions": [
            {
                "source_chunk_ids": [str(chunk.chunk_id) for chunk in batch.chunks],
                "bundle_id": "mail-one",
                "chunk_type": "ORDER_HEADER",
                "semantic_role": "order_identity",
                "financial_role": "none",
                "region_title_private": "Invalid merged orders",
                "semantic_summary_private": "Two orders incorrectly merged.",
                "embedding_text_private": "Two unrelated order identifiers.",
                "query_families": ["order_lookup"],
                "candidate_facts": [],
                "money_interpretations": [],
                "conflict_flags": [],
                "uncertainty_notes_private": [],
                "entity_candidates": [],
                "relation_candidates": [],
            }
        ],
    }

    result = validate_agentic_response(batch, json.dumps(response))

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.regions == ()
    assert result.quarantine_reasons == ("cross_bundle_region",)


def test_default_policy_uses_80k_input_tokens_and_reserves_context() -> None:
    policy = AgenticBatchPolicy()

    assert GLM_CONTEXT_WINDOW_TOKENS == 131_072
    assert policy.target_input_tokens == 64_000
    assert policy.max_input_tokens == 80_000
    assert policy.max_completion_tokens == 24_000
    assert policy.max_input_tokens + policy.max_completion_tokens < policy.context_window_tokens


def test_compatible_pdf_orders_share_a_token_bounded_call() -> None:
    first = _bundle(
        "pdf-order-one",
        (
            _chunk(30, source_number=30, text="first order header"),
            _chunk(31, source_number=30, text="first order total"),
        ),
        cohort="zomato:food:pdf-backed:order-summary+merchant-invoice",
    )
    second = _bundle(
        "pdf-order-two",
        (
            _chunk(40, source_number=40, text="second order header"),
            _chunk(41, source_number=40, text="second order total"),
        ),
        cohort="zomato:food:pdf-backed:order-summary+merchant-invoice",
    )

    plan = plan_agentic_batches(
        (first, second),
        policy=AgenticBatchPolicy(
            target_input_tokens=20_000,
            max_input_tokens=30_000,
            max_completion_tokens=5_000,
            context_window_tokens=40_000,
            max_chunks=16,
            max_bundles=6,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )

    assert len(plan.batches) == 1
    assert plan.batches[0].bundle_ids == ("pdf-order-one", "pdf-order-two")
    assert plan.batches[0].estimated_input_tokens <= 30_000


def test_agent_input_contains_full_deterministic_metadata() -> None:
    batch, _ = _one_batch()

    prompt = render_agentic_user_prompt(batch)

    for required_field in (
        '"bounding_box"',
        '"candidate_assertions"',
        '"candidate_money_components"',
        '"entity_mentions"',
        '"extraction_confidence"',
        '"query_families"',
        '"chunk_completeness"',
    ):
        assert required_field in prompt
