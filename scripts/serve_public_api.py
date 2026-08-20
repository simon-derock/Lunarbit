#!/usr/bin/env python3
"""Serve Lunarbit's browser-safe API without mounting private GraphRAG routes.

With ``NEO4J_URI`` (or ``--neo4j-uri``), this serves a live aggregate topology.
Without it, the public synthetic mirror remains available for demos and contract
verification. The process never loads embedding keys, private API tokens, or a
private retrieval backend.
"""

from __future__ import annotations

import argparse
import os

import uvicorn
from dotenv import load_dotenv

from lunarbit.api import create_app, parse_public_origins
from lunarbit.public_projection import AggregateSnapshotSource, Neo4jAggregateReader


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--neo4j-uri", default=None)
    parser.add_argument("--neo4j-database", default=None)
    return parser.parse_args()


def main() -> int:
    args = _args()
    load_dotenv(".env", override=False)
    uri = args.neo4j_uri or os.environ.get("NEO4J_URI")
    database = args.neo4j_database or os.environ.get("NEO4J_DATABASE", "neo4j")
    allowed_origins = parse_public_origins(os.environ.get("LUNARBIT_PUBLIC_ALLOWED_ORIGINS"))
    reader: Neo4jAggregateReader | None = None

    try:
        source = None
        if uri:
            reader = Neo4jAggregateReader.connect(
                uri,
                database=database,
                username=os.environ.get("NEO4J_USERNAME") or None,
                password=os.environ.get("NEO4J_PASSWORD") or None,
            )
            source = AggregateSnapshotSource(reader)
        app = create_app(
            public_snapshot_source=source,
            allowed_origins=allowed_origins,
            include_private_routes=False,
        )
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        if reader is not None:
            reader.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
