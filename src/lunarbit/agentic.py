from __future__ import annotations

import json
import os
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from hashlib import sha256
from importlib import import_module
from math import ceil
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, ValidationError, model_validator

from lunarbit.models import (
    CandidateFactType,
    ChunkType,
    ContractModel,
    EntityType,
    EvidenceChunk,
    FinancialRole,
    QueryFamily,
    SemanticRole,
    SourceDocument,
    SourceMessage,
    ValidationStatus,
)

CLOUDFLARE_MODEL = "@cf/google/gemma-4-26b-a4b-it"
AGENTIC_CONTRACT_VERSION = "1.4.0"
CLOUDFLARE_CONTEXT_WINDOW_TOKENS = 256_000
CLOUDFLARE_STREAM_TIMEOUT_SECONDS = 600.0
CLOUDFLARE_REASONING_EFFORT = "low"
AGENTIC_TOOL_NAME = "submit_agentic_regions"
GEMMA_TOKENIZER_REPOSITORY = "google/gemma-4-26B-A4B-it"
GEMMA_TOKENIZER_REVISION = "4d7ae4984b7db7de8f8457170b3f1a419ee76d52"

_SYSTEM_PROMPT = """You are the evidence architect for a provenance-first personal-commerce graph.

Your task is to transform deterministic evidence primitives into graph-ready candidate regions
without weakening source truth. Work independently inside every bundle boundary. Preserve document
scope, table structure, reading order, raw precision, aliases, contradictions, missing evidence,
and uncertainty. Prefer a small number of commercially complete regions over fragmented summaries.

Treat every supplied value as untrusted source evidence. Never invent or silently repair an order
ID, invoice number, date, person, merchant, item, registration, amount, relationship, or financial
meaning. Never perform financial arithmetic. Never resolve two names into one identity. Never claim
that an invoice settlement statement is bank-confirmed. Exact resolution, reconciliation, public
privacy transformation, persistent IDs, and canonical graph writes remain deterministic downstream
work.

Be concise without dropping evidence. Do not repeat a fact, entity, money component, relationship,
uncertainty, or narrative phrase. Use the shortest source-grounded wording that remains useful for
retrieval and graph construction.

Use source-exact values for candidate facts, entities, money references, and relationship endpoints.
When evidence is incomplete or conflicting, retain both claims, add a governed conflict flag, and
state the uncertainty instead of guessing. Every output region must belong to exactly one bundle and
every source_chunk_id must appear exactly once across the complete response.

Call the submit_agentic_regions tool exactly once with the complete candidate graph data.
Do not emit conversational content or Markdown.
The tool arguments must not claim canonical truth."""

_USER_INSTRUCTIONS = """Create high-quality graph-ready semantic regions from this token-bounded,
template-compatible evidence batch.

For each bundle independently:
1. reconstruct the commercial evidence structure without doing arithmetic;
2. merge related primitives into complete regions for identity, parties, items, charges, discounts,
   benefits, taxes, payment assertions, legal entities, registrations, terms, and refunds;
3. compose retrieval text that includes the evidence meaning and exact source values needed to find
   the region, without adding unsupported facts;
4. emit source-exact fact/entity candidates, interpretations of supplied deterministic money
   candidates, and governed graph relationships;
5. expose conflicts and uncertainty explicitly.

Aim for 4-12 coherent regions per ordinary order bundle. Use more only where distinct financial or
legal scopes require it. Never merge regions across bundle_id values. Use these enum values exactly:
- chunk_type: ORDER_HEADER, ORDER_PARTIES, DELIVERY_MENTION, ITEM_TABLE, ITEM_ROW, SUBTOTAL,
  DISCOUNT_BLOCK, MEMBERSHIP_BENEFIT, PACKING_CHARGE, HANDLING_FEE, DELIVERY_CHARGE,
  PLATFORM_FEE, TAX_BLOCK, PAYMENT_ASSERTION, REFUND_BLOCK, LEGAL_ENTITY_BLOCK,
  REGULATORY_BLOCK, TERMS_BLOCK, OTHER_EVIDENCE
- semantic_role: order_identity, party_identity, delivery_evidence, item_detail,
  financial_detail, payment_evidence, legal_detail, regulatory_detail, general_evidence
- financial_role: none, item, charge, discount, tax, total, payment, refund
- entity_type: merchant, legal_entity, delivery_partner
- fact_type: order_id, order_date, merchant_name, legal_entity_name, delivery_partner_name,
  invoice_number, payment_method
- relation_type: REFERENCES_ORDER, ORDERED_FROM, ISSUED_BY, SOLD_BY, DELIVERED_BY,
  CONTAINS_ITEM, HAS_CHARGE, HAS_DISCOUNT, HAS_BENEFIT, HAS_TAX, HAS_TOTAL, PAID_VIA,
  HAS_LEGAL_IDENTIFIER, FORMERLY_KNOWN_AS, MENTIONS_ENTITY
- query_families: order_lookup, item_search, financial_breakdown, merchant_analysis,
  delivery_analysis, tax_analysis, payment_analysis, evidence_replay
- money_scope: order, merchant_invoice, platform_service_invoice, delivery_service_invoice,
  item, payment, refund, unknown
- money_meaning: item_gross, item_net, subtotal, charge, discount, benefit, tax, total,
  payment_assertion, refund, unresolved
- conflict_flags: identifier_conflict, amount_scope_conflict, name_variant, duplicate_evidence,
  missing_context, unresolved_interpretation

Entity candidates use a closed vocabulary.
- Classify a named restaurant, store, or vendor as merchant.
- Classify a named invoice issuer or registered company as legal_entity.
- Classify a named courier or delivery provider as delivery_partner.
- Never emit customer, person, item, address, order, or payment method as an entity candidate.
For any concept that does not fit an allowed type exactly, preserve it in supported narrative
evidence when useful and use an empty array instead of inventing an enum value. Apply this same rule
to every enumerated field: use one listed value exactly or omit the optional candidate.

Only emit entity_candidates that occur in the supplied deterministic entity_mentions. Copy the
entity_type, raw_value_private, and source_chunk_id combination exactly as supplied. The tool schema
restricts this field to those evidence-backed combinations.

Only emit candidate_facts that occur in the supplied deterministic candidate_assertions. Copy the
fact_type, source_chunk_id, and exact source span from those assertions; never infer a new fact from
raw_text_private alone. If a deterministic assertion is not supplied, emit an empty candidate_facts
array for that region.

Only emit relation_candidates whose endpoints and evidence_chunk_ids are supported by the supplied
deterministic graph_candidates. Do not invent a relationship from narrative context alone; use an
empty relation_candidates array when no deterministic graph candidate supports it.

For each entity candidate, copy raw_value_private byte-for-byte from the cited source chunk. The
source_chunk_id must identify the chunk whose raw_text_private contains that exact value. Do not
normalize whitespace, punctuation, spelling, casing, or legal suffixes in raw_value_private.
Omit the candidate when an exact cited substring is unavailable.

Interpret every supplied deterministic money component exactly once. Copy each source_component_id
and its source_chunk_id pairing exactly as supplied, then classify its evidence scope and meaning.
Do not omit, duplicate, combine, or arithmetically reconcile money components.

Perform this coverage checklist before calling the tool:
- The union of source_chunk_ids equals the complete input chunk set exactly.
- Every input source_chunk_id occurs once and only once across all regions.
- Copy every input source_chunk_id into covered_source_chunk_ids in the supplied order.
- Copy every supplied money component ID into covered_money_component_ids in the supplied order.
- Every mail-only bundle must produce at least one region, even when its evidence is sparse.
- No region may contain source chunks from different bundles.

Submit this shape as the submit_agentic_regions tool arguments:
{"batch_id":"UUID","covered_source_chunk_ids":["every input UUID in supplied order"],
"covered_money_component_ids":["every supplied money component UUID in supplied order"],
"regions":[{"bundle_id":"exact supplied bundle ID",
"source_chunk_ids":["UUID"],"chunk_type":"...","semantic_role":"...",
"financial_role":"...","region_title_private":"...","semantic_summary_private":"...",
"embedding_text_private":"...","query_families":["..."],
"candidate_facts":[{"fact_type":"...","raw_value_private":"exact substring",
"normalized_value_private":"...","source_chunk_id":"UUID","source_span_start":0,
"source_span_end":1}],"entity_candidates":[{"entity_type":"...",
"raw_value_private":"exact source substring","source_chunk_id":"UUID"}],
"money_interpretations":[{"source_component_id":"UUID","source_chunk_id":"UUID",
"money_scope":"...","money_meaning":"...","interpretation_private":"..."}],
"relation_candidates":[{"relation_type":"...","subject_private":"ORDER or exact substring",
"object_private":"exact substring","evidence_chunk_ids":["UUID"]}],
"conflict_flags":["..."],"uncertainty_notes_private":["..."]}]}

Evidence batch:
"""

_SYMBOLIC_RELATION_ENDPOINTS = frozenset({"ORDER", "DOCUMENT", "MESSAGE"})


class TokenCounter(Protocol):
    identifier: str

    def count_text(self, text: str) -> int: ...

    def count_messages(self, *, system_prompt: str, user_prompt: str) -> int: ...


class ApproximateGemmaTokenCounter:
    """Conservative local fallback; live runs use the pinned model tokenizer."""

    identifier = "gemma-4-26b-a4b-it-approximate-v1"

    def count_text(self, text: str) -> int:
        ascii_characters = sum(character.isascii() for character in text)
        non_ascii_bytes = len(text.encode()) - ascii_characters
        return ceil(ascii_characters / 3) + non_ascii_bytes

    def count_messages(self, *, system_prompt: str, user_prompt: str) -> int:
        return self.count_text(system_prompt) + self.count_text(user_prompt) + 64


class GemmaTokenizerCounter:
    def __init__(self, tokenizer: Any) -> None:
        self._tokenizer = tokenizer
        self._token_cache: dict[str, int] = {}
        self.identifier = f"{GEMMA_TOKENIZER_REPOSITORY}@{GEMMA_TOKENIZER_REVISION}:tokenizer-json"

    @classmethod
    def from_cache(cls, cache_root: Path) -> GemmaTokenizerCounter:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        try:
            hub = import_module("huggingface_hub")
            tokenizers = import_module("tokenizers")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Install the agent dependency group before exact token planning"
            ) from error
        tokenizer_path = hub.hf_hub_download(
            repo_id=GEMMA_TOKENIZER_REPOSITORY,
            filename="tokenizer.json",
            revision=GEMMA_TOKENIZER_REVISION,
            cache_dir=cache_root,
        )
        return cls(tokenizers.Tokenizer.from_file(tokenizer_path))

    def count_text(self, text: str) -> int:
        cache_key = sha256(text.encode()).hexdigest()
        cached = self._token_cache.get(cache_key)
        if cached is not None:
            return cached
        token_count = len(self._tokenizer.encode(text, add_special_tokens=False).ids)
        self._token_cache[cache_key] = token_count
        return token_count

    def count_messages(self, *, system_prompt: str, user_prompt: str) -> int:
        return self.count_text(system_prompt) + self.count_text(user_prompt) + 64


class AgenticRelationType(StrEnum):
    REFERENCES_ORDER = "REFERENCES_ORDER"
    ORDERED_FROM = "ORDERED_FROM"
    ISSUED_BY = "ISSUED_BY"
    SOLD_BY = "SOLD_BY"
    DELIVERED_BY = "DELIVERED_BY"
    CONTAINS_ITEM = "CONTAINS_ITEM"
    HAS_CHARGE = "HAS_CHARGE"
    HAS_DISCOUNT = "HAS_DISCOUNT"
    HAS_BENEFIT = "HAS_BENEFIT"
    HAS_TAX = "HAS_TAX"
    HAS_TOTAL = "HAS_TOTAL"
    PAID_VIA = "PAID_VIA"
    HAS_LEGAL_IDENTIFIER = "HAS_LEGAL_IDENTIFIER"
    FORMERLY_KNOWN_AS = "FORMERLY_KNOWN_AS"
    MENTIONS_ENTITY = "MENTIONS_ENTITY"


class AgenticMoneyScope(StrEnum):
    ORDER = "order"
    MERCHANT_INVOICE = "merchant_invoice"
    PLATFORM_SERVICE_INVOICE = "platform_service_invoice"
    DELIVERY_SERVICE_INVOICE = "delivery_service_invoice"
    ITEM = "item"
    PAYMENT = "payment"
    REFUND = "refund"
    UNKNOWN = "unknown"


class AgenticMoneyMeaning(StrEnum):
    ITEM_GROSS = "item_gross"
    ITEM_NET = "item_net"
    SUBTOTAL = "subtotal"
    CHARGE = "charge"
    DISCOUNT = "discount"
    BENEFIT = "benefit"
    TAX = "tax"
    TOTAL = "total"
    PAYMENT_ASSERTION = "payment_assertion"
    REFUND = "refund"
    UNRESOLVED = "unresolved"


class AgenticConflictFlag(StrEnum):
    IDENTIFIER_CONFLICT = "identifier_conflict"
    AMOUNT_SCOPE_CONFLICT = "amount_scope_conflict"
    NAME_VARIANT = "name_variant"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    MISSING_CONTEXT = "missing_context"
    UNRESOLVED_INTERPRETATION = "unresolved_interpretation"


class AgenticBatchPolicy(ContractModel):
    target_input_tokens: int = Field(default=64_000, ge=1_000)
    max_input_tokens: int = Field(default=80_000, ge=2_000)
    max_completion_tokens: int = Field(default=24_000, ge=1_000)
    context_window_tokens: int = Field(default=CLOUDFLARE_CONTEXT_WINDOW_TOKENS, ge=4_000)
    max_chunks: int = Field(default=512, ge=2)
    max_bundles: int = Field(default=6, ge=1)
    minimum_chunks: int = Field(default=2, ge=2)
    max_estimated_output_tokens: int | None = Field(default=None, ge=1_000)

    @model_validator(mode="after")
    def targets_fit_hard_limits(self) -> AgenticBatchPolicy:
        if self.target_input_tokens > self.max_input_tokens:
            raise ValueError("target_input_tokens cannot exceed max_input_tokens")
        if self.max_input_tokens + self.max_completion_tokens >= self.context_window_tokens:
            raise ValueError("input and completion budgets must leave context-window headroom")
        if self.minimum_chunks > self.max_chunks:
            raise ValueError("minimum_chunks cannot exceed max_chunks")
        return self


class AgenticEvidenceBundle(ContractModel):
    bundle_id: str = Field(min_length=1)
    cohort_key: str = Field(min_length=1)
    mail_only: bool
    chunks: tuple[EvidenceChunk, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def chunks_are_unique_and_accepted(self) -> AgenticEvidenceBundle:
        chunk_ids = tuple(chunk.chunk_id for chunk in self.chunks)
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("bundle chunks must be unique")
        if any(chunk.validation_status is not ValidationStatus.ACCEPTED for chunk in self.chunks):
            raise ValueError("agentic input requires accepted deterministic chunks")
        return self


class AgenticBatch(ContractModel):
    batch_id: UUID
    contract_version: str = Field(default=AGENTIC_CONTRACT_VERSION, min_length=1)
    cohort_key: str = Field(min_length=1)
    bundle_ids: tuple[str, ...] = Field(min_length=1)
    chunk_bundle_ids: tuple[str, ...] = Field(min_length=2)
    chunks: tuple[EvidenceChunk, ...] = Field(min_length=2)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    estimated_input_tokens: int = Field(ge=1)
    token_counter_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def batch_members_are_aligned(self) -> AgenticBatch:
        if len(self.chunk_bundle_ids) != len(self.chunks):
            raise ValueError("chunk_bundle_ids must align with chunks")
        if tuple(dict.fromkeys(self.chunk_bundle_ids)) != self.bundle_ids:
            raise ValueError("bundle_ids must match first-seen chunk bundle IDs")
        chunk_ids = tuple(chunk.chunk_id for chunk in self.chunks)
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("batch chunks must be unique")
        expected_hash = _batch_input_hash(self.chunk_bundle_ids, self.chunks)
        if self.input_sha256 != expected_hash:
            raise ValueError("input_sha256 must match batch evidence")
        return self


class AgenticBatchPlan(ContractModel):
    policy: AgenticBatchPolicy
    bundles: int = Field(ge=0)
    input_chunks: int = Field(ge=0)
    batches: tuple[AgenticBatch, ...]
    quarantined_chunk_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def planned_chunks_are_unique(self) -> AgenticBatchPlan:
        planned = tuple(chunk.chunk_id for batch in self.batches for chunk in batch.chunks)
        if len(planned) != len(set(planned)):
            raise ValueError("a source chunk cannot appear in multiple agentic batches")
        if set(planned) & set(self.quarantined_chunk_ids):
            raise ValueError("planned and quarantined chunks must be disjoint")
        if len(planned) + len(self.quarantined_chunk_ids) != self.input_chunks:
            raise ValueError("every input chunk must be planned or quarantined")
        return self


class AgenticEntityCandidate(ContractModel):
    entity_type: EntityType
    raw_value_private: str = Field(repr=False, min_length=1, max_length=512)
    source_chunk_id: UUID


class AgenticFactCandidate(ContractModel):
    fact_type: CandidateFactType
    raw_value_private: str = Field(repr=False, min_length=1, max_length=512)
    normalized_value_private: str = Field(repr=False, min_length=1, max_length=512)
    source_chunk_id: UUID
    source_span_start: int = Field(ge=0)
    source_span_end: int = Field(gt=0)

    @model_validator(mode="after")
    def source_span_is_ordered(self) -> AgenticFactCandidate:
        if self.source_span_end <= self.source_span_start:
            raise ValueError("source_span_end must exceed source_span_start")
        return self


class AgenticMoneyInterpretation(ContractModel):
    source_component_id: UUID
    source_chunk_id: UUID
    money_scope: AgenticMoneyScope
    money_meaning: AgenticMoneyMeaning
    interpretation_private: str = Field(repr=False, min_length=1, max_length=800)


class AgenticRelationCandidate(ContractModel):
    relation_type: AgenticRelationType
    subject_private: str = Field(repr=False, min_length=1, max_length=512)
    object_private: str = Field(repr=False, min_length=1, max_length=512)
    evidence_chunk_ids: tuple[UUID, ...] = Field(min_length=1, max_length=64)


class AgenticRegionProposal(ContractModel):
    bundle_id: str = Field(min_length=1)
    source_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    chunk_type: ChunkType
    semantic_role: SemanticRole
    financial_role: FinancialRole
    region_title_private: str = Field(repr=False, min_length=1, max_length=160)
    semantic_summary_private: str = Field(repr=False, min_length=1, max_length=1_200)
    embedding_text_private: str = Field(repr=False, min_length=1, max_length=1_600)
    query_families: tuple[QueryFamily, ...] = Field(min_length=1, max_length=8)
    candidate_facts: tuple[AgenticFactCandidate, ...] = Field(default=(), max_length=64)
    entity_candidates: tuple[AgenticEntityCandidate, ...] = Field(default=(), max_length=32)
    money_interpretations: tuple[AgenticMoneyInterpretation, ...] = Field(default=(), max_length=64)
    relation_candidates: tuple[AgenticRelationCandidate, ...] = Field(default=(), max_length=32)
    conflict_flags: tuple[AgenticConflictFlag, ...] = Field(default=(), max_length=6)
    uncertainty_notes_private: tuple[str, ...] = Field(default=(), repr=False, max_length=8)


class AgenticModelResponse(ContractModel):
    batch_id: UUID
    covered_source_chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    covered_money_component_ids: tuple[UUID, ...]
    regions: tuple[AgenticRegionProposal, ...] = Field(min_length=1)


@cache
def _base_agentic_tool_parameters() -> dict[str, Any]:
    return AgenticModelResponse.model_json_schema()


def _agentic_tool_definition(
    *,
    batch_id: UUID,
    bundle_ids: Sequence[str],
    chunks: Sequence[EvidenceChunk],
) -> dict[str, object]:
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
    parameters = deepcopy(_base_agentic_tool_parameters())
    properties = parameters["properties"]
    properties["batch_id"]["const"] = str(batch_id)
    properties["covered_source_chunk_ids"]["const"] = [str(chunk_id) for chunk_id in chunk_ids]
    money_components = tuple(
        (component.component_id, chunk.chunk_id)
        for chunk in chunks
        for component in chunk.candidate_money_components
    )
    properties["covered_money_component_ids"]["const"] = [
        str(component_id) for component_id, _ in money_components
    ]
    properties["regions"]["maxItems"] = len(chunk_ids)
    region_properties = parameters["$defs"]["AgenticRegionProposal"]["properties"]
    region_properties["bundle_id"]["enum"] = list(bundle_ids)
    source_ids_schema = region_properties["source_chunk_ids"]
    source_ids_schema["uniqueItems"] = True
    source_ids_schema["maxItems"] = len(chunk_ids)
    source_ids_schema["items"]["enum"] = [str(chunk_id) for chunk_id in chunk_ids]
    allowed_entities = tuple(
        dict.fromkeys(
            (
                mention.entity_type.value,
                mention.raw_value_private,
                str(chunk.chunk_id),
            )
            for chunk in chunks
            for mention in chunk.entity_mentions
        )
    )
    entity_candidates_schema = region_properties["entity_candidates"]
    if allowed_entities:
        entity_definition = parameters["$defs"]["AgenticEntityCandidate"]
        entity_definition["anyOf"] = [
            {
                "properties": {
                    "entity_type": {"const": entity_type},
                    "raw_value_private": {"const": raw_value},
                    "source_chunk_id": {"const": source_chunk_id},
                },
                "required": ["entity_type", "raw_value_private", "source_chunk_id"],
            }
            for entity_type, raw_value, source_chunk_id in allowed_entities
        ]
    else:
        entity_candidates_schema["maxItems"] = 0
    money_interpretations_schema = region_properties["money_interpretations"]
    if money_components:
        money_interpretations_schema["maxItems"] = min(64, len(money_components))
        money_definition = parameters["$defs"]["AgenticMoneyInterpretation"]
        money_properties = money_definition["properties"]
        money_properties["source_component_id"]["enum"] = [
            str(component_id) for component_id, _ in money_components
        ]
        money_properties["source_chunk_id"]["enum"] = [
            str(source_chunk_id)
            for source_chunk_id in dict.fromkeys(
                source_chunk_id for _, source_chunk_id in money_components
            )
        ]
    else:
        money_interpretations_schema["maxItems"] = 0
    return {
        "name": AGENTIC_TOOL_NAME,
        "description": (
            "Submit the complete bundle-isolated, graph-ready semantic region proposal."
        ),
        "parameters": parameters,
    }


def _serialized_agentic_tool_definition(assignments: Sequence[_ChunkAssignment]) -> str:
    return json.dumps(
        _agentic_tool_definition(
            batch_id=_batch_identity(assignments),
            bundle_ids=tuple(dict.fromkeys(item.bundle_id for item in assignments)),
            chunks=tuple(item.chunk for item in assignments),
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@cache
def _serialized_base_agentic_tool_definition() -> str:
    return json.dumps(
        {
            "name": AGENTIC_TOOL_NAME,
            "description": (
                "Submit the complete bundle-isolated, graph-ready semantic region proposal."
            ),
            "parameters": _base_agentic_tool_parameters(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class AgenticBatchResult(ContractModel):
    batch_id: UUID
    model: str = Field(min_length=1)
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    regions: tuple[AgenticRegionProposal, ...]
    validation_status: ValidationStatus
    quarantine_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def result_state_is_atomic(self) -> AgenticBatchResult:
        if self.validation_status is ValidationStatus.ACCEPTED:
            if not self.regions or self.quarantine_reasons or self.response_sha256 is None:
                raise ValueError("accepted agentic results require regions and a response hash")
        elif self.regions or not self.quarantine_reasons:
            raise ValueError("quarantined agentic results require reasons and no regions")
        return self


class AgenticRunSummary(ContractModel):
    planned_batches: int = Field(ge=0)
    attempted_batches: int = Field(ge=0)
    accepted_batches: int = Field(ge=0)
    quarantined_batches: int = Field(ge=0)
    remaining_batches: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class StreamingTransportResponse:
    status_code: int
    headers: Mapping[str, str]
    content: str = field(repr=False)
    finish_reason: str | None
    usage: Mapping[str, object]
    completed: bool
    tool_name: str | None = None


class StreamingTransport(Protocol):
    def post_sse(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> StreamingTransportResponse: ...


class CloudflareWorkersAIError(RuntimeError):
    """Safe operational error that never includes private request or response content."""

    def __init__(self, message: str, *, code: str = "unknown") -> None:
        super().__init__(message)
        normalized_code = code.strip().lower()
        self.code = (
            normalized_code
            if normalized_code
            and all(character.isalnum() or character == "_" for character in normalized_code)
            else "unknown"
        )


def _numeric_provider_error_code(event: Mapping[str, object]) -> str | None:
    candidates: list[object] = [event]
    for key in ("error", "errors"):
        value = event.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            candidates.extend(value)
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        raw_code = candidate.get("code")
        if isinstance(raw_code, int) and not isinstance(raw_code, bool):
            return str(raw_code)
        if isinstance(raw_code, str) and raw_code.isascii() and raw_code.isdigit():
            return raw_code[:12]
    return None


def _decode_cloudflare_sse(
    lines: Iterable[bytes],
    *,
    deadline_monotonic: float | None = None,
) -> tuple[str, str | None, Mapping[str, object], bool, str | None]:
    content_parts: list[str] = []
    tool_argument_parts: dict[int, list[str]] = defaultdict(list)
    tool_names: dict[int, str] = {}
    finish_reason: str | None = None
    usage: Mapping[str, object] = {}
    completed = False
    data_lines: list[str] = []

    def consume_event(data: str) -> None:
        nonlocal completed, finish_reason, usage
        if data == "[DONE]":
            completed = True
            return
        try:
            event = json.loads(data)
        except json.JSONDecodeError as error:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI returned an invalid SSE event",
                code="invalid_sse_event",
            ) from error
        if not isinstance(event, dict):
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI returned an invalid SSE event",
                code="invalid_sse_event",
            )
        if event.get("success") is False or event.get("error") or event.get("errors"):
            provider_code = _numeric_provider_error_code(event)
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI rejected the stream",
                code=(
                    f"stream_rejected_cf_{provider_code}"
                    if provider_code is not None
                    else "stream_rejected"
                ),
            )
        event_usage = event.get("usage")
        if isinstance(event_usage, Mapping):
            usage = cast(Mapping[str, object], event_usage)
        choices = event.get("choices")
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
            return
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            reason = choice.get("finish_reason")
            if isinstance(reason, str):
                finish_reason = reason
            delta = choice.get("delta")
            if not isinstance(delta, Mapping):
                continue
            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, Sequence) and not isinstance(tool_calls, (str, bytes)):
                for tool_call in tool_calls:
                    if not isinstance(tool_call, Mapping):
                        continue
                    raw_index = tool_call.get("index", 0)
                    index = raw_index if isinstance(raw_index, int) else 0
                    function = tool_call.get("function")
                    if not isinstance(function, Mapping):
                        continue
                    name = function.get("name")
                    if isinstance(name, str) and name:
                        tool_names[index] = name
                    arguments = function.get("arguments")
                    if arguments is None:
                        continue
                    if not isinstance(arguments, str):
                        raise CloudflareWorkersAIError(
                            "Cloudflare Workers AI returned invalid tool arguments",
                            code="invalid_tool_arguments",
                        )
                    tool_argument_parts[index].append(arguments)
            content = delta.get("content")
            if content is None:
                continue
            if not isinstance(content, str):
                raise CloudflareWorkersAIError(
                    "Cloudflare Workers AI returned invalid streamed content",
                    code="invalid_stream_content",
                )
            content_parts.append(content)

    for raw_line in lines:
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI stream exceeded its deadline",
                code="stream_deadline_exceeded",
            )
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as error:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI returned invalid SSE encoding",
                code="invalid_sse_encoding",
            ) from error
        if not line:
            if data_lines:
                consume_event("\n".join(data_lines))
                data_lines.clear()
            continue
        if line.startswith(":"):
            continue
        if line == "data":
            data_lines.append("")
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))
    if data_lines:
        consume_event("\n".join(data_lines))
    answer_content = "".join(content_parts)
    if tool_argument_parts:
        if len(tool_argument_parts) != 1:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI returned multiple tool calls",
                code="multiple_tool_calls",
            )
        if answer_content.strip():
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI mixed content with a required tool call",
                code="mixed_content_tool_call",
            )
        tool_index = next(iter(tool_argument_parts))
        return (
            "".join(tool_argument_parts[tool_index]),
            finish_reason,
            usage,
            completed,
            tool_names.get(tool_index),
        )
    return answer_content, finish_reason, usage, completed, None


class UrllibSseTransport:
    def post_sse(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> StreamingTransportResponse:
        request = Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=headers,
            method="POST",
        )
        try:
            deadline_monotonic = time.monotonic() + timeout_seconds
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = response.status
                response_headers = dict(response.headers.items())
                content_type = response.headers.get("Content-Type", "")
                if not content_type.lower().startswith("text/event-stream"):
                    raise CloudflareWorkersAIError(
                        "Cloudflare Workers AI returned an unexpected content type",
                        code="unexpected_content_type",
                    )
                content, finish_reason, usage, completed, tool_name = _decode_cloudflare_sse(
                    response,
                    deadline_monotonic=deadline_monotonic,
                )
        except HTTPError as error:
            return StreamingTransportResponse(
                status_code=error.code,
                headers=dict(error.headers.items()) if error.headers is not None else {},
                content="",
                finish_reason=None,
                usage={},
                completed=False,
                tool_name=None,
            )
        except TimeoutError as error:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI network request timed out",
                code="network_timeout",
            ) from error
        except URLError as error:
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI network request failed",
                code="network_request_failed",
            ) from error
        return StreamingTransportResponse(
            status_code=status_code,
            headers=response_headers,
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            completed=completed,
            tool_name=tool_name,
        )


@dataclass(frozen=True, slots=True)
class _ChunkAssignment:
    bundle_id: str
    cohort_key: str
    chunk: EvidenceChunk


@dataclass(frozen=True, slots=True)
class _PackingUnit:
    assignments: tuple[_ChunkAssignment, ...]


def _chunk_prompt_record(assignment: _ChunkAssignment) -> dict[str, object]:
    chunk = assignment.chunk
    record = cast(dict[str, object], chunk.model_dump(mode="json"))
    record["bundle_id"] = assignment.bundle_id
    return record


def _batch_identity(assignments: Sequence[_ChunkAssignment]) -> UUID:
    material = "|".join(
        f"{assignment.bundle_id}:{assignment.chunk.chunk_id}" for assignment in assignments
    )
    return uuid5(
        NAMESPACE_URL,
        f"lunarbit:agentic-batch:{AGENTIC_CONTRACT_VERSION}:{material}",
    )


def _batch_input_hash(
    chunk_bundle_ids: Sequence[str],
    chunks: Sequence[EvidenceChunk],
) -> str:
    records = [
        _chunk_prompt_record(_ChunkAssignment(bundle_id=bundle_id, cohort_key="", chunk=chunk))
        for bundle_id, chunk in zip(chunk_bundle_ids, chunks, strict=True)
    ]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _render_assignments(assignments: Sequence[_ChunkAssignment]) -> str:
    batch_id = _batch_identity(assignments)
    bundle_ids = tuple(dict.fromkeys(assignment.bundle_id for assignment in assignments))
    evidence = {
        "batch_id": str(batch_id),
        "contract_version": AGENTIC_CONTRACT_VERSION,
        "cohort_key": assignments[0].cohort_key,
        "bundles": [
            {
                "bundle_id": bundle_id,
                "chunks": [
                    _chunk_prompt_record(assignment)
                    for assignment in assignments
                    if assignment.bundle_id == bundle_id
                ],
            }
            for bundle_id in bundle_ids
        ],
    }
    return _USER_INSTRUCTIONS + json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _count_input_tokens(
    assignments: Sequence[_ChunkAssignment],
    *,
    token_counter: TokenCounter,
    exact_tool_schema: bool = False,
) -> int:
    record_tokens = sum(
        token_counter.count_text(
            json.dumps(
                _chunk_prompt_record(assignment),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        for assignment in assignments
    )
    bundle_count = len({assignment.bundle_id for assignment in assignments})
    if exact_tool_schema:
        tool_tokens = token_counter.count_text(_serialized_agentic_tool_definition(assignments))
    else:
        tool_tokens = (
            token_counter.count_text(_serialized_base_agentic_tool_definition())
            + len(assignments) * 96
            + bundle_count * 64
            + 512
        )
    return (
        token_counter.count_text(_SYSTEM_PROMPT)
        + token_counter.count_text(_USER_INSTRUCTIONS)
        + tool_tokens
        + record_tokens
        + len(assignments) * 12
        + bundle_count * 64
        + 256
    )


def _estimate_output_tokens(assignments: Sequence[_ChunkAssignment]) -> int:
    """Conservatively budget the typed graph payload before making a model call."""
    return 1_200 + sum(
        220
        + len(assignment.chunk.candidate_assertions) * 180
        + len(assignment.chunk.entity_mentions) * 180
        + len(assignment.chunk.candidate_money_components) * 500
        + len(assignment.chunk.graph_candidates) * 120
        + len(assignment.chunk.query_families) * 50
        for assignment in assignments
    )


def _make_batch(
    assignments: Sequence[_ChunkAssignment],
    *,
    token_counter: TokenCounter,
) -> AgenticBatch:
    assignment_tuple = tuple(assignments)
    bundle_ids = tuple(dict.fromkeys(item.bundle_id for item in assignment_tuple))
    chunks = tuple(item.chunk for item in assignment_tuple)
    chunk_bundle_ids = tuple(item.bundle_id for item in assignment_tuple)
    return AgenticBatch(
        batch_id=_batch_identity(assignment_tuple),
        cohort_key=assignment_tuple[0].cohort_key,
        bundle_ids=bundle_ids,
        chunk_bundle_ids=chunk_bundle_ids,
        chunks=chunks,
        input_sha256=_batch_input_hash(chunk_bundle_ids, chunks),
        estimated_input_tokens=_count_input_tokens(
            assignment_tuple,
            token_counter=token_counter,
            exact_tool_schema=True,
        ),
        token_counter_id=token_counter.identifier,
    )


def render_agentic_user_prompt(batch: AgenticBatch) -> str:
    assignments = tuple(
        _ChunkAssignment(
            bundle_id=bundle_id,
            cohort_key=batch.cohort_key,
            chunk=chunk,
        )
        for bundle_id, chunk in zip(batch.chunk_bundle_ids, batch.chunks, strict=True)
    )
    rendered = _render_assignments(assignments)
    if _batch_identity(assignments) != batch.batch_id:
        raise ValueError("batch ID does not match prompt assignments")
    return rendered


def _table_key(chunk: EvidenceChunk) -> tuple[str, str] | None:
    if chunk.chunk_type is ChunkType.ITEM_TABLE and chunk.table_id is not None:
        return chunk.source_id, chunk.table_id
    if chunk.chunk_type is ChunkType.ITEM_ROW and chunk.parent_region_id is not None:
        return chunk.source_id, chunk.parent_region_id
    return None


def _bundle_units(bundle: AgenticEvidenceBundle) -> tuple[_PackingUnit, ...]:
    table_members: dict[tuple[str, str], list[_ChunkAssignment]] = defaultdict(list)
    assignments = tuple(
        _ChunkAssignment(
            bundle_id=bundle.bundle_id,
            cohort_key=bundle.cohort_key,
            chunk=chunk,
        )
        for chunk in bundle.chunks
    )
    for assignment in assignments:
        key = _table_key(assignment.chunk)
        if key is not None:
            table_members[key].append(assignment)

    units: list[_PackingUnit] = []
    emitted_tables: set[tuple[str, str]] = set()
    for assignment in assignments:
        key = _table_key(assignment.chunk)
        if key is None:
            units.append(_PackingUnit(assignments=(assignment,)))
        elif key not in emitted_tables:
            units.append(_PackingUnit(assignments=tuple(table_members[key])))
            emitted_tables.add(key)
    return tuple(units)


def _fits(
    assignments: Sequence[_ChunkAssignment],
    *,
    policy: AgenticBatchPolicy,
    token_counter: TokenCounter,
) -> bool:
    return (
        len(assignments) <= policy.max_chunks
        and len({assignment.bundle_id for assignment in assignments}) <= policy.max_bundles
        and _count_input_tokens(assignments, token_counter=token_counter) <= policy.max_input_tokens
        and (
            policy.max_estimated_output_tokens is None
            or _estimate_output_tokens(assignments) <= policy.max_estimated_output_tokens
        )
    )


def _split_oversized_unit(
    unit: _PackingUnit,
    *,
    policy: AgenticBatchPolicy,
    token_counter: TokenCounter,
) -> tuple[_PackingUnit, ...]:
    if _fits(unit.assignments, policy=policy, token_counter=token_counter):
        return (unit,)
    split: list[_PackingUnit] = []
    current: list[_ChunkAssignment] = []
    for assignment in unit.assignments:
        candidate = (*current, assignment)
        if current and not _fits(candidate, policy=policy, token_counter=token_counter):
            split.append(_PackingUnit(assignments=tuple(current)))
            current = [assignment]
        else:
            current.append(assignment)
    if current:
        split.append(_PackingUnit(assignments=tuple(current)))
    return tuple(split)


def _pack_units(
    units: Sequence[_PackingUnit],
    *,
    policy: AgenticBatchPolicy,
    token_counter: TokenCounter,
) -> tuple[tuple[_ChunkAssignment, ...], ...]:
    expanded = tuple(
        split_unit
        for unit in units
        for split_unit in _split_oversized_unit(
            unit,
            policy=policy,
            token_counter=token_counter,
        )
    )
    packed: list[tuple[_ChunkAssignment, ...]] = []
    current: list[_ChunkAssignment] = []
    for unit in expanded:
        candidate = (*current, *unit.assignments)
        reached_target = (
            len(current) >= policy.minimum_chunks
            and _count_input_tokens(current, token_counter=token_counter)
            >= policy.target_input_tokens
        )
        if current and (
            reached_target or not _fits(candidate, policy=policy, token_counter=token_counter)
        ):
            packed.append(tuple(current))
            current = list(unit.assignments)
        else:
            current.extend(unit.assignments)
    if current:
        packed.append(tuple(current))

    if len(packed) >= 2 and len(packed[-1]) < policy.minimum_chunks:
        candidate = (*packed[-2], *packed[-1])
        if _fits(candidate, policy=policy, token_counter=token_counter):
            packed[-2:] = [candidate]
        else:
            previous_bundle_counts = Counter(assignment.bundle_id for assignment in packed[-2])
            transfer_count = policy.minimum_chunks - len(packed[-1])
            transferred = packed[-2][-transfer_count:]
            rebalanced_previous = packed[-2][:-transfer_count]
            rebalanced_last = (*transferred, *packed[-1])
            transfers_are_complete_singletons = all(
                previous_bundle_counts[assignment.bundle_id] == 1 for assignment in transferred
            )
            if (
                transfers_are_complete_singletons
                and len(rebalanced_previous) >= policy.minimum_chunks
                and _fits(
                    rebalanced_previous,
                    policy=policy,
                    token_counter=token_counter,
                )
                and _fits(
                    rebalanced_last,
                    policy=policy,
                    token_counter=token_counter,
                )
            ):
                packed[-2:] = [rebalanced_previous, rebalanced_last]
    return tuple(packed)


def plan_agentic_batches(
    bundles: Sequence[AgenticEvidenceBundle],
    *,
    policy: AgenticBatchPolicy | None = None,
    token_counter: TokenCounter | None = None,
) -> AgenticBatchPlan:
    selected_policy = policy or AgenticBatchPolicy()
    selected_token_counter = token_counter or ApproximateGemmaTokenCounter()
    ordered_bundles = tuple(sorted(bundles, key=lambda bundle: bundle.bundle_id))
    all_chunk_ids = tuple(chunk.chunk_id for bundle in ordered_bundles for chunk in bundle.chunks)
    if len(all_chunk_ids) != len(set(all_chunk_ids)):
        raise ValueError("agentic bundles contain duplicate chunks")

    packed: list[tuple[_ChunkAssignment, ...]] = []
    bundles_by_cohort: dict[str, list[AgenticEvidenceBundle]] = defaultdict(list)
    for bundle in ordered_bundles:
        bundles_by_cohort[bundle.cohort_key].append(bundle)
    for cohort in sorted(bundles_by_cohort):
        units: list[_PackingUnit] = []
        for bundle in bundles_by_cohort[cohort]:
            bundle_units = _bundle_units(bundle)
            complete_bundle = _PackingUnit(
                assignments=tuple(
                    assignment for unit in bundle_units for assignment in unit.assignments
                )
            )
            if _fits(
                complete_bundle.assignments,
                policy=selected_policy,
                token_counter=selected_token_counter,
            ):
                units.append(complete_bundle)
            else:
                units.extend(bundle_units)
        packed.extend(
            _pack_units(
                units,
                policy=selected_policy,
                token_counter=selected_token_counter,
            )
        )

    accepted_batches: list[AgenticBatch] = []
    quarantined: list[UUID] = []
    for assignments in packed:
        if len(assignments) < selected_policy.minimum_chunks or not _fits(
            assignments,
            policy=selected_policy,
            token_counter=selected_token_counter,
        ):
            quarantined.extend(assignment.chunk.chunk_id for assignment in assignments)
            continue
        accepted_batches.append(_make_batch(assignments, token_counter=selected_token_counter))

    return AgenticBatchPlan(
        policy=selected_policy,
        bundles=len(ordered_bundles),
        input_chunks=len(all_chunk_ids),
        batches=tuple(accepted_batches),
        quarantined_chunk_ids=tuple(quarantined),
    )


def _extract_json_object(raw_response: str) -> tuple[Mapping[str, object], str]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(raw_response):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw_response[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "batch_id" in candidate and "regions" in candidate:
            canonical = json.dumps(
                candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            return cast(dict[str, object], candidate), canonical
    raise ValueError("model response does not contain the expected JSON object")


def _quarantined_result(
    batch: AgenticBatch,
    reason: str | Sequence[str],
) -> AgenticBatchResult:
    reasons = (reason,) if isinstance(reason, str) else tuple(reason)
    return AgenticBatchResult(
        batch_id=batch.batch_id,
        model=CLOUDFLARE_MODEL,
        regions=(),
        validation_status=ValidationStatus.QUARANTINED,
        quarantine_reasons=reasons,
    )


def _safe_schema_failure_reasons(error: ValidationError) -> tuple[str, ...]:
    failures = error.errors(include_url=False, include_context=False, include_input=False)
    if not failures:
        return ("invalid_model_schema",)
    reasons: list[str] = []
    for failure in failures:
        failure_type = str(failure.get("type", "unknown")).replace(":", "_")
        raw_location = failure.get("loc", ())
        location = ".".join(str(part) for part in raw_location) or "root"
        reason = f"invalid_model_schema:{failure_type}:{location}"
        if reason not in reasons:
            reasons.append(reason)
        if len(reasons) == 20:
            break
    return tuple(reasons)


def validate_agentic_response(batch: AgenticBatch, raw_response: str) -> AgenticBatchResult:
    try:
        candidate, canonical = _extract_json_object(raw_response)
    except ValueError:
        return _quarantined_result(batch, "invalid_model_json")
    try:
        response = AgenticModelResponse.model_validate_json(
            json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        )
    except ValidationError as error:
        return _quarantined_result(batch, _safe_schema_failure_reasons(error))
    if response.batch_id != batch.batch_id:
        return _quarantined_result(batch, "batch_id_mismatch")

    expected_ids = tuple(chunk.chunk_id for chunk in batch.chunks)
    if response.covered_source_chunk_ids != expected_ids:
        return _quarantined_result(batch, "coverage_manifest_mismatch")
    proposed_ids = tuple(
        chunk_id for region in response.regions for chunk_id in region.source_chunk_ids
    )
    if Counter(proposed_ids) != Counter(expected_ids):
        return _quarantined_result(batch, "incomplete_batch_coverage")

    expected_money_ids = tuple(
        component.component_id
        for chunk in batch.chunks
        for component in chunk.candidate_money_components
    )
    if response.covered_money_component_ids != expected_money_ids:
        return _quarantined_result(batch, "money_coverage_manifest_mismatch")
    proposed_money_ids = tuple(
        interpretation.source_component_id
        for region in response.regions
        for interpretation in region.money_interpretations
    )
    if Counter(proposed_money_ids) != Counter(expected_money_ids):
        return _quarantined_result(batch, "incomplete_money_component_coverage")

    chunks_by_id = {chunk.chunk_id: chunk for chunk in batch.chunks}
    bundles_by_chunk_id = dict(zip(expected_ids, batch.chunk_bundle_ids, strict=True))
    for region in response.regions:
        region_ids = set(region.source_chunk_ids)
        region_bundle_ids = {bundles_by_chunk_id[chunk_id] for chunk_id in region_ids}
        if len(region_bundle_ids) != 1:
            return _quarantined_result(batch, "cross_bundle_region")
        if region.bundle_id != next(iter(region_bundle_ids)):
            return _quarantined_result(batch, "bundle_id_mismatch")
        for fact in region.candidate_facts:
            source = chunks_by_id.get(fact.source_chunk_id)
            if (
                source is None
                or fact.source_chunk_id not in region_ids
                or fact.source_span_end > len(source.raw_text_private)
                or source.raw_text_private[fact.source_span_start : fact.source_span_end]
                != fact.raw_value_private
            ):
                return _quarantined_result(batch, "unsupported_fact_candidate")
        for entity in region.entity_candidates:
            source = chunks_by_id.get(entity.source_chunk_id)
            if (
                source is None
                or entity.source_chunk_id not in region_ids
                or entity.raw_value_private not in source.raw_text_private
            ):
                return _quarantined_result(batch, "unsupported_entity_candidate")
        for interpretation in region.money_interpretations:
            source = chunks_by_id.get(interpretation.source_chunk_id)
            if (
                source is None
                or interpretation.source_chunk_id not in region_ids
                or interpretation.source_component_id
                not in {component.component_id for component in source.candidate_money_components}
            ):
                return _quarantined_result(batch, "unsupported_money_interpretation")
        for relation in region.relation_candidates:
            if not set(relation.evidence_chunk_ids) <= region_ids:
                return _quarantined_result(batch, "unsupported_relation_candidate")
            evidence = [chunks_by_id.get(chunk_id) for chunk_id in relation.evidence_chunk_ids]
            if any(chunk is None for chunk in evidence):
                return _quarantined_result(batch, "unsupported_relation_candidate")
            endpoints = (relation.subject_private, relation.object_private)
            if any(
                endpoint not in _SYMBOLIC_RELATION_ENDPOINTS
                and not any(
                    endpoint in chunk.raw_text_private for chunk in evidence if chunk is not None
                )
                for endpoint in endpoints
            ):
                return _quarantined_result(batch, "unsupported_relation_candidate")

    return AgenticBatchResult(
        batch_id=batch.batch_id,
        model=CLOUDFLARE_MODEL,
        response_sha256=sha256(canonical.encode()).hexdigest(),
        regions=response.regions,
        validation_status=ValidationStatus.ACCEPTED,
    )


class CloudflareWorkersAIClient:
    def __init__(
        self,
        *,
        account_id: str,
        auth_token: str,
        transport: StreamingTransport | None = None,
        timeout_seconds: float = CLOUDFLARE_STREAM_TIMEOUT_SECONDS,
        max_attempts: int = 3,
        max_completion_tokens: int = 24_000,
    ) -> None:
        if not account_id.strip() or not auth_token.strip():
            raise ValueError("Cloudflare account ID and auth token are required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._account_id = account_id.strip()
        self._auth_token = auth_token.strip()
        self._transport = transport or UrllibSseTransport()
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_completion_tokens = max_completion_tokens

    @classmethod
    def from_environment(
        cls,
        *,
        max_completion_tokens: int = 24_000,
        timeout_seconds: float = CLOUDFLARE_STREAM_TIMEOUT_SECONDS,
    ) -> CloudflareWorkersAIClient:
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        auth_token = os.environ.get("CLOUDFLARE_AUTH_TOKEN") or os.environ.get(
            "tryCLOUDFLARE_AUTH_TOKEN",  # noqa: SIM112
            "",
        )
        if not account_id or not auth_token:
            raise CloudflareWorkersAIError(
                "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AUTH_TOKEN before live execution",
                code="missing_credentials",
            )
        return cls(
            account_id=account_id,
            auth_token=auth_token,
            max_completion_tokens=max_completion_tokens,
            timeout_seconds=timeout_seconds,
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(account_id=<redacted>, model={CLOUDFLARE_MODEL!r}, "
            f"timeout_seconds={self._timeout_seconds!r})"
        )

    def _request(self, batch: AgenticBatch) -> StreamingTransportResponse:
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self._account_id}/ai/run/{CLOUDFLARE_MODEL}"
        )
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload: dict[str, object] = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": render_agentic_user_prompt(batch)},
            ],
            "max_completion_tokens": self._max_completion_tokens,
            "temperature": 0,
            "seed": 42,
            "store": False,
            "stream": True,
            "reasoning_effort": CLOUDFLARE_REASONING_EFFORT,
            "chat_template_kwargs": {"enable_thinking": False},
            "tools": [
                _agentic_tool_definition(
                    batch_id=batch.batch_id,
                    bundle_ids=batch.bundle_ids,
                    chunks=batch.chunks,
                )
            ],
            "tool_choice": "required",
            "parallel_tool_calls": False,
        }
        response: StreamingTransportResponse | None = None
        for attempt in range(1, self._max_attempts + 1):
            response = self._transport.post_sse(
                url=url,
                headers=headers,
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )
            if response.status_code != 429 and response.status_code < 500:
                break
            if attempt < self._max_attempts:
                time.sleep(float(attempt))
        if response is None or not 200 <= response.status_code < 300:
            status = response.status_code if response is not None else "unknown"
            request_id = (
                response.headers.get("cf-ray", "unavailable") if response else "unavailable"
            )
            raise CloudflareWorkersAIError(
                f"Cloudflare Workers AI request failed (status={status}, request_id={request_id})",
                code=f"http_{status}" if isinstance(status, int) else "http_unknown",
            )
        if (
            response.completed
            and response.finish_reason != "length"
            and not response.content.strip()
        ):
            raise CloudflareWorkersAIError(
                "Cloudflare Workers AI returned no model response",
                code="empty_model_response",
            )
        return response

    def propose(self, batch: AgenticBatch) -> AgenticBatchResult:
        response = self._request(batch)
        if not response.completed:
            return _quarantined_result(batch, "incomplete_model_stream")
        if response.finish_reason == "length":
            return _quarantined_result(batch, "model_output_truncated")
        if response.tool_name != AGENTIC_TOOL_NAME:
            return _quarantined_result(batch, "missing_required_tool_call")
        return validate_agentic_response(batch, response.content)


def _read_chunk_file(path: Path) -> tuple[EvidenceChunk, ...]:
    return tuple(
        EvidenceChunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def load_agentic_evidence_bundles(processed_root: Path) -> tuple[AgenticEvidenceBundle, ...]:
    inventory_root = processed_root / "_inventory"
    documents = tuple(
        SourceDocument.model_validate_json(line)
        for line in (inventory_root / "documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    messages = tuple(
        SourceMessage.model_validate_json(line)
        for line in (inventory_root / "source_messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    )
    documents_by_message: dict[str, list[SourceDocument]] = defaultdict(list)
    for document in documents:
        documents_by_message[document.message_id].append(document)

    bundles: list[AgenticEvidenceBundle] = []
    for message in sorted(messages, key=lambda item: item.message_id):
        message_chunks = _read_chunk_file(
            processed_root / "_messages" / message.message_id / "chunks.jsonl"
        )
        attached_documents = tuple(
            sorted(
                documents_by_message.get(message.message_id, ()), key=lambda item: item.document_id
            )
        )
        document_chunks = tuple(
            chunk
            for document in attached_documents
            for chunk in _read_chunk_file(processed_root / document.document_id / "chunks.jsonl")
        )
        mail_only = not attached_documents
        evidence_kind = "mail-only" if mail_only else "pdf-backed"
        if any("HISTORY_REPORT" in document.role.value for document in attached_documents):
            evidence_kind = "history-report"
        role_key = (
            "+".join(sorted({document.role.value for document in attached_documents})) or "message"
        )
        bundles.append(
            AgenticEvidenceBundle(
                bundle_id=message.message_id,
                cohort_key=(
                    f"{message.platform.value}:{message.category.value}:{evidence_kind}:{role_key}"
                ),
                mail_only=mail_only,
                chunks=(*message_chunks, *document_chunks),
            )
        )
    return tuple(bundles)


def _atomic_private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_agentic_result(result: AgenticBatchResult, output_root: Path) -> Path:
    output_path = output_root / f"{result.batch_id}.json"
    _atomic_private_write(
        output_path,
        f"{result.model_dump_json(indent=2)}\n".encode(),
    )
    return output_path


def execute_agentic_plan(
    plan: AgenticBatchPlan,
    *,
    client: CloudflareWorkersAIClient,
    output_root: Path,
    max_calls: int,
    resume: bool = False,
) -> AgenticRunSummary:
    if max_calls < 1:
        raise ValueError("max_calls must be positive for live execution")
    candidates = tuple(
        batch
        for batch in plan.batches
        if not resume or not (output_root / f"{batch.batch_id}.json").exists()
    )
    selected = candidates[:max_calls]
    results: list[AgenticBatchResult] = []
    for batch in selected:
        try:
            result = client.propose(batch)
        except CloudflareWorkersAIError as error:
            result = _quarantined_result(batch, f"api_request_failed:{error.code}")
        write_agentic_result(result, output_root)
        results.append(result)
    accepted = sum(result.validation_status is ValidationStatus.ACCEPTED for result in results)
    return AgenticRunSummary(
        planned_batches=len(plan.batches),
        attempted_batches=len(results),
        accepted_batches=accepted,
        quarantined_batches=len(results) - accepted,
        remaining_batches=len(candidates) - len(results),
    )
