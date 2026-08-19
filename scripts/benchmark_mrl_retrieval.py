#!/usr/bin/env python3
"""Benchmark Cohere Embed v4 retrieval retention across Neo4j MRL indexes."""

from __future__ import annotations

import argparse
import json
import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from lunarbit.agentic import _atomic_private_write
from lunarbit.cohere import CohereClient, EmbedInputType
from lunarbit.embedding_archive import vector_identifiers
from lunarbit.evaluation import RetrievalMetrics, first_relevant_rank, retrieval_metrics

MODEL = "embed-v4.0"
DIMENSIONS = (256, 512, 1024, 1536)
NATIVE_INDEX = "evidence_vector_cohere_embed_v4_0_1536"
PROTOCOL = "semantic-summary-relevance-set-v2"
type QueryCase = tuple[str, frozenset[str]]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=int, default=40)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def _private_api_key() -> str:
    load_dotenv(".env", override=False)
    value = os.environ.get("COHERE_API_KEY")
    if not value:
        raise ValueError("COHERE_API_KEY is required for the MRL benchmark")
    return value


def _sample_queries(session: Any, count: int) -> tuple[QueryCase, ...]:
    if not 1 <= count <= 96:
        raise ValueError("benchmark query count must be between 1 and 96")
    rows = tuple(
        record.data()
        for record in session.run(
            "MATCH (node:EvidenceChunk) "
            "WHERE node.semantic_summary_private IS NOT NULL "
            "AND size(trim(node.semantic_summary_private)) >= 24 "
            "RETURN node.node_id AS node_id, "
            "node.semantic_summary_private AS query_text"
        )
    )
    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(str(row["query_text"]), set()).add(str(row["node_id"]))

    def by_hash(value: QueryCase) -> str:
        return sha256(value[0].encode()).hexdigest()

    unique = sorted(
        ((text, frozenset(node_ids)) for text, node_ids in groups.items() if len(node_ids) == 1),
        key=by_hash,
    )
    ambiguous = sorted(
        (
            (text, frozenset(node_ids))
            for text, node_ids in groups.items()
            if 2 <= len(node_ids) <= 20
        ),
        key=by_hash,
    )
    unique_count = (count + 1) // 2
    ambiguous_count = count - unique_count
    selected = unique[:unique_count] + ambiguous[:ambiguous_count]
    if len(selected) < count:
        raise ValueError("graph does not contain enough benchmarkable evidence summaries")
    return tuple(sorted(selected, key=by_hash))


def _index_name(dimension: int) -> str:
    if dimension == 1536:
        return NATIVE_INDEX
    return vector_identifiers("cohere-mrl", MODEL, dimension).index_name


def _rank_for(
    session: Any,
    index: str,
    vector: tuple[float, ...],
    relevant_ids: frozenset[str],
    top_k: int,
) -> int | None:
    rows = tuple(
        record.data()
        for record in session.run(
            "CALL db.index.vector.queryNodes($index_name, $top_k, $embedding) "
            "YIELD node, score RETURN node.node_id AS node_id ORDER BY score DESC",
            {"index_name": index, "top_k": top_k, "embedding": list(vector)},
        )
    )
    return first_relevant_rank(
        tuple(str(row["node_id"]) for row in rows),
        relevant_ids,
    )


def _evaluate_dimension(
    session: Any,
    queries: tuple[QueryCase, ...],
    *,
    api_key: str,
    dimension: int,
    top_k: int,
) -> RetrievalMetrics:
    client = CohereClient(api_key, embedding_dimension=dimension)
    vectors = client.embed(
        tuple(text for text, _ in queries),
        input_type=EmbedInputType.SEARCH_QUERY,
    )
    index = _index_name(dimension)
    # Warm the index without including cold-start cost in the measured distribution.
    _rank_for(session, index, vectors[0], queries[0][1], top_k)
    ranks: list[int | None] = []
    latencies: list[float] = []
    for (_, relevant_ids), vector in zip(queries, vectors, strict=True):
        started = time.perf_counter()
        ranks.append(_rank_for(session, index, vector, relevant_ids, top_k))
        latencies.append((time.perf_counter() - started) * 1_000)
    return retrieval_metrics(tuple(ranks), tuple(latencies))


def main() -> int:
    args = _args()
    if not 1 <= args.top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    api_key = _private_api_key()
    driver = GraphDatabase.driver(args.uri, auth=None)
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            queries = _sample_queries(session, args.queries)
            metrics = {
                dimension: _evaluate_dimension(
                    session,
                    queries,
                    api_key=api_key,
                    dimension=dimension,
                    top_k=args.top_k,
                )
                for dimension in DIMENSIONS
            }
    finally:
        driver.close()
    reference = metrics[1536]
    noninferior = {
        dimension: (
            value.hit_at_10 >= reference.hit_at_10 - 0.01 and value.mrr >= reference.mrr * 0.98
        )
        for dimension, value in metrics.items()
    }
    result = {
        "protocol": PROTOCOL,
        "model": MODEL,
        "query_count": len(queries),
        "query_strata": {
            "unique_summary": sum(len(relevant_ids) == 1 for _, relevant_ids in queries),
            "ambiguous_summary": sum(len(relevant_ids) > 1 for _, relevant_ids in queries),
            "maximum_relevance_set": max(len(relevant_ids) for _, relevant_ids in queries),
        },
        "top_k": args.top_k,
        "corpus_nodes": 24675,
        "representations": {
            "256": "normalized_1536_prefix",
            "512": "normalized_1536_prefix",
            "1024": "normalized_1536_prefix",
            "1536": "native_api_output",
        },
        "metrics": {
            str(dimension): value.model_dump(mode="json") for dimension, value in metrics.items()
        },
        "noninferior_to_1536": {str(key): value for key, value in noninferior.items()},
        "limitation": (
            "Relevance is exact normalized semantic-summary equivalence over balanced unique "
            "and ambiguous strata; this does not replace the user-query golden set."
        ),
    }
    content = f"{json.dumps(result, indent=2, sort_keys=True)}\n"
    if args.output is not None:
        _atomic_private_write(args.output, content.encode())
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
