#!/usr/bin/env python3
"""Compile repaired baseline and semantic retries into one deterministic region archive."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from lunarbit.agentic import (
    AgenticBatchResult,
    _atomic_private_write,
    load_agentic_evidence_bundles,
)
from lunarbit.agentic_quality import AgenticRegionOrigin, compile_agentic_region_records

ARCHIVE_VERSION = "1.0.0"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--retry", type=Path, required=True)
    parser.add_argument("--retry-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read_results(root: Path) -> tuple[AgenticBatchResult, ...]:
    paths = tuple(path for path in sorted(root.glob("*.json")) if not path.name.startswith("_"))
    return tuple(
        AgenticBatchResult.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )


def _retry_chunk_ids(path: Path) -> frozenset[str]:
    return frozenset(
        source_chunk_id
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
        for region in json.loads(line)["regions"]
        for source_chunk_id in region["source_chunk_ids"]
    )


def main() -> int:
    args = _parse_args()
    bundles = load_agentic_evidence_bundles(args.processed_root)
    chunks_by_id = {str(chunk.chunk_id): chunk for bundle in bundles for chunk in bundle.chunks}
    records = compile_agentic_region_records(
        _read_results(args.baseline),
        _read_results(args.retry),
        retry_chunk_ids=_retry_chunk_ids(args.retry_manifest),
        chunks_by_id=chunks_by_id,
    )
    content = "".join(f"{record.model_dump_json()}\n" for record in records).encode()
    output_root = args.output.resolve()
    _atomic_private_write(output_root / "regions.jsonl", content)

    origin_counts = Counter(record.origin.value for record in records)
    issue_counts = Counter(issue.value for record in records for issue in record.quality_issues)
    manifest = {
        "archive_version": ARCHIVE_VERSION,
        "archive_sha256": sha256(content).hexdigest(),
        "regions": len(records),
        "source_chunks": len(chunks_by_id),
        "money_components": sum(
            len(chunk.candidate_money_components) for chunk in chunks_by_id.values()
        ),
        "baseline_regions": origin_counts[AgenticRegionOrigin.REPAIRED_BASELINE.value],
        "semantic_retry_regions": origin_counts[AgenticRegionOrigin.SEMANTIC_RETRY.value],
        "quality_issues": dict(sorted(issue_counts.items())),
    }
    _atomic_private_write(
        output_root / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
