#!/usr/bin/env python3
"""Generate resumable Cohere Embed v4 evidence vectors and load Neo4j HNSW."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase, ManagedTransaction

from lunarbit.agentic import _atomic_private_write
from lunarbit.cohere import EMBED_MODEL, MAX_EMBED_INPUTS, CohereClient, EmbedInputType
from lunarbit.embedding_archive import (
    EmbeddingInput,
    archive_batch_path,
    batch_embedding_inputs,
    load_embedding_batch,
    vector_identifiers,
    write_embedding_batch,
)
from lunarbit.graph import GraphNode, NodeLabel

PROVIDER = "cohere"
DEFAULT_DIMENSION = 1536
DEFAULT_WORKERS = 4
# 96 inputs / 3.05 seconds remains below Cohere's documented 2,000 text inputs/minute.
DEFAULT_START_INTERVAL = 3.05
RETRYABLE_ERRORS = frozenset(
    {
        "cohere_http_408",
        "cohere_http_429",
        "cohere_http_500",
        "cohere_http_502",
        "cohere_http_503",
        "cohere_http_504",
        "cohere_transport_error",
    }
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dimension", type=int, choices=(256, 512, 1024, 1536), default=1536)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--minimum-start-interval", type=float, default=DEFAULT_START_INTERVAL)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    return parser.parse_args()


def _private_api_key(path: Path = Path(".env")) -> str | None:
    load_dotenv(path, override=False)
    return os.environ.get("COHERE_API_KEY")


def _evidence_inputs(path: Path) -> tuple[EmbeddingInput, ...]:
    values: list[EmbeddingInput] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        node = GraphNode.model_validate_json(line)
        if NodeLabel.EVIDENCE_CHUNK not in node.labels:
            continue
        summary = str(node.properties.get("semantic_summary_private") or "")
        normalized = str(node.properties.get("normalized_text_private") or "")
        text = f"{summary}\nEvidence: {normalized}".strip()[:8_000]
        if text:
            values.append(EmbeddingInput(node_id=node.node_id, text=text))
    return tuple(sorted(values, key=lambda value: value.node_id))


class StartRateGate:
    def __init__(self, interval: float) -> None:
        if interval < 0:
            raise ValueError("minimum start interval cannot be negative")
        self._interval = interval
        self._next_start = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            scheduled = max(now, self._next_start)
            self._next_start = scheduled + self._interval
        delay = scheduled - now
        if delay > 0:
            time.sleep(delay)


def _execute_batch(
    batch: tuple[EmbeddingInput, ...],
    *,
    output: Path,
    client: CohereClient,
    gate: StartRateGate,
    dimension: int,
    max_attempts: int,
) -> Path:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    path = archive_batch_path(output, batch, model=EMBED_MODEL, dimension=dimension)
    for attempt in range(1, max_attempts + 1):
        gate.wait()
        try:
            vectors = client.embed(
                tuple(value.text for value in batch),
                input_type=EmbedInputType.SEARCH_DOCUMENT,
            )
            write_embedding_batch(
                path,
                batch,
                vectors,
                model=EMBED_MODEL,
                dimension=dimension,
                input_type=EmbedInputType.SEARCH_DOCUMENT.value,
            )
            return path
        except RuntimeError as error:
            if str(error) not in RETRYABLE_ERRORS or attempt == max_attempts:
                raise
            time.sleep(min(60.0, float(2 ** (attempt - 1))))
    raise AssertionError("retry loop ended without returning or raising")


def _write_vectors(
    transaction: ManagedTransaction,
    rows: list[dict[str, Any]],
    *,
    property_name: str,
    model_property: str,
    dimension_property: str,
    dimension: int,
) -> None:
    transaction.run(
        "UNWIND $rows AS row MATCH (node:LunarbitNode {node_id: row.node_id}) "
        "CALL db.create.setNodeVectorProperty(node, $property_name, row.embedding) "
        "SET node[$model_property] = $model, node[$dimension_property] = $dimension",
        {
            "rows": rows,
            "property_name": property_name,
            "model_property": model_property,
            "dimension_property": dimension_property,
            "model": EMBED_MODEL,
            "dimension": dimension,
        },
    ).consume()


def _ingest(
    rows: list[dict[str, Any]],
    *,
    dimension: int,
    uri: str,
    database: str,
    username: str | None = None,
    password: str | None = None,
) -> None:
    identifiers = vector_identifiers(PROVIDER, EMBED_MODEL, dimension)
    if (username is None) != (password is None):
        raise ValueError("Neo4j username and password must be supplied together")
    auth: tuple[str, str] | None = None
    if username is not None and password is not None:
        auth = (username, password)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for offset in range(0, len(rows), 500):
                session.execute_write(
                    _write_vectors,
                    rows[offset : offset + 500],
                    property_name=identifiers.property_name,
                    model_property=identifiers.model_property,
                    dimension_property=identifiers.dimension_property,
                    dimension=dimension,
                )
            session.run(
                f"CREATE VECTOR INDEX {identifiers.index_name} IF NOT EXISTS "
                f"FOR (node:EvidenceChunk) ON node.{identifiers.property_name} "
                "OPTIONS {indexConfig: {`vector.dimensions`: $dimension, "
                "`vector.similarity_function`: 'cosine', `vector.quantization.enabled`: true, "
                "`vector.hnsw.m`: 16, `vector.hnsw.ef_construction`: 100}}",
                {"dimension": dimension},
            ).consume()
            count = session.run(
                "MATCH (node:EvidenceChunk) "
                f"WHERE node.{identifiers.property_name} IS NOT NULL "
                "RETURN count(node) AS count"
            ).single(strict=True)["count"]
    finally:
        driver.close()
    if int(count) != len(rows):
        raise ValueError("Neo4j Cohere embedding coverage does not match the private archive")


def main() -> int:
    args = _args()
    if args.workers <= 0:
        raise ValueError("workers must be positive")
    values = _evidence_inputs(args.graph_root / "nodes.jsonl")
    batches = batch_embedding_inputs(values, max_inputs=MAX_EMBED_INPUTS)
    output = args.output.resolve()
    missing = [
        batch
        for batch in batches
        if not archive_batch_path(
            output,
            batch,
            model=EMBED_MODEL,
            dimension=args.dimension,
        ).exists()
    ]
    selected = missing[: args.max_batches or None]
    if args.execute and selected:
        api_key = _private_api_key()
        if not api_key:
            raise ValueError("COHERE_API_KEY is required for embedding execution")
        client = CohereClient(
            api_key,
            embedding_dimension=args.dimension,
            timeout=args.timeout,
        )
        gate = StartRateGate(args.minimum_start_interval)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures: tuple[Future[Path], ...] = tuple(
                executor.submit(
                    _execute_batch,
                    batch,
                    output=output,
                    client=client,
                    gate=gate,
                    dimension=args.dimension,
                    max_attempts=args.max_attempts,
                )
                for batch in selected
            )
            for completed, future in enumerate(as_completed(futures), start=1):
                future.result()
                print(json.dumps({"completed_this_run": completed, "scheduled": len(futures)}))
    all_rows: list[dict[str, Any]] = []
    completed_batches = 0
    for batch in batches:
        path = archive_batch_path(output, batch, model=EMBED_MODEL, dimension=args.dimension)
        if not path.exists():
            continue
        all_rows.extend(
            load_embedding_batch(
                path,
                expected=batch,
                model=EMBED_MODEL,
                dimension=args.dimension,
                input_type=EmbedInputType.SEARCH_DOCUMENT.value,
            )
        )
        completed_batches += 1
    complete = completed_batches == len(batches)
    if args.ingest:
        if not complete:
            raise ValueError("Cohere embedding archive must be complete before Neo4j ingestion")
        _ingest(
            all_rows,
            dimension=args.dimension,
            uri=args.uri,
            database=args.database,
            username=os.environ.get("NEO4J_USERNAME"),
            password=os.environ.get("NEO4J_PASSWORD"),
        )
    identifiers = vector_identifiers(PROVIDER, EMBED_MODEL, args.dimension)
    manifest = {
        "provider": PROVIDER,
        "model": EMBED_MODEL,
        "dimension": args.dimension,
        "input_type": EmbedInputType.SEARCH_DOCUMENT.value,
        "evidence_nodes": len(values),
        "planned_batches": len(batches),
        "completed_batches": completed_batches,
        "embedded_nodes": len(all_rows),
        "complete": complete,
        "neo4j_property": identifiers.property_name,
        "neo4j_index": identifiers.index_name,
    }
    _atomic_private_write(
        output / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
