#!/usr/bin/env python3
"""Serve the public demo API plus the authenticated private GraphRAG runtime."""

from __future__ import annotations

import argparse
import os

import uvicorn
from dotenv import load_dotenv

from lunarbit.api import create_app
from lunarbit.cohere import CohereClient
from lunarbit.hybrid import HybridRetriever, Neo4jHybridGraph
from lunarbit.service import HybridRetrievalBackend


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--neo4j-uri", default=None)
    parser.add_argument("--neo4j-database", default=None)
    return parser.parse_args()


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is required for the private API runtime")
    return value


def main() -> int:
    args = _args()
    load_dotenv(".env", override=False)
    cohere_key = _required_environment("COHERE_API_KEY")
    private_token = _required_environment("LUNARBIT_PRIVATE_API_TOKEN")
    uri = args.neo4j_uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = args.neo4j_database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = os.environ.get("NEO4J_USERNAME") or None
    password = os.environ.get("NEO4J_PASSWORD") or None
    graph = Neo4jHybridGraph.connect(
        uri,
        database=database,
        username=username,
        password=password,
    )
    try:
        cohere = CohereClient(cohere_key, embedding_dimension=1536)
        backend = HybridRetrievalBackend(HybridRetriever(graph, cohere))
        app = create_app(private_backend=backend, private_api_token=private_token)
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
