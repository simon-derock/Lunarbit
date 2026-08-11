#!/usr/bin/env python3
"""Generate resumable evidence embeddings and load the Neo4j HNSW index."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from neo4j import GraphDatabase, ManagedTransaction

from lunarbit.agentic import _atomic_private_write
from lunarbit.graph import GraphNode, NodeLabel

EMBEDDING_MODEL = "mistral-embed-2312"
EMBEDDING_DIMENSION = 1024
MAX_BATCH_INPUTS = 128
MAX_BATCH_CHARACTERS = 48_000
VECTOR_INDEX_NAME = "evidence_vector"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--minimum-start-interval", type=float, default=1.05)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    return parser.parse_args()


def _private_env(path: Path = Path(".env")) -> str | None:
    load_dotenv(path, override=False)
    import os

    return os.environ.get("MISTRAL_API_KEY")


def _evidence_nodes(path: Path) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        node = GraphNode.model_validate_json(line)
        if NodeLabel.EVIDENCE_CHUNK not in node.labels:
            continue
        summary = str(node.properties.get("semantic_summary_private") or "")
        normalized = str(node.properties.get("normalized_text_private") or "")
        text = f"{summary}\nEvidence: {normalized}".strip()[:8_000]
        values.append((node.node_id, text))
    return tuple(sorted(values))


def _batches(values: tuple[tuple[str, str], ...]) -> tuple[tuple[tuple[str, str], ...], ...]:
    batches: list[tuple[tuple[str, str], ...]] = []
    current: list[tuple[str, str]] = []
    characters = 0
    for value in values:
        if current and (
            len(current) >= MAX_BATCH_INPUTS or characters + len(value[1]) > MAX_BATCH_CHARACTERS
        ):
            batches.append(tuple(current))
            current = []
            characters = 0
        current.append(value)
        characters += len(value[1])
    if current:
        batches.append(tuple(current))
    return tuple(batches)


def _batch_path(output: Path, batch: tuple[tuple[str, str], ...]) -> Path:
    identity = ",".join(node_id for node_id, _ in batch)
    return output / "batches" / f"{sha256(identity.encode()).hexdigest()}.json"


def _request_embeddings(
    batch: tuple[tuple[str, str], ...],
    *,
    api_key: str,
    timeout: float,
) -> list[list[float]]:
    request = urllib.request.Request(
        "https://api.mistral.ai/v1/embeddings",
        data=json.dumps(
            {"model": EMBEDDING_MODEL, "input": [text for _, text in batch]},
            ensure_ascii=False,
        ).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"mistral_embedding_http_{error.code}") from error
    ordered = sorted(body["data"], key=lambda item: int(item["index"]))
    vectors = [item["embedding"] for item in ordered]
    if len(vectors) != len(batch) or any(len(vector) != EMBEDDING_DIMENSION for vector in vectors):
        raise ValueError("embedding response shape does not match the deterministic batch")
    return vectors


def _load_batch(path: Path, expected_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if body["model"] != EMBEDDING_MODEL or body["dimension"] != EMBEDDING_DIMENSION:
        raise ValueError("stored embedding batch model contract changed")
    rows = cast(list[dict[str, Any]], body["rows"])
    if tuple(row["node_id"] for row in rows) != expected_ids:
        raise ValueError("stored embedding batch coverage changed")
    if any(len(row["embedding"]) != EMBEDDING_DIMENSION for row in rows):
        raise ValueError("stored embedding dimension changed")
    return rows


def _write_vectors(transaction: ManagedTransaction, rows: list[dict[str, Any]]) -> None:
    transaction.run(
        "UNWIND $rows AS row MATCH (node:LunarbitNode {node_id: row.node_id}) "
        "CALL db.create.setNodeVectorProperty(node, 'embedding', row.embedding) "
        "SET node.embedding_model = $model, node.embedding_dimension = $dimension",
        {"rows": rows, "model": EMBEDDING_MODEL, "dimension": EMBEDDING_DIMENSION},
    ).consume()


def _ingest(rows: list[dict[str, Any]], *, uri: str, database: str) -> None:
    driver = GraphDatabase.driver(uri, auth=None)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for offset in range(0, len(rows), 500):
                session.execute_write(_write_vectors, rows[offset : offset + 500])
            session.run(
                f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS "
                "FOR (node:EvidenceChunk) ON node.embedding OPTIONS {indexConfig: {"
                "`vector.dimensions`: $dimension, `vector.similarity_function`: 'cosine', "
                "`vector.quantization.enabled`: true, `vector.hnsw.m`: 16, "
                "`vector.hnsw.ef_construction`: 100}}",
                {"dimension": EMBEDDING_DIMENSION},
            ).consume()
            count = session.run(
                "MATCH (node:EvidenceChunk) WHERE node.embedding IS NOT NULL "
                "RETURN count(node) AS count"
            ).single(strict=True)["count"]
    finally:
        driver.close()
    if int(count) != len(rows):
        raise ValueError("Neo4j embedding coverage does not match the private archive")


def main() -> int:
    args = _args()
    values = _evidence_nodes(args.graph_root / "nodes.jsonl")
    batches = _batches(values)
    output = args.output.resolve()
    missing = [batch for batch in batches if not _batch_path(output, batch).exists()]
    selected = missing[: args.max_batches or None]
    if args.execute and selected:
        api_key = _private_env()
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is required for embedding execution")
        last_started: float | None = None
        for batch in selected:
            if last_started is not None:
                delay = args.minimum_start_interval - (time.monotonic() - last_started)
                if delay > 0:
                    time.sleep(delay)
            last_started = time.monotonic()
            vectors = _request_embeddings(batch, api_key=api_key, timeout=args.timeout)
            rows = [
                {"node_id": node_id, "embedding": vector}
                for (node_id, _), vector in zip(batch, vectors, strict=True)
            ]
            content = {
                "model": EMBEDDING_MODEL,
                "dimension": EMBEDDING_DIMENSION,
                "rows": rows,
            }
            _atomic_private_write(
                _batch_path(output, batch),
                f"{json.dumps(content, separators=(',', ':'))}\n".encode(),
            )
    all_rows: list[dict[str, Any]] = []
    completed = 0
    for batch in batches:
        path = _batch_path(output, batch)
        if not path.exists():
            continue
        all_rows.extend(_load_batch(path, tuple(node_id for node_id, _ in batch)))
        completed += 1
    complete = completed == len(batches)
    if args.ingest:
        if not complete:
            raise ValueError("embedding archive must be complete before Neo4j ingestion")
        _ingest(all_rows, uri=args.uri, database=args.database)
    manifest = {
        "model": EMBEDDING_MODEL,
        "dimension": EMBEDDING_DIMENSION,
        "evidence_nodes": len(values),
        "planned_batches": len(batches),
        "completed_batches": completed,
        "embedded_nodes": len(all_rows),
        "complete": complete,
    }
    _atomic_private_write(
        output / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
