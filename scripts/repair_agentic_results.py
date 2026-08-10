#!/usr/bin/env python3
"""Repair deterministic agentic quality defects without mutating model outputs in place."""

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
    write_agentic_result,
)
from lunarbit.agentic_quality import (
    AgenticQualityIssue,
    audit_agentic_region,
    repair_agentic_result,
)

POSTPROCESS_VERSION = "1.0.0"
_LLM_RETRY_ISSUES = frozenset(
    {
        AgenticQualityIssue.DETERMINISTIC_FALLBACK,
        AgenticQualityIssue.SHORT_STRUCTURALLY_SPARSE,
        AgenticQualityIssue.UNCITED_AMOUNT_CONFLICT,
    }
)


def _archive_hash(paths: tuple[Path, ...]) -> str:
    digest = sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_root = args.input.resolve()
    output_root = args.output.resolve()
    if input_root == output_root:
        raise SystemExit("input and output directories must differ")
    input_paths = tuple(
        path for path in sorted(input_root.glob("*.json")) if not path.name.startswith("_")
    )
    if not input_paths:
        raise SystemExit("input directory contains no agentic result files")

    bundles = load_agentic_evidence_bundles(args.processed_root)
    chunks_by_id = {str(chunk.chunk_id): chunk for bundle in bundles for chunk in bundle.chunks}
    before_issues: Counter[str] = Counter()
    after_issues: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    changed_results = 0
    changed_regions = 0
    retry_records: list[dict[str, object]] = []
    retry_region_count = 0
    written_paths: list[Path] = []

    for input_path in input_paths:
        result = AgenticBatchResult.model_validate_json(input_path.read_text(encoding="utf-8"))
        for region in result.regions:
            before_issues.update(
                issue.value for issue in audit_agentic_region(region, chunks_by_id).issues
            )

        repaired, report = repair_agentic_result(result, chunks_by_id)
        if repaired != result:
            changed_results += 1
        changed_regions += report.changed_regions
        action_counts.update(
            {
                "restored_fact_candidates": report.restored_fact_candidates,
                "restored_entity_candidates": report.restored_entity_candidates,
                "removed_unsupported_fact_candidates": (
                    report.removed_unsupported_fact_candidates
                ),
                "removed_unsupported_entity_candidates": (
                    report.removed_unsupported_entity_candidates
                ),
                "removed_temporary_aliases": report.removed_temporary_aliases,
                "recomposed_embedding_texts": report.recomposed_embedding_texts,
                "enriched_sparse_regions": report.enriched_sparse_regions,
            }
        )

        retry_regions: list[dict[str, object]] = []
        for region_index, region in enumerate(repaired.regions):
            audit = audit_agentic_region(region, chunks_by_id)
            after_issues.update(issue.value for issue in audit.issues)
            retry_issues = tuple(issue for issue in audit.issues if issue in _LLM_RETRY_ISSUES)
            if retry_issues:
                retry_regions.append(
                    {
                        "region_index": region_index,
                        "source_chunk_ids": [str(value) for value in region.source_chunk_ids],
                        "issues": [issue.value for issue in retry_issues],
                    }
                )
        if retry_regions:
            retry_region_count += len(retry_regions)
            retry_records.append(
                {
                    "batch_id": str(repaired.batch_id),
                    "regions": retry_regions,
                }
            )
        written_paths.append(write_agentic_result(repaired, output_root))

    retry_content = "".join(
        f"{json.dumps(record, sort_keys=True, separators=(',', ':'))}\n"
        for record in retry_records
    )
    _atomic_private_write(output_root / "_llm_retry.jsonl", retry_content.encode())
    manifest = {
        "postprocess_version": POSTPROCESS_VERSION,
        "input_archive_sha256": _archive_hash(input_paths),
        "output_archive_sha256": _archive_hash(tuple(written_paths)),
        "result_files": len(input_paths),
        "regions": sum(
            len(AgenticBatchResult.model_validate_json(path.read_text()).regions)
            for path in written_paths
        ),
        "changed_results": changed_results,
        "changed_regions": changed_regions,
        "actions": dict(sorted(action_counts.items())),
        "issues_before": dict(sorted(before_issues.items())),
        "issues_after": dict(sorted(after_issues.items())),
        "llm_retry_batches": len(retry_records),
        "llm_retry_regions": retry_region_count,
    }
    _atomic_private_write(
        output_root / "_quality_manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
