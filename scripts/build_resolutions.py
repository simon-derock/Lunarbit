#!/usr/bin/env python3
"""Build deterministic order identities and reversible provenance bundles."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from lunarbit.agentic import _atomic_private_write, load_agentic_evidence_bundles
from lunarbit.agentic_quality import AgenticRegionRecord
from lunarbit.finance import (
    FinancialArchive,
    FinancialArchiveSummary,
    MoneyComponent,
    ReconciliationStatus,
    normalize_money_component,
    reconcile_document_scope,
)
from lunarbit.models import (
    CandidateFactType,
    EvidenceChunk,
    FinancialRole,
    OrderEvidence,
    SourceDocument,
    SourceMessage,
)
from lunarbit.product import (
    ItemEvidenceObservation,
    ProductResolutionArchive,
    item_observation_from_chunk,
    resolve_item_observations,
)
from lunarbit.resolve import (
    AgenticOrderRegionReference,
    EntityEvidenceMention,
    EntityResolutionArchive,
    OrderResolutionArchive,
    link_agentic_regions_to_order_evidence,
    resolve_entity_mentions,
    resolve_order_evidence,
)

RESOLUTION_ARCHIVE_VERSION = "1.0.0"
_ORDER_ID_TOKEN = re.compile(r"(?<!\d)\d{10,15}(?!\d)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--canonical-regions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identity-output", type=Path, required=True)
    parser.add_argument("--product-output", type=Path, required=True)
    parser.add_argument("--finance-output", type=Path, required=True)
    parser.add_argument(
        "--decided-at",
        type=datetime.fromisoformat,
        required=True,
        help="Timezone-aware policy decision timestamp used for reproducible output",
    )
    return parser.parse_args()


def _read_jsonl[T: BaseModel](path: Path, model: type[T]) -> tuple[T, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _region_references(
    records: tuple[AgenticRegionRecord, ...],
    chunks_by_id: dict[str, EvidenceChunk],
    known_order_ids: frozenset[str],
) -> tuple[AgenticOrderRegionReference, ...]:
    references: list[AgenticOrderRegionReference] = []
    for record in records:
        source_ids = tuple(
            sorted(
                {
                    chunks_by_id[str(chunk_id)].source_id
                    for chunk_id in record.region.source_chunk_ids
                }
            )
        )
        source_order_ids = {
            token
            for chunk_id in record.region.source_chunk_ids
            for token in _ORDER_ID_TOKEN.findall(chunks_by_id[str(chunk_id)].raw_text_private)
            if token in known_order_ids
        }
        candidate_order_ids = {
            candidate.raw_value_private
            for candidate in record.region.candidate_facts
            if candidate.fact_type is CandidateFactType.ORDER_ID
        }
        order_ids = tuple(sorted(source_order_ids | candidate_order_ids))
        references.append(
            AgenticOrderRegionReference(
                region_id=record.region_id,
                source_ids=source_ids,
                order_ids_private=order_ids,
            )
        )
    return tuple(references)


def _jsonl(values: tuple[BaseModel, ...]) -> bytes:
    return "".join(f"{value.model_dump_json()}\n" for value in values).encode()


def _write_archive(
    archive: OrderResolutionArchive,
    output_root: Path,
    *,
    canonical_region_sha256: str,
) -> dict[str, object]:
    files = {
        "candidates.jsonl": _jsonl(archive.candidates),
        "bundles.jsonl": _jsonl(archive.bundles),
        "orders.jsonl": _jsonl(archive.orders),
        "decisions.jsonl": _jsonl(archive.decisions),
    }
    for name, content in files.items():
        _atomic_private_write(output_root / name, content)
    file_hashes = {name: sha256(content).hexdigest() for name, content in files.items()}
    archive_digest = sha256(
        "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes)).encode()
    ).hexdigest()
    manifest: dict[str, object] = {
        "archive_version": RESOLUTION_ARCHIVE_VERSION,
        "policy_version": archive.policy_version,
        "archive_sha256": archive_digest,
        "canonical_region_sha256": canonical_region_sha256,
        "files": file_hashes,
        **archive.summary.model_dump(mode="json"),
    }
    _atomic_private_write(
        output_root / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    return manifest


def _entity_mentions(
    records: tuple[AgenticRegionRecord, ...],
    chunks_by_id: dict[str, EvidenceChunk],
    messages: tuple[SourceMessage, ...],
    documents: tuple[SourceDocument, ...],
    order_archive: OrderResolutionArchive,
) -> tuple[EntityEvidenceMention, ...]:
    platform_by_source_id = {
        **{message.message_id: message.platform for message in messages},
        **{document.document_id: document.platform for document in documents},
    }
    order_ids_by_region: dict[UUID, set[UUID]] = {}
    for bundle in order_archive.bundles:
        for region_id in bundle.agentic_region_ids:
            order_ids_by_region.setdefault(region_id, set()).add(bundle.order_id)
    region_by_chunk_id = {
        str(chunk_id): record.region_id
        for record in records
        for chunk_id in record.region.source_chunk_ids
    }
    mentions: list[EntityEvidenceMention] = []
    for chunk in chunks_by_id.values():
        region_id = region_by_chunk_id[str(chunk.chunk_id)]
        order_ids = tuple(sorted(order_ids_by_region.get(region_id, set()), key=str))
        for mention in chunk.entity_mentions:
            mentions.append(
                EntityEvidenceMention(
                    mention_id=mention.mention_id,
                    entity_type=mention.entity_type,
                    raw_value_private=mention.raw_value_private,
                    normalized_value_private=mention.normalized_value_private,
                    source_chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    platform=platform_by_source_id[chunk.source_id],
                    order_ids=order_ids,
                )
            )
    return tuple(mentions)


def _write_entity_archive(
    archive: EntityResolutionArchive,
    output_root: Path,
    *,
    order_archive_sha256: str,
) -> dict[str, object]:
    files = {
        "mentions.jsonl": _jsonl(archive.mentions),
        "merchants.jsonl": _jsonl(archive.merchants),
        "outlets.jsonl": _jsonl(archive.outlets),
        "legal_entities.jsonl": _jsonl(archive.legal_entities),
        "delivery_mentions.jsonl": _jsonl(archive.delivery_mentions),
        "person_identities.jsonl": _jsonl(archive.person_identities),
        "decisions.jsonl": _jsonl(archive.decisions),
    }
    for name, content in files.items():
        _atomic_private_write(output_root / name, content)
    file_hashes = {name: sha256(content).hexdigest() for name, content in files.items()}
    archive_digest = sha256(
        "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes)).encode()
    ).hexdigest()
    manifest: dict[str, object] = {
        "archive_version": RESOLUTION_ARCHIVE_VERSION,
        "policy_version": archive.policy_version,
        "archive_sha256": archive_digest,
        "order_archive_sha256": order_archive_sha256,
        "files": file_hashes,
        **archive.summary.model_dump(mode="json"),
    }
    _atomic_private_write(
        output_root / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    return manifest


def _item_observations(
    records: tuple[AgenticRegionRecord, ...],
    chunks_by_id: dict[str, EvidenceChunk],
    order_archive: OrderResolutionArchive,
    entity_archive: EntityResolutionArchive,
) -> tuple[ItemEvidenceObservation, ...]:
    order_ids_by_region: dict[UUID, set[UUID]] = {}
    for bundle in order_archive.bundles:
        for region_id in bundle.agentic_region_ids:
            order_ids_by_region.setdefault(region_id, set()).add(bundle.order_id)
    merchant_ids_by_order: dict[UUID, set[UUID]] = {}
    for outlet in entity_archive.outlets:
        merchant_ids_by_order.setdefault(outlet.order_id, set()).add(outlet.merchant_id)
    observations: dict[UUID, ItemEvidenceObservation] = {}
    for record in records:
        if record.region.financial_role is not FinancialRole.ITEM:
            continue
        order_ids = order_ids_by_region.get(record.region_id, set())
        if len(order_ids) != 1:
            continue
        order_id = next(iter(order_ids))
        merchant_ids = merchant_ids_by_order.get(order_id, set())
        merchant_id = next(iter(merchant_ids)) if len(merchant_ids) == 1 else None
        for chunk_id in record.region.source_chunk_ids:
            observation = item_observation_from_chunk(
                chunks_by_id[str(chunk_id)],
                order_id=order_id,
                merchant_id=merchant_id,
            )
            if observation is not None:
                observations[observation.observation_id] = observation
    return tuple(observations.values())


def _write_product_archive(
    archive: ProductResolutionArchive,
    output_root: Path,
    *,
    entity_archive_sha256: str,
) -> dict[str, object]:
    files = {
        "observations.jsonl": _jsonl(archive.observations),
        "merchant_items.jsonl": _jsonl(archive.merchant_items),
        "canonical_items.jsonl": _jsonl(archive.canonical_items),
        "comparable_item_groups.jsonl": _jsonl(archive.comparable_item_groups),
    }
    for name, content in files.items():
        _atomic_private_write(output_root / name, content)
    file_hashes = {name: sha256(content).hexdigest() for name, content in files.items()}
    archive_digest = sha256(
        "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes)).encode()
    ).hexdigest()
    manifest: dict[str, object] = {
        "archive_version": RESOLUTION_ARCHIVE_VERSION,
        "policy_version": archive.policy_version,
        "archive_sha256": archive_digest,
        "entity_archive_sha256": entity_archive_sha256,
        "files": file_hashes,
        **archive.summary.model_dump(mode="json"),
    }
    _atomic_private_write(
        output_root / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    return manifest


def _financial_archive(
    records: tuple[AgenticRegionRecord, ...],
    chunks_by_id: dict[str, EvidenceChunk],
    order_archive: OrderResolutionArchive,
    *,
    executed_at: datetime,
) -> FinancialArchive:
    order_ids_by_region: dict[UUID, set[UUID]] = {}
    for bundle in order_archive.bundles:
        for region_id in bundle.agentic_region_ids:
            order_ids_by_region.setdefault(region_id, set()).add(bundle.order_id)
    candidates = {
        component.component_id: (component, chunk)
        for chunk in chunks_by_id.values()
        for component in chunk.candidate_money_components
    }
    components: list[MoneyComponent] = []
    for record in records:
        order_ids = tuple(sorted(order_ids_by_region.get(record.region_id, set()), key=str))
        for interpretation in record.region.money_interpretations:
            source, chunk = candidates[interpretation.source_component_id]
            components.append(
                normalize_money_component(
                    source,
                    interpretation,
                    source_id=chunk.source_id,
                    order_ids=order_ids,
                )
            )
    components.sort(key=lambda component: str(component.component_id))
    groups: dict[tuple[str, str, tuple[UUID, ...]], list[MoneyComponent]] = defaultdict(list)
    for component in components:
        groups[(component.source_id, component.scope.value, component.order_ids)].append(component)
    runs = tuple(
        run
        for key in sorted(groups, key=str)
        if (run := reconcile_document_scope(groups[key], executed_at=executed_at)) is not None
    )
    return FinancialArchive(
        policy_version="financial-truth-v1.0.0",
        components=tuple(components),
        reconciliation_runs=runs,
        summary=FinancialArchiveSummary(
            money_components=len(components),
            assigned_order_components=sum(bool(component.order_ids) for component in components),
            unassigned_order_components=sum(not component.order_ids for component in components),
            reconciliation_runs=len(runs),
            exact_reconciliations=sum(run.status is ReconciliationStatus.EXACT for run in runs),
            conflicting_reconciliations=sum(
                run.status is ReconciliationStatus.CONFLICTING for run in runs
            ),
        ),
    )


def _write_financial_archive(
    archive: FinancialArchive,
    output_root: Path,
    *,
    product_archive_sha256: str,
) -> dict[str, object]:
    files = {
        "money_components.jsonl": _jsonl(archive.components),
        "reconciliation_runs.jsonl": _jsonl(archive.reconciliation_runs),
    }
    for name, content in files.items():
        _atomic_private_write(output_root / name, content)
    file_hashes = {name: sha256(content).hexdigest() for name, content in files.items()}
    archive_digest = sha256(
        "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes)).encode()
    ).hexdigest()
    manifest: dict[str, object] = {
        "archive_version": RESOLUTION_ARCHIVE_VERSION,
        "policy_version": archive.policy_version,
        "archive_sha256": archive_digest,
        "product_archive_sha256": product_archive_sha256,
        "files": file_hashes,
        **archive.summary.model_dump(mode="json"),
    }
    _atomic_private_write(
        output_root / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    return manifest


def main() -> int:
    args = _parse_args()
    if args.decided_at.tzinfo is None or args.decided_at.utcoffset() is None:
        raise ValueError("--decided-at must include a UTC offset")
    inventory_root = args.processed_root / "_inventory"
    messages = _read_jsonl(inventory_root / "source_messages.jsonl", SourceMessage)
    documents = _read_jsonl(inventory_root / "documents.jsonl", SourceDocument)
    evidence = _read_jsonl(inventory_root / "order_evidence.jsonl", OrderEvidence)
    region_content = args.canonical_regions.read_bytes()
    records = tuple(
        AgenticRegionRecord.model_validate_json(line)
        for line in region_content.decode().splitlines()
        if line
    )
    bundles = load_agentic_evidence_bundles(args.processed_root)
    chunks_by_id = {str(chunk.chunk_id): chunk for bundle in bundles for chunk in bundle.chunks}
    known_order_ids = frozenset(
        item.order_id_private for item in evidence if item.order_id_private is not None
    )
    references = _region_references(records, chunks_by_id, known_order_ids)
    region_links = link_agentic_regions_to_order_evidence(messages, evidence, references)
    archive = resolve_order_evidence(
        messages,
        documents,
        evidence,
        region_links_by_evidence_id=region_links,
        decided_at=args.decided_at,
    )
    order_manifest = _write_archive(
        archive,
        args.output.resolve(),
        canonical_region_sha256=sha256(region_content).hexdigest(),
    )
    entity_archive = resolve_entity_mentions(
        _entity_mentions(records, chunks_by_id, messages, documents, archive),
        decided_at=args.decided_at,
    )
    entity_manifest = _write_entity_archive(
        entity_archive,
        args.identity_output.resolve(),
        order_archive_sha256=str(order_manifest["archive_sha256"]),
    )
    product_archive = resolve_item_observations(
        _item_observations(records, chunks_by_id, archive, entity_archive)
    )
    product_manifest = _write_product_archive(
        product_archive,
        args.product_output.resolve(),
        entity_archive_sha256=str(entity_manifest["archive_sha256"]),
    )
    financial_archive = _financial_archive(
        records,
        chunks_by_id,
        archive,
        executed_at=args.decided_at,
    )
    finance_manifest = _write_financial_archive(
        financial_archive,
        args.finance_output.resolve(),
        product_archive_sha256=str(product_manifest["archive_sha256"]),
    )
    print(
        json.dumps(
            {
                "orders": order_manifest,
                "entities": entity_manifest,
                "products": product_manifest,
                "finance": finance_manifest,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
