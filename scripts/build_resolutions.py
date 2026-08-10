#!/usr/bin/env python3
"""Build deterministic order identities and reversible provenance bundles."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from lunarbit.agentic import _atomic_private_write, load_agentic_evidence_bundles
from lunarbit.agentic_quality import AgenticRegionRecord
from lunarbit.models import (
    CandidateFactType,
    EvidenceChunk,
    OrderEvidence,
    SourceDocument,
    SourceMessage,
)
from lunarbit.resolve import (
    AgenticOrderRegionReference,
    OrderResolutionArchive,
    link_agentic_regions_to_order_evidence,
    resolve_order_evidence,
)

RESOLUTION_ARCHIVE_VERSION = "1.0.0"
_ORDER_ID_TOKEN = re.compile(r"(?<!\d)\d{10,15}(?!\d)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--canonical-regions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
    manifest = _write_archive(
        archive,
        args.output.resolve(),
        canonical_region_sha256=sha256(region_content).hexdigest(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
