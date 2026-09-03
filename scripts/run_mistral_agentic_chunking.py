#!/usr/bin/env python3
"""Run Lunarbit agentic batches through rate-governed Mistral workers."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

import lunarbit.agentic as agentic
from lunarbit.models import (
    CandidateFactType,
    CandidateMoneyComponent,
    ChunkType,
    EntityType,
    FinancialRole,
    QueryFamily,
    SemanticRole,
)

_KEY_NAMES = (
    "KEY_ONE",
    "KEY_TWO",
    "KEY_THREE",
    "KEY_FOUR",
    "KEY_FIVE",
    "KEY_SIX",
    "KEY_SEVEN",
    "KEY_EIGHT",
    "KEY_NINE",
    "KEY_TEN",
)

_SEMANTIC_RETRY_ADDENDUM = """This is a targeted semantic-quality repair pass over evidence that
already passed deterministic structural validation. Improve it materially; do not merely restate
the deterministic input.

- Produce model-authored regions for every supplied source chunk. Never use phrases such as
  `Preserved evidence`, `Deterministic fallback`, or `missing_context` when the supplied evidence
  supports a more specific interpretation.
- Never mention call-local cNNNN or mNNNN references in titles, summaries, embedding text,
  interpretations, conflicts, or uncertainty notes. Those references are valid only in identifier
  fields required by the tool schema.
- Compose distinct semantic_summary_private and embedding_text_private values. Summaries explain
  commercial meaning; embedding text adds exact grounded retrieval terms and useful query language.
- Do not emit a conflict explanation unless every value in that explanation occurs in the source
  chunks assigned to its region. Group the relevant same-bundle chunks and cite all of them when a
  conflict genuinely exists; otherwise omit the unsupported conflict.
- Transfer every supplied deterministic fact and entity candidate into the region containing its
  source chunk. Do not create additional candidates from narrative text.

All original identifier, coverage, money, enum, relation, and bundle-isolation rules still apply.
"""


def _keys(root: Path) -> tuple[str, ...]:
    values: dict[str, str] = {}
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        value = raw_value.strip().strip('"').strip("'")
        if value:
            values[name.strip()] = value
    keys = tuple(values[name] for name in _KEY_NAMES if name in values)
    if not keys and "MISTRAL_API_KEY" in values:
        keys = (values["MISTRAL_API_KEY"],)
    if not keys:
        raise RuntimeError("No Mistral API keys are configured in .env")
    if len(set(keys)) != len(keys):
        raise RuntimeError("Mistral API keys must be unique")
    return keys


def _tool_arguments(body: object) -> str:
    if not isinstance(body, Mapping):
        raise RuntimeError("mistral_invalid_tool_call")
    choices = body.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or len(choices) != 1:
        raise RuntimeError("mistral_invalid_tool_call")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise RuntimeError("mistral_invalid_tool_call")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("mistral_invalid_tool_call")
    tool_calls = message.get("tool_calls")
    if (
        not isinstance(tool_calls, Sequence)
        or isinstance(tool_calls, (str, bytes))
        or len(tool_calls) != 1
    ):
        raise RuntimeError("mistral_invalid_tool_call")
    tool_call = tool_calls[0]
    if not isinstance(tool_call, Mapping):
        raise RuntimeError("mistral_invalid_tool_call")
    function = tool_call.get("function")
    if not isinstance(function, Mapping) or function.get("name") != agentic.AGENTIC_TOOL_NAME:
        raise RuntimeError("mistral_invalid_tool_call")
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise RuntimeError("mistral_invalid_tool_call")
    return arguments


def _shard[T](items: tuple[T, ...], workers: int) -> tuple[tuple[T, ...], ...]:
    if workers < 1:
        raise ValueError("workers must be positive")
    return tuple(tuple(items[index::workers]) for index in range(workers))


class _ReferenceMaps(NamedTuple):
    chunk_to_ref: dict[str, str]
    ref_to_chunk: dict[str, str]
    component_to_ref: dict[str, str]
    ref_to_component: dict[str, str]


def _reference_maps(batch: agentic.AgenticBatch) -> _ReferenceMaps:
    chunk_to_ref = {
        str(chunk.chunk_id): f"c{index:04d}" for index, chunk in enumerate(batch.chunks, start=1)
    }
    component_ids = tuple(
        str(component.component_id)
        for chunk in batch.chunks
        for component in chunk.candidate_money_components
    )
    component_to_ref = {
        component_id: f"m{index:04d}" for index, component_id in enumerate(component_ids, start=1)
    }
    return _ReferenceMaps(
        chunk_to_ref=chunk_to_ref,
        ref_to_chunk={reference: value for value, reference in chunk_to_ref.items()},
        component_to_ref=component_to_ref,
        ref_to_component={reference: value for value, reference in component_to_ref.items()},
    )


def _mistral_user_prompt(batch: agentic.AgenticBatch) -> str:
    prompt, encoded_evidence = agentic.render_agentic_user_prompt(batch).split(
        "Evidence batch:\n", maxsplit=1
    )
    evidence = json.loads(encoded_evidence)
    references = _reference_maps(batch)
    evidence["batch_id"] = "batch"
    evidence["response_identity"] = {
        "batch_id": "batch",
        "covered_source_chunk_ids": list(references.ref_to_chunk),
        "covered_money_component_ids": list(references.ref_to_component),
    }
    for ledger_item in evidence["coverage_ledger"]:
        ledger_item["source_chunk_id"] = references.chunk_to_ref[ledger_item["source_chunk_id"]]
        ledger_item["source_component_ids"] = [
            references.component_to_ref[value] for value in ledger_item["source_component_ids"]
        ]
    for bundle in evidence["bundles"]:
        for chunk in bundle["chunks"]:
            chunk["chunk_id"] = references.chunk_to_ref[chunk["chunk_id"]]
            for component in chunk["candidate_money_components"]:
                component["component_id"] = references.component_to_ref[component["component_id"]]
            for graph_candidate in chunk["graph_candidates"]:
                graph_candidate["source_candidate_ids"] = [
                    references.component_to_ref.get(value, value)
                    for value in graph_candidate["source_candidate_ids"]
                ]
    reference_instructions = """For this call only, deterministic code replaced source UUIDs with
short opaque references. Use `batch` as batch_id, `cNNNN` values for every source chunk field, and
`mNNNN` values for every money component field. Copy only references present in response_identity
and coverage_ledger. Never output a UUID, placeholder, dummy value, ellipsis, field label, or newly
created identifier. Code resolves these call-local references to UUID5 identifiers after validation.

Evidence batch:
"""
    return (
        prompt
        + reference_instructions
        + json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _mistral_tool_definition(batch: agentic.AgenticBatch) -> dict[str, object]:
    tool = agentic._agentic_tool_definition(
        batch_id=batch.batch_id,
        bundle_ids=batch.bundle_ids,
        chunks=batch.chunks,
    )
    references = _reference_maps(batch)
    parameters = tool["parameters"]
    assert isinstance(parameters, dict)
    properties = parameters["properties"]
    definitions = parameters["$defs"]
    properties["batch_id"] = {"type": "string", "const": "batch"}
    properties["covered_source_chunk_ids"] = {
        "type": "array",
        "items": {"type": "string", "enum": list(references.ref_to_chunk)},
        "const": list(references.ref_to_chunk),
    }
    properties["covered_money_component_ids"] = {
        "type": "array",
        "items": {"type": "string", "enum": list(references.ref_to_component)},
        "const": list(references.ref_to_component),
    }
    region_properties = definitions["AgenticRegionProposal"]["properties"]
    region_properties["source_chunk_ids"]["items"] = {
        "type": "string",
        "enum": list(references.ref_to_chunk),
    }
    definitions["AgenticFactCandidate"]["properties"]["source_chunk_id"] = {
        "type": "string",
        "enum": list(references.ref_to_chunk),
    }
    entity_definition = definitions["AgenticEntityCandidate"]
    entity_definition["properties"]["source_chunk_id"] = {
        "type": "string",
        "enum": list(references.ref_to_chunk),
    }
    for option in entity_definition.get("anyOf", []):
        source_schema = option["properties"]["source_chunk_id"]
        source_schema["const"] = references.chunk_to_ref[source_schema["const"]]
    money_properties = definitions["AgenticMoneyInterpretation"]["properties"]
    money_properties["source_component_id"] = {
        "type": "string",
        "enum": list(references.ref_to_component),
    }
    money_properties["source_chunk_id"] = {
        "type": "string",
        "enum": list(references.ref_to_chunk),
    }
    definitions["AgenticRelationCandidate"]["properties"]["evidence_chunk_ids"]["items"] = {
        "type": "string",
        "enum": list(references.ref_to_chunk),
    }
    return tool


def _resolve_references(batch: agentic.AgenticBatch, raw_arguments: str) -> str:
    candidate = json.loads(raw_arguments)
    if not isinstance(candidate, dict):
        raise RuntimeError("mistral_invalid_tool_arguments")
    references = _reference_maps(batch)

    def chunk_id(value: object) -> object:
        return references.ref_to_chunk.get(value, value) if isinstance(value, str) else value

    def component_id(value: object) -> object:
        return references.ref_to_component.get(value, value) if isinstance(value, str) else value

    candidate["batch_id"] = str(batch.batch_id)
    candidate["covered_source_chunk_ids"] = [str(chunk.chunk_id) for chunk in batch.chunks]
    candidate["covered_money_component_ids"] = [
        str(component.component_id)
        for chunk in batch.chunks
        for component in chunk.candidate_money_components
    ]
    regions = candidate.get("regions")
    if isinstance(regions, list):
        for region in regions:
            if not isinstance(region, dict):
                continue
            source_chunk_ids = region.get("source_chunk_ids")
            if isinstance(source_chunk_ids, list):
                region["source_chunk_ids"] = [chunk_id(value) for value in source_chunk_ids]
            for field in ("candidate_facts", "entity_candidates"):
                values = region.get(field)
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, dict):
                            value["source_chunk_id"] = chunk_id(value.get("source_chunk_id"))
            interpretations = region.get("money_interpretations")
            if isinstance(interpretations, list):
                for interpretation in interpretations:
                    if isinstance(interpretation, dict):
                        interpretation["source_component_id"] = component_id(
                            interpretation.get("source_component_id")
                        )
                        interpretation["source_chunk_id"] = chunk_id(
                            interpretation.get("source_chunk_id")
                        )
            relations = region.get("relation_candidates")
            if isinstance(relations, list):
                for relation in relations:
                    if not isinstance(relation, dict):
                        continue
                    evidence_ids = relation.get("evidence_chunk_ids")
                    if isinstance(evidence_ids, list):
                        relation["evidence_chunk_ids"] = [chunk_id(value) for value in evidence_ids]
    return json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))


def _fallback_money_interpretation(
    component: CandidateMoneyComponent, *, source_chunk_id: str
) -> dict[str, object]:
    component_type = component.component_type.value
    meaning_by_type = {
        "item_amount": "unresolved",
        "subtotal": "subtotal",
        "discount": "discount",
        "packing_charge": "charge",
        "handling_fee": "charge",
        "delivery_charge": "charge",
        "platform_fee": "charge",
        "tax": "tax",
        "invoice_total": "total",
        "refund": "refund",
    }
    scope_by_type = {
        "item_amount": "item",
        "refund": "refund",
    }
    return {
        "source_component_id": str(component.component_id),
        "source_chunk_id": source_chunk_id,
        "money_scope": scope_by_type.get(component_type, "unknown"),
        "money_meaning": meaning_by_type[component_type],
        "interpretation_private": (
            f"Deterministic fallback preserves the {component_type} candidate without inferring "
            "additional commercial scope."
        ),
    }


def _complete_deterministic_coverage(batch: agentic.AgenticBatch, resolved_arguments: str) -> str:
    candidate = json.loads(resolved_arguments)
    if not isinstance(candidate, dict) or not isinstance(candidate.get("regions"), list):
        return resolved_arguments
    candidate = {
        key: candidate[key]
        for key in (
            "batch_id",
            "covered_source_chunk_ids",
            "covered_money_component_ids",
            "regions",
        )
        if key in candidate
    }
    regions = candidate["regions"]
    expected_ids = tuple(str(chunk.chunk_id) for chunk in batch.chunks)
    expected_set = set(expected_ids)
    bundle_by_chunk_id = dict(zip(expected_ids, batch.chunk_bundle_ids, strict=True))
    chunk_by_id = {str(chunk.chunk_id): chunk for chunk in batch.chunks}
    component_source_ids = {
        str(component.component_id): str(chunk.chunk_id)
        for chunk in batch.chunks
        for component in chunk.candidate_money_components
    }
    component_by_id = {
        str(component.component_id): component
        for chunk in batch.chunks
        for component in chunk.candidate_money_components
    }
    allowed_chunk_types = {value.value for value in ChunkType}
    allowed_semantic_roles = {value.value for value in SemanticRole}
    allowed_financial_roles = {value.value for value in FinancialRole}
    allowed_query_families = {value.value for value in QueryFamily}
    allowed_fact_types = {value.value for value in CandidateFactType}
    allowed_entity_types = {value.value for value in EntityType}
    allowed_money_scopes = {value.value for value in agentic.AgenticMoneyScope}
    allowed_money_meanings = {value.value for value in agentic.AgenticMoneyMeaning}
    allowed_relation_types = {value.value for value in agentic.AgenticRelationType}
    allowed_conflict_flags = {value.value for value in agentic.AgenticConflictFlag}
    seen_source_ids: set[str] = set()
    seen_component_ids: set[str] = set()
    cleaned_regions: list[dict[str, object]] = []
    for region in regions:
        if not isinstance(region, dict) or not isinstance(region.get("source_chunk_ids"), list):
            continue
        region_ids = [
            source_id
            for source_id in region["source_chunk_ids"]
            if isinstance(source_id, str)
            and source_id in expected_set
            and source_id not in seen_source_ids
        ]
        if not region_ids:
            continue
        region_bundles = {bundle_by_chunk_id[source_id] for source_id in region_ids}
        if len(region_bundles) != 1:
            continue
        seen_source_ids.update(region_ids)
        region["source_chunk_ids"] = region_ids
        region["bundle_id"] = next(iter(region_bundles))
        source_chunks = [chunk_by_id[source_id] for source_id in region_ids]
        representative = source_chunks[0]
        if region.get("chunk_type") not in allowed_chunk_types:
            region["chunk_type"] = representative.chunk_type.value
        if region.get("semantic_role") not in allowed_semantic_roles:
            region["semantic_role"] = representative.semantic_role.value
        if region.get("financial_role") not in allowed_financial_roles:
            region["financial_role"] = next(
                (
                    chunk.financial_role.value
                    for chunk in source_chunks
                    if chunk.financial_role is not FinancialRole.NONE
                ),
                FinancialRole.NONE.value,
            )
        title = region.get("region_title_private")
        if not isinstance(title, str) or not title.strip():
            region["region_title_private"] = (
                f"Preserved {representative.chunk_type.value.replace('_', ' ').title()} evidence"
            )
        summary = region.get("semantic_summary_private")
        if not isinstance(summary, str) or not summary.strip():
            region["semantic_summary_private"] = " ".join(
                dict.fromkeys(chunk.semantic_summary_private for chunk in source_chunks)
            )[:1_200]
        embedding_text = region.get("embedding_text_private")
        if not isinstance(embedding_text, str) or not embedding_text.strip():
            region["embedding_text_private"] = " ".join(
                dict.fromkeys(chunk.embedding_text_private for chunk in source_chunks)
            )[:1_600]
        query_families = region.get("query_families")
        cleaned_query_families = (
            [
                value
                for value in query_families
                if isinstance(value, str) and value in allowed_query_families
            ]
            if isinstance(query_families, list)
            else []
        )
        if not cleaned_query_families:
            cleaned_query_families = list(
                dict.fromkeys(
                    family.value for chunk in source_chunks for family in chunk.query_families
                )
            )
        region["query_families"] = cleaned_query_families[:8]
        for optional_array in (
            "candidate_facts",
            "entity_candidates",
            "money_interpretations",
            "relation_candidates",
            "conflict_flags",
            "uncertainty_notes_private",
        ):
            if not isinstance(region.get(optional_array), list):
                region[optional_array] = []

        facts = region.get("candidate_facts")
        if isinstance(facts, list):
            region["candidate_facts"] = [
                fact
                for fact in facts
                if isinstance(fact, dict)
                and isinstance(fact.get("source_chunk_id"), str)
                and fact["source_chunk_id"] in region_ids
                and isinstance(fact.get("source_span_start"), int)
                and isinstance(fact.get("source_span_end"), int)
                and isinstance(fact.get("raw_value_private"), str)
                and fact.get("fact_type") in allowed_fact_types
                and isinstance(fact.get("normalized_value_private"), str)
                and 0 <= fact["source_span_start"] < fact["source_span_end"]
                and fact["source_span_end"]
                <= len(chunk_by_id[fact["source_chunk_id"]].raw_text_private)
                and chunk_by_id[fact["source_chunk_id"]].raw_text_private[
                    fact["source_span_start"] : fact["source_span_end"]
                ]
                == fact["raw_value_private"]
            ]
        entities = region.get("entity_candidates")
        if isinstance(entities, list):
            region["entity_candidates"] = [
                entity
                for entity in entities
                if isinstance(entity, dict)
                and isinstance(entity.get("source_chunk_id"), str)
                and entity["source_chunk_id"] in region_ids
                and isinstance(entity.get("raw_value_private"), str)
                and entity.get("entity_type") in allowed_entity_types
                and entity["raw_value_private"]
                in chunk_by_id[entity["source_chunk_id"]].raw_text_private
            ]
        interpretations = region.get("money_interpretations")
        if isinstance(interpretations, list):
            accepted_interpretations: list[dict[str, object]] = []
            for interpretation in interpretations:
                if not isinstance(interpretation, dict):
                    continue
                component_id = interpretation.get("source_component_id")
                source_id = interpretation.get("source_chunk_id")
                if (
                    not isinstance(component_id, str)
                    or not isinstance(source_id, str)
                    or component_id in seen_component_ids
                    or source_id not in region_ids
                    or component_source_ids.get(component_id) != source_id
                ):
                    continue
                fallback = _fallback_money_interpretation(
                    component_by_id[component_id], source_chunk_id=source_id
                )
                if interpretation.get("money_scope") not in allowed_money_scopes:
                    interpretation["money_scope"] = fallback["money_scope"]
                if interpretation.get("money_meaning") not in allowed_money_meanings:
                    interpretation["money_meaning"] = fallback["money_meaning"]
                interpretation_text = interpretation.get("interpretation_private")
                if not isinstance(interpretation_text, str) or not interpretation_text.strip():
                    interpretation["interpretation_private"] = fallback["interpretation_private"]
                seen_component_ids.add(component_id)
                accepted_interpretations.append(interpretation)
            region["money_interpretations"] = accepted_interpretations
        relations = region.get("relation_candidates")
        if isinstance(relations, list):
            accepted_relations: list[dict[str, object]] = []
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                evidence_ids = relation.get("evidence_chunk_ids")
                endpoints = (relation.get("subject_private"), relation.get("object_private"))
                string_evidence_ids = (
                    [source_id for source_id in evidence_ids if isinstance(source_id, str)]
                    if isinstance(evidence_ids, list)
                    else []
                )
                string_endpoints = tuple(
                    endpoint for endpoint in endpoints if isinstance(endpoint, str)
                )
                if (
                    not isinstance(evidence_ids, list)
                    or not evidence_ids
                    or len(string_evidence_ids) != len(evidence_ids)
                    or not all(source_id in region_ids for source_id in string_evidence_ids)
                    or len(string_endpoints) != 2
                    or relation.get("relation_type") not in allowed_relation_types
                ):
                    continue
                if any(
                    endpoint not in {"ORDER", "DOCUMENT", "MESSAGE"}
                    and not any(
                        endpoint in chunk_by_id[source_id].raw_text_private
                        for source_id in string_evidence_ids
                    )
                    for endpoint in string_endpoints
                ):
                    continue
                accepted_relations.append(relation)
            region["relation_candidates"] = accepted_relations
        conflict_flags = region.get("conflict_flags")
        if isinstance(conflict_flags, list):
            region["conflict_flags"] = [
                value
                for value in conflict_flags
                if isinstance(value, str) and value in allowed_conflict_flags
            ]
        uncertainty_notes = region.get("uncertainty_notes_private")
        if isinstance(uncertainty_notes, list):
            region["uncertainty_notes_private"] = [
                value for value in uncertainty_notes if isinstance(value, str) and value.strip()
            ][:8]
        cleaned_regions.append(region)
    candidate["regions"] = regions = cleaned_regions
    proposed_ids: list[str] = []
    for region in regions:
        source_ids = region.get("source_chunk_ids")
        if isinstance(source_ids, list):
            proposed_ids.extend(value for value in source_ids if isinstance(value, str))
    proposed_counts = Counter(proposed_ids)
    for source_id in expected_ids:
        if source_id in proposed_counts:
            continue
        chunk = chunk_by_id[source_id]
        regions.append(
            {
                "bundle_id": bundle_by_chunk_id[source_id],
                "source_chunk_ids": [source_id],
                "chunk_type": chunk.chunk_type.value,
                "semantic_role": chunk.semantic_role.value,
                "financial_role": chunk.financial_role.value,
                "region_title_private": (
                    f"Preserved {chunk.chunk_type.value.replace('_', ' ').title()} evidence"
                ),
                "semantic_summary_private": chunk.semantic_summary_private[:1_200],
                "embedding_text_private": chunk.embedding_text_private[:1_600],
                "query_families": [family.value for family in chunk.query_families],
                "candidate_facts": [
                    {
                        "fact_type": assertion.fact_type.value,
                        "raw_value_private": assertion.raw_value_private,
                        "normalized_value_private": assertion.normalized_value_private,
                        "source_chunk_id": source_id,
                        "source_span_start": assertion.source_span_start,
                        "source_span_end": assertion.source_span_end,
                    }
                    for assertion in chunk.candidate_assertions
                ],
                "entity_candidates": [
                    {
                        "entity_type": mention.entity_type.value,
                        "raw_value_private": mention.raw_value_private,
                        "source_chunk_id": source_id,
                    }
                    for mention in chunk.entity_mentions
                ],
                "money_interpretations": [
                    _fallback_money_interpretation(component, source_chunk_id=source_id)
                    for component in chunk.candidate_money_components
                ],
                "relation_candidates": [],
                "conflict_flags": ["missing_context"],
                "uncertainty_notes_private": [
                    "Agentic grouping omitted this source chunk; deterministic fallback preserved "
                    "it without additional inference."
                ],
            }
        )

    proposed_money_ids: list[object] = []
    for region in regions:
        region_interpretations = region.get("money_interpretations")
        if isinstance(region_interpretations, list):
            proposed_money_ids.extend(
                interpretation.get("source_component_id")
                for interpretation in region_interpretations
                if isinstance(interpretation, dict)
            )
    proposed_money_counts = Counter(proposed_money_ids)
    if any(count > 1 for count in proposed_money_counts.values()):
        return json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
    for chunk in batch.chunks:
        source_id = str(chunk.chunk_id)
        target_region = None
        for region in regions:
            region_source_ids = region.get("source_chunk_ids")
            if isinstance(region_source_ids, list) and source_id in region_source_ids:
                target_region = region
                break
        if target_region is None:
            continue
        interpretations = target_region.setdefault("money_interpretations", [])
        if not isinstance(interpretations, list):
            continue
        for component in chunk.candidate_money_components:
            if str(component.component_id) not in proposed_money_counts:
                interpretations.append(
                    _fallback_money_interpretation(component, source_chunk_id=source_id)
                )
    return json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))


def _propose(
    batch: agentic.AgenticBatch,
    *,
    key: str,
    model: str,
    timeout: float,
    max_tokens: int,
    raw_output_root: Path,
    semantic_retry: bool = False,
) -> agentic.AgenticBatchResult:
    tool = _mistral_tool_definition(batch)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": agentic._SYSTEM_PROMPT
                + (f"\n\n{_SEMANTIC_RETRY_ADDENDUM}" if semantic_retry else ""),
            },
            {"role": "user", "content": _mistral_user_prompt(batch)},
        ],
        "tools": [{"type": "function", "function": tool}],
        "tool_choice": "any",
        "parallel_tool_calls": False,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2_000]
        raise RuntimeError(f"mistral_http_{error.code}: {detail}") from error
    content = _tool_arguments(body)
    agentic._atomic_private_write(
        raw_output_root / f"{batch.batch_id}.json",
        f"{content.rstrip()}\n".encode(),
    )
    resolved_content = _resolve_references(batch, content)
    completed_content = _complete_deterministic_coverage(batch, resolved_content)
    validated = agentic.validate_agentic_response(batch, completed_content)
    return validated.model_copy(update={"model": model})


class _WorkerResult(NamedTuple):
    attempted: int
    accepted: int
    stopped_on_error: str | None


def _run_worker(
    batches: tuple[agentic.AgenticBatch, ...],
    *,
    key: str,
    model: str,
    timeout: float,
    max_tokens: int,
    output_root: Path,
    minimum_start_interval: float,
    initial_delay: float = 0,
    max_attempts: int = 3,
    semantic_retry: bool = False,
) -> _WorkerResult:
    attempted = 0
    accepted = 0
    last_started: float | None = None
    if initial_delay > 0:
        time.sleep(initial_delay)
    for batch in batches:
        final_error: str | None = None
        for _ in range(max_attempts):
            if last_started is not None:
                delay = minimum_start_interval - (time.monotonic() - last_started)
                if delay > 0:
                    time.sleep(delay)
            last_started = time.monotonic()
            attempted += 1
            try:
                result = _propose(
                    batch,
                    key=key,
                    model=model,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    raw_output_root=output_root / "_raw",
                    semantic_retry=semantic_retry,
                )
            except (RuntimeError, TimeoutError, urllib.error.URLError) as error:
                final_error = str(error)
                continue
            if result.validation_status.value != "accepted":
                final_error = ",".join(result.quarantine_reasons)
                continue
            agentic.write_agentic_result(result, output_root)
            accepted += 1
            final_error = None
            break
        if final_error is not None:
            return _WorkerResult(attempted, accepted, final_error)
    return _WorkerResult(attempted, accepted, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", default="mistral-large-2512")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--bundle-start", type=int, default=0)
    parser.add_argument("--bundle-count", type=int, default=0)
    parser.add_argument(
        "--retry-manifest",
        type=Path,
        default=None,
        help="Private quality manifest selecting source chunks for targeted semantic retry",
    )
    parser.add_argument(
        "--quality-archive",
        type=Path,
        default=None,
        help="Canonical region JSONL whose flagged regions should be retried",
    )
    parser.add_argument("--expand-conflict-bundles", action="store_true")
    parser.add_argument("--context-source-chunk", action="append", default=[])
    parser.add_argument("--target-input-tokens", type=int, default=64_000)
    parser.add_argument("--max-input-tokens", type=int, default=80_000)
    parser.add_argument("--max-estimated-output-tokens", type=int, default=18_000)
    parser.add_argument("--max-chunks", type=int, default=512)
    parser.add_argument("--max-bundles", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=24_000)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--lanes-per-key", type=int, default=1)
    parser.add_argument("--minimum-start-interval", type=float, default=32.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Provider-specific result directory; defaults to input/_agentic/mistral-large-2512",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    keys = _keys(root)
    if args.workers < 1:
        parser.error("workers must be positive")
    if args.lanes_per_key < 1:
        parser.error("lanes-per-key must be positive")
    if args.minimum_start_interval < 0:
        parser.error("minimum-start-interval must be non-negative")
    if args.max_attempts < 1:
        parser.error("max-attempts must be positive")
    if args.retry_manifest is not None and args.quality_archive is not None:
        parser.error("retry-manifest and quality-archive are mutually exclusive")
    worker_count = min(args.workers, len(keys))
    bundles = agentic.load_agentic_evidence_bundles(args.input)
    retry_chunk_ids: set[str] | None = None
    if args.retry_manifest is not None:
        retry_chunk_ids = {
            source_chunk_id
            for line in args.retry_manifest.read_text(encoding="utf-8").splitlines()
            if line
            for region in json.loads(line)["regions"]
            for source_chunk_id in region["source_chunk_ids"]
        }
    elif args.quality_archive is not None:
        records = [
            json.loads(line)
            for line in args.quality_archive.read_text(encoding="utf-8").splitlines()
            if line
        ]
        conflict_bundles = {
            record["region"]["bundle_id"]
            for record in records
            if "uncited_amount_conflict" in record["quality_issues"]
        }
        retry_chunk_ids = {
            source_chunk_id
            for record in records
            if record["quality_issues"]
            and (
                not args.expand_conflict_bundles
                or "uncited_amount_conflict" not in record["quality_issues"]
            )
            for source_chunk_id in record["region"]["source_chunk_ids"]
        }
        if args.expand_conflict_bundles:
            retry_chunk_ids.update(
                source_chunk_id
                for record in records
                if record["region"]["bundle_id"] in conflict_bundles
                for source_chunk_id in record["region"]["source_chunk_ids"]
            )
        context_ids = set(args.context_source_chunk)
        retry_chunk_ids.update(
            source_chunk_id
            for record in records
            if context_ids & set(record["region"]["source_chunk_ids"])
            for source_chunk_id in record["region"]["source_chunk_ids"]
        )
    if retry_chunk_ids is not None:
        available_chunk_ids = {str(chunk.chunk_id) for bundle in bundles for chunk in bundle.chunks}
        unknown_retry_ids = retry_chunk_ids - available_chunk_ids
        if unknown_retry_ids:
            raise RuntimeError("Retry manifest contains unknown source chunks")
        bundles = tuple(
            agentic.AgenticEvidenceBundle(
                bundle_id=bundle.bundle_id,
                cohort_key=bundle.cohort_key,
                mail_only=bundle.mail_only,
                chunks=tuple(
                    chunk for chunk in bundle.chunks if str(chunk.chunk_id) in retry_chunk_ids
                ),
            )
            for bundle in bundles
            if any(str(chunk.chunk_id) in retry_chunk_ids for chunk in bundle.chunks)
        )
    if args.bundle_start < 0 or args.bundle_count < 0:
        parser.error("bundle-start and bundle-count must be non-negative")
    if args.bundle_count:
        bundles = bundles[args.bundle_start : args.bundle_start + args.bundle_count]
    elif args.bundle_start:
        bundles = bundles[args.bundle_start :]
    policy = agentic.AgenticBatchPolicy(
        target_input_tokens=args.target_input_tokens,
        max_input_tokens=args.max_input_tokens,
        max_completion_tokens=args.max_tokens,
        max_estimated_output_tokens=args.max_estimated_output_tokens,
        max_chunks=args.max_chunks,
        max_bundles=args.max_bundles,
        minimum_chunks=2,
    )
    counter = agentic.GemmaTokenizerCounter.from_cache(args.input / "_agentic" / "_tokenizer")
    plan = agentic.plan_agentic_batches(bundles, policy=policy, token_counter=counter)
    if not args.execute:
        print(
            json.dumps(
                {
                    "execution": "dry-run",
                    "model": args.model,
                    "workers": worker_count,
                    "lanes_per_key": args.lanes_per_key,
                    "configured_keys": len(keys),
                    "bundles": plan.bundles,
                    "input_chunks": plan.input_chunks,
                    "planned_batches": len(plan.batches),
                    "quarantined_chunks": len(plan.quarantined_chunk_ids),
                    "minimum_start_interval_seconds": args.minimum_start_interval,
                    "maximum_estimated_input_tokens": max(
                        (batch.estimated_input_tokens for batch in plan.batches), default=0
                    ),
                    "reserved_completion_tokens": args.max_tokens,
                }
            )
        )
        return 0
    output_root = args.output or (args.input / "_agentic" / "mistral-large-2512")
    output_root.mkdir(parents=True, exist_ok=True)
    if retry_chunk_ids is not None:
        selection = {"regions": [{"source_chunk_ids": sorted(retry_chunk_ids)}]}
        agentic._atomic_private_write(
            output_root / "_selection.jsonl",
            f"{json.dumps(selection, sort_keys=True, separators=(',', ':'))}\n".encode(),
        )
    candidates = tuple(
        batch
        for batch in plan.batches
        if not args.resume or not (output_root / f"{batch.batch_id}.json").exists()
    )
    limit = args.max_calls or len(candidates)
    selected = candidates[:limit]
    worker_specs = tuple(
        (key_index, lane_index)
        for key_index in range(worker_count)
        for lane_index in range(args.lanes_per_key)
    )
    shards = _shard(selected, len(worker_specs))
    active = tuple((worker_specs[index], shard) for index, shard in enumerate(shards) if shard)
    with ThreadPoolExecutor(max_workers=len(active) or 1) as executor:
        futures = tuple(
            executor.submit(
                _run_worker,
                shard,
                key=keys[key_index],
                model=args.model,
                timeout=args.timeout_seconds,
                max_tokens=args.max_tokens,
                output_root=output_root,
                minimum_start_interval=(args.minimum_start_interval * args.lanes_per_key),
                initial_delay=args.minimum_start_interval * lane_index,
                max_attempts=args.max_attempts,
                semantic_retry=retry_chunk_ids is not None,
            )
            for (key_index, lane_index), shard in active
        )
        results = tuple(future.result() for future in futures)
    attempted = sum(result.attempted for result in results)
    accepted = sum(result.accepted for result in results)
    errors = tuple(result.stopped_on_error for result in results if result.stopped_on_error)
    print(
        json.dumps(
            {
                "planned_batches": len(plan.batches),
                "attempted_batches": attempted,
                "accepted_batches": accepted,
                "quarantined_batches": attempted - accepted - len(errors),
                "worker_errors": errors,
                "workers": worker_count,
                "lanes_per_key": args.lanes_per_key,
                "minimum_start_interval_seconds": args.minimum_start_interval,
                "model": args.model,
            }
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
