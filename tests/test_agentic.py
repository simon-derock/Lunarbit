from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

import lunarbit.agentic as agentic_module
from lunarbit.agentic import (
    AGENTIC_CONTRACT_VERSION,
    AGENTIC_TOOL_NAME,
    CLOUDFLARE_CONTEXT_WINDOW_TOKENS,
    CLOUDFLARE_MODEL,
    CLOUDFLARE_REASONING_EFFORT,
    CLOUDFLARE_STREAM_TIMEOUT_SECONDS,
    AgenticBatch,
    AgenticBatchPlan,
    AgenticBatchPolicy,
    AgenticEvidenceBundle,
    CloudflareWorkersAIClient,
    CloudflareWorkersAIError,
    StreamingTransportResponse,
    _agentic_tool_definition,
    _decode_cloudflare_sse,
    _estimate_output_tokens,
    execute_agentic_plan,
    plan_agentic_batches,
    render_agentic_user_prompt,
    validate_agentic_response,
)
from lunarbit.models import (
    BoundingBox,
    CandidateMoneyComponent,
    CandidateMoneyType,
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


class _CharacterTokenCounter:
    identifier = "test-character-counter"

    def count_text(self, text: str) -> int:
        return (len(text) + 3) // 4

    def count_messages(self, *, system_prompt: str, user_prompt: str) -> int:
        return self.count_text(system_prompt) + self.count_text(user_prompt)


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
    entity_mentions: tuple[EntityMention, ...] = (),
    candidate_money_components: tuple[CandidateMoneyComponent, ...] = (),
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
        entity_mentions=entity_mentions,
        candidate_money_components=candidate_money_components,
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
        target_input_tokens=6_500,
        max_input_tokens=9_000,
        max_completion_tokens=1_000,
        context_window_tokens=12_000,
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
        batch.estimated_input_tokens
        >= token_counter.count_messages(
            system_prompt="",
            user_prompt=render_agentic_user_prompt(batch),
        )
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


def test_output_budget_splits_large_payloads_before_model_execution() -> None:
    bundle = _bundle(
        "output-heavy",
        tuple(
            _chunk(index, source_number=1, text=f"rich evidence {index} " * 8)
            for index in range(1, 11)
        ),
        cohort="zomato:food:pdf-backed",
    )
    policy = AgenticBatchPolicy(
        target_input_tokens=50_000,
        max_input_tokens=60_000,
        max_completion_tokens=24_000,
        max_estimated_output_tokens=2_500,
        context_window_tokens=100_000,
        max_chunks=10,
        max_bundles=1,
        minimum_chunks=2,
    )

    plan = plan_agentic_batches(
        (bundle,),
        policy=policy,
        token_counter=_CharacterTokenCounter(),
    )

    assert len(plan.batches) > 1
    assert all(
        _estimate_output_tokens(
            tuple(
                agentic_module._ChunkAssignment(
                    bundle_id=bundle_id,
                    cohort_key=plan.batches[0].cohort_key,
                    chunk=chunk,
                )
                for bundle_id, chunk in zip(batch.chunk_bundle_ids, batch.chunks, strict=True)
            )
        )
        <= policy.max_estimated_output_tokens
        for batch in plan.batches
    )


class _FakeTransport:
    def __init__(self, response: StreamingTransportResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post_sse(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> StreamingTransportResponse:
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
    merchant_text = "Restaurant: Test Kitchen"
    merchant_start = merchant_text.index("Test Kitchen")
    bundle = _bundle(
        "order-client",
        (
            _chunk(1, source_number=1, text="Order ID: 1234567890"),
            _chunk(
                2,
                source_number=1,
                text=merchant_text,
                entity_mentions=(
                    EntityMention(
                        mention_id=uuid5(NAMESPACE_URL, "test-mention:merchant"),
                        entity_type=EntityType.MERCHANT,
                        raw_value_private="Test Kitchen",
                        normalized_value_private="test kitchen",
                        source_span_start=merchant_start,
                        source_span_end=merchant_start + len("Test Kitchen"),
                        confidence=Decimal("1"),
                    ),
                ),
            ),
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
        "covered_source_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
        "covered_money_component_ids": [],
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
        StreamingTransportResponse(
            status_code=200,
            headers={"cf-ray": "safe-request-id"},
            content=f"```json\n{json.dumps(model_output)}\n```",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            completed=True,
            tool_name=AGENTIC_TOOL_NAME,
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
        "Accept": "text/event-stream",
    }
    payload = call["payload"]
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["reasoning_effort"] == CLOUDFLARE_REASONING_EFFORT
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["tool_choice"] == "required"
    assert payload["parallel_tool_calls"] is False
    tools = payload["tools"]
    assert isinstance(tools, list)
    assert len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, dict)
    assert tool["name"] == AGENTIC_TOOL_NAME
    parameters = tool["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["required"] == [
        "batch_id",
        "covered_source_chunk_ids",
        "covered_money_component_ids",
        "regions",
    ]
    properties = parameters["properties"]
    assert isinstance(properties, dict)
    batch_id_schema = properties["batch_id"]
    assert isinstance(batch_id_schema, dict)
    assert batch_id_schema["const"] == str(batch.batch_id)
    coverage_schema = properties["covered_source_chunk_ids"]
    assert isinstance(coverage_schema, dict)
    assert coverage_schema["const"] == [str(chunk.chunk_id) for chunk in batch.chunks]
    money_coverage_schema = properties["covered_money_component_ids"]
    assert isinstance(money_coverage_schema, dict)
    assert money_coverage_schema["const"] == []
    regions_schema = properties["regions"]
    assert isinstance(regions_schema, dict)
    assert "allOf" not in regions_schema
    assert regions_schema["maxItems"] == len(batch.chunks)
    definitions = parameters["$defs"]
    assert isinstance(definitions, dict)
    region_definition = definitions["AgenticRegionProposal"]
    assert isinstance(region_definition, dict)
    region_properties = region_definition["properties"]
    assert isinstance(region_properties, dict)
    assert region_properties["region_title_private"]["maxLength"] == 160
    assert region_properties["semantic_summary_private"]["maxLength"] == 1_200
    assert region_properties["embedding_text_private"]["maxLength"] == 1_600
    assert region_properties["relation_candidates"]["maxItems"] == 32
    assert region_properties["uncertainty_notes_private"]["maxItems"] == 8
    bundle_schema = region_properties["bundle_id"]
    source_ids_schema = region_properties["source_chunk_ids"]
    assert isinstance(bundle_schema, dict)
    assert isinstance(source_ids_schema, dict)
    assert bundle_schema["enum"] == ["order-client"]
    assert source_ids_schema["uniqueItems"] is True
    source_id_items = source_ids_schema["items"]
    assert isinstance(source_id_items, dict)
    assert set(source_id_items["enum"]) == {str(chunk.chunk_id) for chunk in batch.chunks}
    entity_definition = definitions["AgenticEntityCandidate"]
    assert isinstance(entity_definition, dict)
    entity_constraints = entity_definition["anyOf"]
    assert isinstance(entity_constraints, list)
    assert entity_constraints == [
        {
            "properties": {
                "entity_type": {"const": "merchant"},
                "raw_value_private": {"const": "Test Kitchen"},
                "source_chunk_id": {"const": str(batch.chunks[1].chunk_id)},
            },
            "required": ["entity_type", "raw_value_private", "source_chunk_id"],
        }
    ]
    assert payload["temperature"] == 0
    assert payload["seed"] == 42
    assert payload["max_completion_tokens"] == 24_000
    assert call["timeout_seconds"] == CLOUDFLARE_STREAM_TIMEOUT_SECONDS
    messages = payload["messages"]
    assert isinstance(messages, list)
    second_message = messages[1]
    assert isinstance(second_message, dict)
    assert second_message["content"] == render_agentic_user_prompt(batch)
    assert "response_format" not in payload
    assert "private-token" not in repr(client)


def test_agentic_prompt_enforces_closed_entity_vocabulary() -> None:
    batch, _ = _one_batch()

    prompt = render_agentic_user_prompt(batch)

    assert "Entity candidates use a closed vocabulary" in prompt
    assert "restaurant, store, or vendor as merchant" in prompt
    assert "Never emit customer, person, item, address, order, or payment method" in prompt
    assert "use an empty array instead of inventing an enum value" in prompt
    assert "raw_value_private byte-for-byte from the cited source chunk" in prompt
    assert "union of source_chunk_ids equals the complete input chunk set exactly" in prompt
    assert "Every mail-only bundle must produce at least one region" in prompt


def test_invalid_model_batch_is_quarantined_without_partial_acceptance() -> None:
    batch, chunk_ids = _one_batch()
    incomplete_output = {
        "batch_id": str(batch.batch_id),
        "covered_source_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
        "covered_money_component_ids": [],
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
        StreamingTransportResponse(
            status_code=200,
            headers={},
            content=json.dumps(incomplete_output),
            finish_reason="stop",
            usage={},
            completed=True,
            tool_name=AGENTIC_TOOL_NAME,
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


def test_model_must_interpret_every_deterministic_money_component() -> None:
    money_text = "Invoice total: 120.00"
    amount_start = money_text.index("120.00")
    component_id = uuid5(NAMESPACE_URL, "test-money:invoice-total")
    bundle = _bundle(
        "money-order",
        (
            _chunk(
                10,
                source_number=10,
                text=money_text,
                chunk_type=ChunkType.SUBTOTAL,
                semantic_role=SemanticRole.FINANCIAL_DETAIL,
                financial_role=FinancialRole.TOTAL,
                candidate_money_components=(
                    CandidateMoneyComponent(
                        component_id=component_id,
                        component_type=CandidateMoneyType.INVOICE_TOTAL,
                        amount=Decimal("120.00"),
                        source_amount_string_private="120.00",
                        source_precision=2,
                        source_span_start=amount_start,
                        source_span_end=amount_start + len("120.00"),
                        confidence=Decimal("1"),
                    ),
                ),
            ),
            _chunk(11, source_number=10, text="Order ID: 1234567890"),
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
            max_chunks=4,
            max_bundles=1,
            minimum_chunks=2,
        ),
        token_counter=_CharacterTokenCounter(),
    )
    batch = plan.batches[0]
    tool = _agentic_tool_definition(
        batch_id=batch.batch_id,
        bundle_ids=batch.bundle_ids,
        chunks=batch.chunks,
    )
    parameters = tool["parameters"]
    assert isinstance(parameters, dict)
    money_definition = parameters["$defs"]["AgenticMoneyInterpretation"]
    assert "anyOf" not in money_definition
    money_properties = money_definition["properties"]
    assert money_properties["source_component_id"]["enum"] == [str(component_id)]
    assert money_properties["source_chunk_id"]["enum"] == [str(batch.chunks[0].chunk_id)]
    response = {
        "batch_id": str(batch.batch_id),
        "covered_source_chunk_ids": [str(chunk.chunk_id) for chunk in batch.chunks],
        "covered_money_component_ids": [str(component_id)],
        "regions": [
            {
                "source_chunk_ids": [str(chunk.chunk_id) for chunk in batch.chunks],
                "bundle_id": "money-order",
                "chunk_type": "SUBTOTAL",
                "semantic_role": "financial_detail",
                "financial_role": "total",
                "region_title_private": "Invoice total",
                "semantic_summary_private": "Invoice total evidence.",
                "embedding_text_private": "Invoice total 120.00.",
                "query_families": ["financial_breakdown", "evidence_replay"],
                "candidate_facts": [],
                "entity_candidates": [],
                "money_interpretations": [],
                "relation_candidates": [],
                "conflict_flags": [],
                "uncertainty_notes_private": [],
            }
        ],
    }

    result = validate_agentic_response(batch, json.dumps(response))

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.regions == ()
    assert result.quarantine_reasons == ("incomplete_money_component_coverage",)


def test_invalid_model_json_is_quarantined_with_a_safe_reason() -> None:
    batch, _ = _one_batch()

    result = validate_agentic_response(batch, "not a JSON response")

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.quarantine_reasons == ("invalid_model_json",)


def test_invalid_model_schema_reports_only_type_and_field_location() -> None:
    batch, _ = _one_batch()
    private_sentinel = "PRIVATE_VALUE_MUST_NOT_APPEAR"
    invalid_response = {
        "batch_id": str(batch.batch_id),
        "regions": [
            {
                "bundle_id": private_sentinel,
                "source_chunk_ids": [str(batch.chunks[0].chunk_id)],
            }
        ],
    }

    result = validate_agentic_response(batch, json.dumps(invalid_response))

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert len(result.quarantine_reasons) > 1
    assert all(reason.startswith("invalid_model_schema:") for reason in result.quarantine_reasons)
    assert any("regions.0" in reason for reason in result.quarantine_reasons)
    assert all(private_sentinel not in reason for reason in result.quarantine_reasons)


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
        "covered_source_chunk_ids": [str(chunk.chunk_id) for chunk in batch.chunks],
        "covered_money_component_ids": [],
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


def test_cloudflare_sse_decoder_assembles_only_answer_content() -> None:
    events = (
        b'data: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"},'
        b'"finish_reason":null}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"content":"{\\"batch_id\\":"},"finish_reason":null}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"content":"\\"value\\"}"},'
        b'"finish_reason":"stop"}],"usage":{"completion_tokens":12}}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    )

    content, finish_reason, usage, completed, tool_name = _decode_cloudflare_sse(events)

    assert content == '{"batch_id":"value"}'
    assert "private reasoning" not in content
    assert finish_reason == "stop"
    assert usage == {"completion_tokens": 12}
    assert completed is True
    assert tool_name is None


def test_cloudflare_sse_decoder_assembles_function_arguments() -> None:
    events = (
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"type":"function",'
        b'"function":{"name":"submit_agentic_regions","arguments":"{\\"batch_id\\":"}}]},'
        b'"finish_reason":null}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":'
        b'{"arguments":"\\"value\\"}"}}]},"finish_reason":"tool_calls"}]}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    )

    content, finish_reason, _, completed, tool_name = _decode_cloudflare_sse(events)

    assert content == '{"batch_id":"value"}'
    assert finish_reason == "tool_calls"
    assert completed is True
    assert tool_name == AGENTIC_TOOL_NAME


def test_cloudflare_sse_decoder_enforces_wall_clock_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agentic_module.time, "monotonic", lambda: 11.0)

    with pytest.raises(CloudflareWorkersAIError, match="exceeded its deadline"):
        _decode_cloudflare_sse(
            (b"data: [DONE]\n",),
            deadline_monotonic=10.0,
        )


def test_cloudflare_sse_decoder_exposes_only_numeric_provider_error_code() -> None:
    private_message = "PRIVATE_PROVIDER_MESSAGE_MUST_NOT_ESCAPE"
    events = (
        b"data: "
        + json.dumps(
            {
                "success": False,
                "errors": [{"code": 7000, "message": private_message}],
            }
        ).encode()
        + b"\n",
        b"\n",
    )

    with pytest.raises(CloudflareWorkersAIError) as raised:
        _decode_cloudflare_sse(events)

    assert raised.value.code == "stream_rejected_cf_7000"
    assert private_message not in str(raised.value)


def test_cloudflare_client_quarantines_length_limited_stream() -> None:
    batch, _ = _one_batch()
    transport = _FakeTransport(
        StreamingTransportResponse(
            status_code=200,
            headers={},
            content='{"batch_id":',
            finish_reason="length",
            usage={"completion_tokens": 24_000},
            completed=True,
            tool_name=AGENTIC_TOOL_NAME,
        )
    )
    client = CloudflareWorkersAIClient(
        account_id="0123456789abcdef0123456789abcdef",
        auth_token="private-token",
        transport=transport,
    )

    result = client.propose(batch)

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.quarantine_reasons == ("model_output_truncated",)


def test_execute_plan_persists_only_safe_transport_error_code(tmp_path: Path) -> None:
    batch, _ = _one_batch()
    plan = AgenticBatchPlan(
        policy=AgenticBatchPolicy(
            target_input_tokens=4_000,
            max_input_tokens=6_000,
            max_completion_tokens=1_000,
            context_window_tokens=8_000,
            max_chunks=8,
            max_bundles=1,
            minimum_chunks=2,
        ),
        bundles=1,
        input_chunks=len(batch.chunks),
        batches=(batch,),
    )

    class _FailingClient:
        def propose(self, _: AgenticBatch) -> Any:
            raise CloudflareWorkersAIError(
                "safe message without response content",
                code="mixed_content_tool_call",
            )

    summary = execute_agentic_plan(
        plan,
        client=_FailingClient(),  # type: ignore[arg-type]
        output_root=tmp_path,
        max_calls=1,
    )
    persisted = json.loads((tmp_path / f"{batch.batch_id}.json").read_text())

    assert summary.quarantined_batches == 1
    assert persisted["quarantine_reasons"] == ["api_request_failed:mixed_content_tool_call"]
    assert "safe message" not in json.dumps(persisted)


def test_default_policy_uses_80k_input_tokens_and_reserves_context() -> None:
    policy = AgenticBatchPolicy()

    assert AGENTIC_CONTRACT_VERSION == "1.4.0"
    assert CLOUDFLARE_MODEL == "@cf/google/gemma-4-26b-a4b-it"
    assert CLOUDFLARE_CONTEXT_WINDOW_TOKENS == 256_000
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
