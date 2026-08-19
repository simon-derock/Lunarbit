#!/usr/bin/env python3
"""Derive normalized Embed v4 MRL prefixes and load versioned Neo4j indexes."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, cast

from neo4j import GraphDatabase, ManagedTransaction

from lunarbit.cohere import EMBED_MODEL, EmbedInputType
from lunarbit.embedding_archive import normalized_matryoshka_prefix, vector_identifiers

SOURCE_DIMENSION = 1536
DEFAULT_DIMENSIONS = (256, 512, 1024)
PROVIDER = "cohere-mrl"
REPRESENTATION = "normalized_1536_prefix"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        choices=(256, 512, 1024),
        default=DEFAULT_DIMENSIONS,
    )
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--index-timeout", type=float, default=300.0)
    return parser.parse_args()


def _source_batches(archive: Path) -> tuple[Path, ...]:
    paths = tuple(sorted((archive / "batches").glob("*.json")))
    if not paths:
        raise ValueError("source embedding archive does not contain any batches")
    return paths


def _load_source_rows(path: Path) -> tuple[dict[str, Any], ...]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict) or (
        body.get("model") != EMBED_MODEL
        or body.get("dimension") != SOURCE_DIMENSION
        or body.get("input_type") != EmbedInputType.SEARCH_DOCUMENT.value
    ):
        raise ValueError("source embedding batch contract changed")
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source embedding batch has no rows")
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("node_id"), str):
            raise ValueError("source embedding row identity changed")
        vector = row.get("embedding")
        if not isinstance(vector, list) or len(vector) != SOURCE_DIMENSION:
            raise ValueError("source embedding dimension changed")
        if any(not isinstance(value, (int, float)) for value in vector):
            raise ValueError("source embedding contains a non-numeric value")
        parsed.append(
            {
                "node_id": row["node_id"],
                "embedding": tuple(float(value) for value in vector),
            }
        )
    return tuple(parsed)


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
        "SET node[$model_property] = $model, node[$dimension_property] = $dimension, "
        "node[$representation_property] = $representation",
        {
            "rows": rows,
            "property_name": property_name,
            "model_property": model_property,
            "dimension_property": dimension_property,
            "representation_property": f"{property_name}_representation",
            "model": EMBED_MODEL,
            "dimension": dimension,
            "representation": REPRESENTATION,
        },
    ).consume()


def _create_index(session: Any, dimension: int) -> str:
    identifiers = vector_identifiers(PROVIDER, EMBED_MODEL, dimension)
    session.run(
        f"CREATE VECTOR INDEX {identifiers.index_name} IF NOT EXISTS "
        f"FOR (node:EvidenceChunk) ON node.{identifiers.property_name} "
        "OPTIONS {indexConfig: {`vector.dimensions`: $dimension, "
        "`vector.similarity_function`: 'cosine', `vector.quantization.enabled`: true, "
        "`vector.hnsw.m`: 16, `vector.hnsw.ef_construction`: 100}}",
        {"dimension": dimension},
    ).consume()
    return identifiers.index_name


def _wait_for_indexes(session: Any, names: tuple[str, ...], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        rows = tuple(
            record.data()
            for record in session.run(
                "SHOW INDEXES YIELD name, state WHERE name IN $names RETURN name, state",
                {"names": list(names)},
            )
        )
        states = {str(row["name"]): str(row["state"]) for row in rows}
        if all(states.get(name) == "ONLINE" for name in names):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("MRL vector indexes did not become ONLINE before the deadline")
        time.sleep(1.0)


def _manifest_count(archive: Path) -> int:
    body = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(body, dict) or body.get("complete") is not True:
        raise ValueError("source embedding archive is incomplete")
    count = body.get("embedded_nodes")
    if not isinstance(count, int) or count <= 0:
        raise ValueError("source embedding manifest count is invalid")
    return count


def main() -> int:
    args = _args()
    dimensions = tuple(sorted(set(cast(list[int], args.dimensions))))
    expected_count = _manifest_count(args.archive)
    paths = _source_batches(args.archive)
    plan = {
        "source_model": EMBED_MODEL,
        "source_dimension": SOURCE_DIMENSION,
        "representation": REPRESENTATION,
        "target_dimensions": dimensions,
        "source_batches": len(paths),
        "expected_nodes": expected_count,
        "ingest": bool(args.ingest),
    }
    if not args.ingest:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    driver = GraphDatabase.driver(args.uri, auth=None)
    seen: set[str] = set()
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            for path in paths:
                source_rows = _load_source_rows(path)
                node_ids = tuple(str(row["node_id"]) for row in source_rows)
                if seen.intersection(node_ids):
                    raise ValueError("source embedding archive repeats node coverage")
                seen.update(node_ids)
                for dimension in dimensions:
                    identifiers = vector_identifiers(PROVIDER, EMBED_MODEL, dimension)
                    rows = [
                        {
                            "node_id": row["node_id"],
                            "embedding": list(
                                normalized_matryoshka_prefix(
                                    cast(tuple[float, ...], row["embedding"]),
                                    dimension=dimension,
                                )
                            ),
                        }
                        for row in source_rows
                    ]
                    session.execute_write(
                        _write_vectors,
                        rows,
                        property_name=identifiers.property_name,
                        model_property=identifiers.model_property,
                        dimension_property=identifiers.dimension_property,
                        dimension=dimension,
                    )
            if len(seen) != expected_count:
                raise ValueError("MRL source coverage does not match the complete archive")
            index_names = tuple(_create_index(session, dimension) for dimension in dimensions)
            _wait_for_indexes(session, index_names, args.index_timeout)
            coverage: dict[int, int] = {}
            for dimension in dimensions:
                identifiers = vector_identifiers(PROVIDER, EMBED_MODEL, dimension)
                count = session.run(
                    "MATCH (node:EvidenceChunk) "
                    f"WHERE node.{identifiers.property_name} IS NOT NULL "
                    "RETURN count(node) AS count"
                ).single(strict=True)["count"]
                coverage[dimension] = int(count)
    finally:
        driver.close()
    if any(count != expected_count for count in coverage.values()):
        raise ValueError("Neo4j MRL coverage does not match the source archive")
    plan.update({"coverage": coverage, "indexes_online": True})
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
