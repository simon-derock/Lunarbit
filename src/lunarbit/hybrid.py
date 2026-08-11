from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Protocol, Self

from neo4j import READ_ACCESS, Driver, GraphDatabase
from pydantic import Field

from lunarbit.cohere import EmbedInputType, RerankResult
from lunarbit.models import ContractModel
from lunarbit.reranking import RerankOutcome, RerankStatus, rerank_fused_candidates
from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    EvidenceVerification,
    RetrievalCandidate,
    VerificationStatus,
    reciprocal_rank_fusion,
    verify_evidence_pack,
)

_LEXICAL_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


class EvidenceDocument(ContractModel):
    candidate_id: str = Field(min_length=1)
    text_private: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    quality_flags: tuple[str, ...]


class HybridGraph(Protocol):
    def dense_candidates(self, vector: tuple[float, ...], limit: int) -> tuple[str, ...]: ...

    def lexical_candidates(self, query: str, limit: int) -> tuple[str, ...]: ...

    def expand_evidence(
        self,
        candidate_ids: tuple[str, ...],
    ) -> Mapping[str, EvidenceDocument]: ...


class EmbedderReranker(Protocol):
    def embed(
        self,
        texts: Sequence[str],
        *,
        input_type: EmbedInputType = EmbedInputType.SEARCH_QUERY,
    ) -> tuple[tuple[float, ...], ...]: ...

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]: ...


class HybridStatus(StrEnum):
    VERIFIED = "verified"
    VERIFIED_DEGRADED = "verified_degraded"
    ABSTAINED = "abstained"


class HybridResult(ContractModel):
    status: HybridStatus
    channel_counts: dict[str, int]
    evidence: tuple[EvidenceDocument, ...]
    reranking: RerankOutcome | None
    citations: tuple[EvidenceCitation, ...]
    verification: EvidenceVerification
    degradations: tuple[str, ...]


def lexical_terms(question: str) -> str:
    terms = _LEXICAL_TOKEN.findall(question.casefold())
    if not terms:
        raise ValueError("query does not contain searchable lexical terms")
    return " ".join(terms)


class HybridRetriever:
    def __init__(self, graph: HybridGraph, cohere: EmbedderReranker) -> None:
        self._graph = graph
        self._cohere = cohere

    def retrieve(
        self,
        question: str,
        *,
        candidate_limit: int = 30,
        top_n: int = 10,
    ) -> HybridResult:
        if not question.strip():
            raise ValueError("hybrid retrieval question cannot be empty")
        if not 1 <= candidate_limit <= 200:
            raise ValueError("candidate_limit must be between 1 and 200")
        degradations: list[str] = []
        try:
            vector = self._cohere.embed(
                (question,),
                input_type=EmbedInputType.SEARCH_QUERY,
            )[0]
            dense_ids = self._graph.dense_candidates(vector, candidate_limit)
        except RuntimeError:
            dense_ids = ()
            degradations.append("dense_unavailable")
        lexical_ids = self._graph.lexical_candidates(lexical_terms(question), candidate_limit)
        channels = tuple(
            channel
            for channel in (
                tuple(
                    RetrievalCandidate(candidate_id=value, channel="dense", rank=rank)
                    for rank, value in enumerate(dense_ids, start=1)
                ),
                tuple(
                    RetrievalCandidate(candidate_id=value, channel="lexical", rank=rank)
                    for rank, value in enumerate(lexical_ids, start=1)
                ),
            )
            if channel
        )
        claim_id = f"hybrid:claim:{sha256(question.encode()).hexdigest()[:24]}"
        if not channels:
            verification = verify_evidence_pack(EvidencePack(claim_ids=(claim_id,), citations=()))
            return HybridResult(
                status=HybridStatus.ABSTAINED,
                channel_counts={"dense": 0, "lexical": 0},
                evidence=(),
                reranking=None,
                citations=(),
                verification=verification,
                degradations=tuple(degradations),
            )
        fused = reciprocal_rank_fusion(channels, limit=min(candidate_limit * 2, 60))
        expanded = self._graph.expand_evidence(tuple(candidate.candidate_id for candidate in fused))
        rerankable = sum(1 for candidate in fused if candidate.candidate_id in expanded)
        if rerankable == 0:
            verification = verify_evidence_pack(EvidencePack(claim_ids=(claim_id,), citations=()))
            return HybridResult(
                status=HybridStatus.ABSTAINED,
                channel_counts={"dense": len(dense_ids), "lexical": len(lexical_ids)},
                evidence=(),
                reranking=None,
                citations=(),
                verification=verification,
                degradations=tuple(degradations),
            )
        reranking = rerank_fused_candidates(
            question,
            fused,
            {key: value.text_private for key, value in expanded.items()},
            self._cohere,
            top_n=min(top_n, rerankable),
        )
        if reranking.status is RerankStatus.FALLBACK_RRF:
            degradations.append("rerank_unavailable")
        evidence = tuple(expanded[item.candidate_id] for item in reranking.candidates)
        citations = tuple(
            EvidenceCitation(
                citation_id=f"hybrid:citation:{index}",
                chunk_node_id=document.candidate_id,
                source_node_id=document.source_node_id,
                source_hash=document.source_hash,
                authority_score=document.authority_score,
                supports_claim_ids=(claim_id,),
                quality_flags=document.quality_flags,
            )
            for index, document in enumerate(evidence, start=1)
        )
        verification = verify_evidence_pack(
            EvidencePack(claim_ids=(claim_id,), citations=citations)
        )
        if verification.status is VerificationStatus.ABSTAINED:
            status = HybridStatus.ABSTAINED
        elif degradations:
            status = HybridStatus.VERIFIED_DEGRADED
        else:
            status = HybridStatus.VERIFIED
        return HybridResult(
            status=status,
            channel_counts={"dense": len(dense_ids), "lexical": len(lexical_ids)},
            evidence=evidence,
            reranking=reranking,
            citations=citations,
            verification=verification,
            degradations=tuple(degradations),
        )


class Neo4jHybridGraph:
    """Read-only Neo4j implementation of dense, lexical, and evidence expansion stages."""

    def __init__(
        self,
        driver: Driver,
        *,
        database: str = "neo4j",
        vector_index: str = "evidence_vector_cohere_embed_v4_0_1536",
        lexical_index: str = "evidence_lexical",
    ) -> None:
        self._driver = driver
        self._database = database
        self._vector_index = vector_index
        self._lexical_index = lexical_index

    @classmethod
    def connect(
        cls,
        uri: str,
        *,
        database: str = "neo4j",
        username: str | None = None,
        password: str | None = None,
    ) -> Self:
        if (username is None) != (password is None):
            raise ValueError("Neo4j username and password must be supplied together")
        if username is None:
            auth = None
        else:
            assert password is not None
            auth = (username, password)
        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity()
        return cls(driver, database=database)

    def dense_candidates(self, vector: tuple[float, ...], limit: int) -> tuple[str, ...]:
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return tuple(
                str(record["node_id"])
                for record in session.run(
                    "CALL db.index.vector.queryNodes($index_name, $limit, $embedding) "
                    "YIELD node, score RETURN node.node_id AS node_id ORDER BY score DESC",
                    {
                        "index_name": self._vector_index,
                        "limit": limit,
                        "embedding": list(vector),
                    },
                )
            )

    def lexical_candidates(self, query: str, limit: int) -> tuple[str, ...]:
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return tuple(
                str(record["node_id"])
                for record in session.run(
                    "CALL db.index.fulltext.queryNodes($index_name, $query, {limit: $limit}) "
                    "YIELD node, score RETURN node.node_id AS node_id ORDER BY score DESC",
                    {"index_name": self._lexical_index, "query": query, "limit": limit},
                )
            )

    def expand_evidence(
        self,
        candidate_ids: tuple[str, ...],
    ) -> Mapping[str, EvidenceDocument]:
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            rows = tuple(
                record.data()
                for record in session.run(
                    "UNWIND range(0, size($node_ids) - 1) AS position "
                    "WITH position, $node_ids[position] AS node_id "
                    "MATCH (chunk:EvidenceChunk {node_id: node_id}) "
                    "MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
                    "RETURN position, chunk.node_id AS candidate_id, "
                    "coalesce(chunk.semantic_summary_private, '') + '\\nEvidence: ' + "
                    "coalesce(chunk.normalized_text_private, '') AS text_private, "
                    "min(source.node_id) AS source_node_id, chunk.source_hash AS source_hash, "
                    "coalesce(chunk.quality_flags, []) AS quality_flags ORDER BY position",
                    {"node_ids": list(candidate_ids)},
                )
            )
        documents: dict[str, EvidenceDocument] = {}
        for row in rows:
            candidate_id = str(row["candidate_id"])
            documents[candidate_id] = EvidenceDocument(
                candidate_id=candidate_id,
                text_private=str(row["text_private"]).strip(),
                source_node_id=str(row["source_node_id"]),
                source_hash=str(row["source_hash"]),
                authority_score=Decimal("0.80"),
                quality_flags=tuple(str(value) for value in row["quality_flags"]),
            )
        return documents

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
