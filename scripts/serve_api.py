#!/usr/bin/env python3
"""Serve the public demo API plus the authenticated private GraphRAG runtime."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from neo4j import Driver, GraphDatabase

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


def _neo4j_auth(username: str | None, password: str | None) -> tuple[str, str] | None:
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    if username is None:
        return None
    assert password is not None
    return (username, password)


def _connect_neo4j(
    uri: str,
    *,
    username: str | None,
    password: str | None,
) -> Driver:
    driver = GraphDatabase.driver(
        uri,
        auth=_neo4j_auth(username, password),
        max_connection_lifetime=300,
    )
    driver.verify_connectivity()
    return driver


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
    driver = _connect_neo4j(uri, username=username, password=password)
    graph = Neo4jHybridGraph(driver, database=database)
    reader = Neo4jGraphReader(driver, database=database)
    public_reader = Neo4jAggregateReader(driver, database=database)
    session_store = (
        SQLiteConversationStore(
            str(production_config.session_db)
            if production_config is not None
            else os.environ["LUNARBIT_SESSION_DB"]
        )
        if production_config is not None or os.environ.get("LUNARBIT_SESSION_DB")
        else None
    )
    checkpoint_connection: sqlite3.Connection | None = None
    try:
        if session_store is not None:
            session_path = Path(
                str(production_config.session_db)
                if production_config is not None
                else os.environ["LUNARBIT_SESSION_DB"]
            )
            checkpoint_path = session_path.with_name(
                f"{session_path.stem}.langgraph{session_path.suffix}"
            )
            checkpoint_connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
            checkpointer = SqliteSaver(checkpoint_connection)
            checkpointer.setup()
        else:
            checkpointer = None
        cohere = CohereClient(cohere_key, embedding_dimension=1536)
        retrieval_backend = HybridRetrievalBackend(HybridRetriever(graph, cohere))
        answer_backend = GovernedAnswerBackend(reader)
        workflow = GraphRAGWorkflow(
            reader,
            planner=planner_from_environment(),
            checkpointer=checkpointer,
        )
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
            conversation_store=session_store,
        )
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        driver.close()
        if session_store is not None:
            session_store.close()
        if checkpoint_connection is not None:
            checkpoint_connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
