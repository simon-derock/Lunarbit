#!/usr/bin/env python3
"""Serve the public demo API plus the authenticated private GraphRAG runtime."""

from __future__ import annotations

import argparse
import os

import uvicorn
from dotenv import load_dotenv

from lunarbit.api import DEFAULT_PUBLIC_ORIGINS, create_app
from lunarbit.cohere import CohereClient
from lunarbit.conversation import SQLiteConversationStore
from lunarbit.deployment_config import validate_deployment_environment
from lunarbit.hybrid import HybridRetriever, Neo4jHybridGraph
from lunarbit.langgraph_workflow import GraphRAGWorkflow
from lunarbit.public_projection import NavigationSnapshotSource, Neo4jAggregateReader
from lunarbit.query_planner import planner_from_environment
from lunarbit.runtime import Neo4jGraphReader
from lunarbit.service import GovernedAnswerBackend, HybridRetrievalBackend


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--neo4j-uri", default=None)
    parser.add_argument("--neo4j-database", default=None)
    parser.add_argument(
        "--production",
        action="store_true",
        help="validate the deployment environment and enforce production settings",
    )
    return parser.parse_args()


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is required for the private API runtime")
    return value


def main() -> int:
    args = _args()
    load_dotenv(".env", override=False)
    production_config = validate_deployment_environment() if args.production else None
    cohere_key = _required_environment("COHERE_API_KEY")
    private_token = _required_environment("LUNARBIT_PRIVATE_API_TOKEN")
    uri = args.neo4j_uri or (
        production_config.neo4j_uri
        if production_config is not None
        else os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    )
    database = args.neo4j_database or (
        production_config.database
        if production_config is not None
        else os.environ.get("NEO4J_DATABASE", "neo4j")
    )
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
            public_snapshot_source=NavigationSnapshotSource(
                public_reader,
                per_class=24,
                relationship_limit=600,
            ),
            private_backend=retrieval_backend,
            private_answer_backend=answer_backend,
            private_workflow=workflow,
            private_api_token=private_token,
            allowed_origins=(
                production_config.allowed_origins
                if production_config is not None
                else DEFAULT_PUBLIC_ORIGINS
            ),
            conversation_store=(
                SQLiteConversationStore(
                    str(production_config.session_db)
                    if production_config is not None
                    else os.environ["LUNARBIT_SESSION_DB"]
                )
                if production_config is not None or os.environ.get("LUNARBIT_SESSION_DB")
                else None
            ),
        )
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        public_reader.close()
        reader.close()
        graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
