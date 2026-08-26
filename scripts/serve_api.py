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
from lunarbit.langgraph_workflow import GraphRAGWorkflow
from lunarbit.public_projection import AggregateSnapshotSource, Neo4jAggregateReader
from lunarbit.query_planner import planner_from_environment
from lunarbit.runtime import Neo4jGraphReader
from lunarbit.service import GovernedAnswerBackend, HybridRetrievalBackend


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
    reader = Neo4jGraphReader.connect(
        uri,
        database=database,
        username=username,
        password=password,
    )
    public_reader = Neo4jAggregateReader.connect(
        uri,
        database=database,
        username=username,
        password=password,
    )
    try:
        cohere = CohereClient(cohere_key, embedding_dimension=1536)
        retrieval_backend = HybridRetrievalBackend(HybridRetriever(graph, cohere))
        answer_backend = GovernedAnswerBackend(reader)
        workflow = GraphRAGWorkflow(reader, planner=planner_from_environment())
        app = create_app(
            public_snapshot_source=AggregateSnapshotSource(public_reader),
            private_backend=retrieval_backend,
            private_answer_backend=answer_backend,
            private_workflow=workflow,
            private_api_token=private_token,
        )
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        public_reader.close()
        reader.close()
        graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
