#!/usr/bin/env python3
"""Build a private, deterministic financial-intelligence corpus and temporal graph."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from lunarbit.agentic import _atomic_private_write
from lunarbit.economic_pipeline import compile_economic_intelligence
from lunarbit.finance import MoneyComponent
from lunarbit.graph import CanonicalGraph, GraphNode, GraphRelationship
from lunarbit.models import SourceDocument, SourceMessage

ARCHIVE_VERSION = "financial-intelligence-corpus-v1.0.0"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path, required=True)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read[T: BaseModel](path: Path, model: type[T]) -> tuple[T, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _jsonl(values: tuple[BaseModel, ...]) -> bytes:
    return ("\n".join(value.model_dump_json() for value in values) + "\n").encode()


def _sha256(content: bytes) -> str:
    return sha256(content).hexdigest()


def _manifest_hash(path: Path) -> str:
    return _sha256(path.read_bytes())


def main() -> int:
    args = _args()
    messages = _read(args.inventory_root / "source_messages.jsonl", SourceMessage)
    documents = _read(args.inventory_root / "documents.jsonl", SourceDocument)
    components = _read(args.finance_root / "money_components.jsonl", MoneyComponent)
    graph = CanonicalGraph(
        nodes=_read(args.graph_root / "nodes.jsonl", GraphNode),
        relationships=_read(
            args.graph_root / "relationships.jsonl",
            GraphRelationship,
        ),
    )
    corpus = compile_economic_intelligence(messages, documents, components, graph)

    files = {
        "financial_events.jsonl": _jsonl(corpus.events),
        "financial_chunks.jsonl": _jsonl(corpus.chunk_archive.chunks),
        "nodes.jsonl": _jsonl(corpus.graph.nodes),
        "relationships.jsonl": _jsonl(corpus.graph.relationships),
    }
    manifest = {
        "archive_version": ARCHIVE_VERSION,
        "pipeline_version": corpus.pipeline_version,
        "observation_clock_policy": corpus.observation_clock_policy.value,
        "observed_at": corpus.observed_at.isoformat(),
        "summary": corpus.summary.model_dump(mode="json"),
        "financial_chunk_archive_sha256": corpus.chunk_archive.archive_sha256,
        "upstream_manifests": {
            "finance_sha256": _manifest_hash(args.finance_root / "manifest.json"),
            "graph_sha256": _manifest_hash(args.graph_root / "manifest.json"),
        },
        "files": {
            name: {"bytes": len(content), "sha256": _sha256(content)}
            for name, content in sorted(files.items())
        },
    }
    manifest_content = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        _atomic_private_write(args.output / name, content)
    _atomic_private_write(args.output / "manifest.json", manifest_content)
    print(
        json.dumps(
            {
                "archive_version": ARCHIVE_VERSION,
                "output": str(args.output),
                "summary": corpus.summary.model_dump(mode="json"),
                "manifest_sha256": _sha256(manifest_content),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
