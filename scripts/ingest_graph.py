#!/usr/bin/env python3
"""Idempotently load a canonical Lunarbit graph archive into Neo4j."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, cast

from neo4j import GraphDatabase, ManagedTransaction
from pydantic import BaseModel

from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    Neo4jWriteBatch,
    neo4j_write_batches,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("cypher/schema.cypher"))
    parser.add_argument("--uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def _read[T: BaseModel](path: Path, model: type[T]) -> tuple[T, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _schema_statements(path: Path) -> tuple[str, ...]:
    content = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("//")
    )
    return tuple(statement.strip() for statement in content.split(";") if statement.strip())


def _connection_config(args: argparse.Namespace) -> tuple[str, str, tuple[str, str] | None]:
    uri = args.uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = args.username or os.environ.get("NEO4J_USERNAME")
    password = args.password or os.environ.get("NEO4J_PASSWORD")
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    auth = None if username is None else (cast(str, username), cast(str, password))
    return cast(str, uri), cast(str, database), auth


def _write_batch(transaction: ManagedTransaction, batch: Neo4jWriteBatch) -> None:
    transaction.run(batch.cypher, batch.parameters).consume()


def main() -> int:
    args = _args()
    uri, database, auth = _connection_config(args)
    graph = CanonicalGraph(
        nodes=_read(args.graph_root / "nodes.jsonl", GraphNode),
        relationships=_read(args.graph_root / "relationships.jsonl", GraphRelationship),
    )
    batches = neo4j_write_batches(graph, batch_size=args.batch_size)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for statement in _schema_statements(args.schema):
                session.run(statement).consume()
            for batch in batches:
                session.execute_write(_write_batch, batch)
            counts: dict[str, Any] = (
                session.run(
                    "MATCH (node) WITH count(node) AS nodes "
                    "MATCH ()-[relationship]->() "
                    "RETURN nodes, count(relationship) AS relationships"
                )
                .single(strict=True)
                .data()
            )
    finally:
        driver.close()
    if counts != {"nodes": len(graph.nodes), "relationships": len(graph.relationships)}:
        raise ValueError("Neo4j counts do not match the canonical graph archive")
    print(
        json.dumps(
            {**counts, "write_batches": len(batches), "database": database},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
