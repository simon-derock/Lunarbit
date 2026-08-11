#!/usr/bin/env python3
"""Validate dense, lexical, graph-expansion, and evidence-verification retrieval."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from decimal import Decimal
from typing import Any, cast

from dotenv import load_dotenv
from neo4j import GraphDatabase

from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    RetrievalCandidate,
    VerificationStatus,
    reciprocal_rank_fusion,
    verify_evidence_pack,
)

MODEL = "mistral-embed-2312"
DIMENSION = 1024


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    return parser.parse_args()


def _embed_query(text: str) -> list[float]:
    load_dotenv(".env", override=False)
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise ValueError("MISTRAL_API_KEY is required for dense query retrieval")
    request = urllib.request.Request(
        "https://api.mistral.ai/v1/embeddings",
        data=json.dumps({"model": MODEL, "input": text}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read())
    vector = cast(list[float], body["data"][0]["embedding"])
    if len(vector) != DIMENSION:
        raise ValueError("dense query embedding dimension changed")
    return vector


def main() -> int:
    args = _args()
    query_text = "restaurant order with platform fee, discount, and tax evidence"
    vector = _embed_query(query_text)
    driver = GraphDatabase.driver(args.uri, auth=None)
    try:
        with driver.session(database=args.database) as session:
            dense_rows = [
                record.data()
                for record in session.run(
                    "CALL db.index.vector.queryNodes('evidence_vector', 30, $embedding) "
                    "YIELD node, score RETURN node.node_id AS node_id, score",
                    {"embedding": vector},
                )
            ]
            lexical_rows = [
                record.data()
                for record in session.run(
                    "CALL db.index.fulltext.queryNodes('evidence_lexical', $query, {limit: 30}) "
                    "YIELD node, score RETURN node.node_id AS node_id, score",
                    {"query": "platform fee discount tax"},
                )
            ]
            dense = tuple(
                RetrievalCandidate(candidate_id=str(row["node_id"]), channel="dense", rank=index)
                for index, row in enumerate(dense_rows, start=1)
            )
            lexical = tuple(
                RetrievalCandidate(candidate_id=str(row["node_id"]), channel="lexical", rank=index)
                for index, row in enumerate(lexical_rows, start=1)
            )
            fused = reciprocal_rank_fusion((dense, lexical), limit=10)
            fused_ids = [candidate.candidate_id for candidate in fused]
            expansion_rows = [
                record.data()
                for record in session.run(
                    "UNWIND $node_ids AS node_id "
                    "MATCH (chunk:EvidenceChunk {node_id: node_id}) "
                    "MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
                    "OPTIONAL MATCH (chunk)-[:GROUPED_INTO]->(region:AgenticRegion) "
                    "OPTIONAL MATCH (money:MoneyComponent)-[:EVIDENCED_BY]->(chunk) "
                    "RETURN chunk.node_id AS chunk_id, chunk.source_hash AS source_hash, "
                    "source.node_id AS source_id, count(DISTINCT region) AS regions, "
                    "count(DISTINCT money) AS money_components LIMIT 30",
                    {"node_ids": fused_ids},
                )
            ]
    finally:
        driver.close()
    citations = tuple(
        EvidenceCitation(
            citation_id=f"hybrid:citation:{index}",
            chunk_node_id=str(row["chunk_id"]),
            source_node_id=str(row["source_id"]),
            source_hash=str(row["source_hash"]),
            authority_score=Decimal("0.80"),
            supports_claim_ids=("hybrid:retrieval-path",),
            quality_flags=(),
        )
        for index, row in enumerate(expansion_rows, start=1)
    )
    verification = verify_evidence_pack(
        EvidencePack(claim_ids=("hybrid:retrieval-path",), citations=citations)
    )
    overlap = len({item.candidate_id for item in dense} & {item.candidate_id for item in lexical})
    result: dict[str, Any] = {
        "dense_candidates": len(dense),
        "lexical_candidates": len(lexical),
        "cross_channel_overlap": overlap,
        "fused_candidates": len(fused),
        "multi_channel_fused_candidates": sum(len(item.channels) > 1 for item in fused),
        "graph_expansion_rows": len(expansion_rows),
        "regions_reached": sum(int(row["regions"]) for row in expansion_rows),
        "money_components_reached": sum(int(row["money_components"]) for row in expansion_rows),
        "verification": verification.status.value,
    }
    if (
        not dense
        or not lexical
        or not fused
        or not expansion_rows
        or verification.status is not VerificationStatus.VERIFIED
    ):
        raise ValueError("hybrid retrieval smoke suite failed")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
