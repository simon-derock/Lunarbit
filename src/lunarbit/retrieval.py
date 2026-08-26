from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from lunarbit.graph import RelationshipType
from lunarbit.models import ContractModel

RETRIEVAL_POLICY_VERSION = "hybrid-retrieval-v1.0.0"
_WRITE_KEYWORDS = re.compile(r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP)\b", re.I)


class QueryIntent(StrEnum):
    EXACT_GRAPH = "exact_graph"
    FINANCIAL_AGGREGATION = "financial_aggregation"
    LEXICAL_LOOKUP = "lexical_lookup"
    SEMANTIC_DISCOVERY = "semantic_discovery"
    EVIDENCE_REQUEST = "evidence_request"
    MULTI_HOP_ECONOMIC = "multi_hop_economic"


class FactFamily(StrEnum):
    CUSTOMER_PAYABLE_TOTAL = "customer_payable_total"
    RESTAURANT_TAXABLE_SUPPLY = "restaurant_taxable_supply"
    PLATFORM_SERVICE_FEE = "platform_service_fee"
    GROCERY_ITEM_TAX = "grocery_item_tax"
    DELIVERY_PERSON_MENTION = "delivery_person_mention"
    ACTUAL_BANK_DEBIT = "actual_bank_debit"


_SOURCE_AUTHORITY: dict[FactFamily, dict[str, Decimal]] = {
    FactFamily.CUSTOMER_PAYABLE_TOTAL: {
        "order_summary": Decimal("1.00"),
        "restaurant_invoice": Decimal("0.45"),
        "platform_fee_invoice": Decimal("0.35"),
    },
    FactFamily.RESTAURANT_TAXABLE_SUPPLY: {
        "restaurant_invoice": Decimal("1.00"),
        "order_summary": Decimal("0.55"),
    },
    FactFamily.PLATFORM_SERVICE_FEE: {
        "platform_fee_invoice": Decimal("1.00"),
        "order_summary": Decimal("0.65"),
    },
    FactFamily.GROCERY_ITEM_TAX: {
        "seller_tax_invoice": Decimal("1.00"),
        "order_summary": Decimal("0.40"),
    },
    FactFamily.DELIVERY_PERSON_MENTION: {
        "order_summary": Decimal("1.00"),
        "delivery_invoice": Decimal("0.90"),
    },
    FactFamily.ACTUAL_BANK_DEBIT: {
        "bank_statement": Decimal("1.00"),
    },
}


def authority_score(fact_family: FactFamily, source_kind: str) -> Decimal:
    """Return a fact-specific authority score; unknown pairings have no authority."""
    return _SOURCE_AUTHORITY[fact_family].get(source_kind, Decimal("0"))


class TraversalAction(StrEnum):
    RESOLVE_ENTITY = "resolve_entity"
    SEARCH_EVIDENCE = "search_evidence"
    READ_NODE_FACTS = "read_node_facts"
    EXPAND_NEIGHBORS = "expand_neighbors"
    RUN_METRIC = "run_metric"
    RUN_RECONCILIATION = "run_reconciliation"
    VERIFY_PATH = "verify_path"
    FINISH_ANSWER = "finish_answer"


class TraversalPolicy(ContractModel):
    maximum_depth: int = Field(default=4, ge=4, le=6)
    candidate_paths_per_step: int = Field(default=2, ge=2, le=3)
    maximum_actions: int = Field(default=12, ge=1, le=64)
    row_limit: int = Field(default=50, ge=1, le=200)
    relationship_allowlist: tuple[RelationshipType, ...] = tuple(RelationshipType)
    policy_version: str = RETRIEVAL_POLICY_VERSION

    @model_validator(mode="after")
    def relationships_are_unique(self) -> TraversalPolicy:
        if len(set(self.relationship_allowlist)) != len(self.relationship_allowlist):
            raise ValueError("relationship allowlist cannot contain duplicates")
        return self


class TraversalStep(ContractModel):
    action: TraversalAction
    depth: int = Field(ge=0)
    relationship_type: RelationshipType | None = None

    @model_validator(mode="after")
    def expansion_declares_relationship(self) -> TraversalStep:
        if self.action is TraversalAction.EXPAND_NEIGHBORS and self.relationship_type is None:
            raise ValueError("neighbor expansion requires a relationship type")
        if (
            self.action is not TraversalAction.EXPAND_NEIGHBORS
            and self.relationship_type is not None
        ):
            raise ValueError("only neighbor expansion may declare a relationship type")
        return self


def validate_traversal(
    steps: Sequence[TraversalStep],
    policy: TraversalPolicy,
) -> tuple[TraversalStep, ...]:
    """Validate a proposed graph path before any database action is executed."""
    bounded = tuple(steps)
    if len(bounded) > policy.maximum_actions:
        raise ValueError("graph action budget exceeded")
    previous_depth = 0
    for index, step in enumerate(bounded):
        if step.depth > policy.maximum_depth:
            raise ValueError("maximum traversal depth exceeded")
        if step.depth > previous_depth + 1:
            raise ValueError("traversal depth cannot skip graph levels")
        previous_depth = step.depth
        if (
            step.action is TraversalAction.EXPAND_NEIGHBORS
            and step.relationship_type not in policy.relationship_allowlist
        ):
            raise ValueError("relationship allowlist rejected graph expansion")
        if step.action is TraversalAction.FINISH_ANSWER and index != len(bounded) - 1:
            raise ValueError("finish_answer must terminate the traversal")
    return bounded


class QueryTemplate(StrEnum):
    MERCHANT_ORDER_RANKING = "merchant_order_ranking"
    MERCHANT_ORDER_COUNT = "merchant_order_count"
    MERCHANT_ITEM_PRICE_HISTORY = "merchant_item_price_history"
    DELIVERY_MENTION_COUNT = "delivery_mention_count"
    FINANCIAL_COMPONENT_SUM = "financial_component_sum"
    EVIDENCE_FOR_MONEY_COMPONENT = "evidence_for_money_component"
    ORDER_RECONSTRUCTION = "order_reconstruction"
    FULLTEXT_EVIDENCE = "fulltext_evidence"


class QueryClassification(ContractModel):
    intent: QueryIntent
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    signals: tuple[str, ...]
    policy_version: str = RETRIEVAL_POLICY_VERSION


def classify_query(question: str) -> QueryClassification:
    normalized = " ".join(question.casefold().split())
    if not normalized:
        raise ValueError("query cannot be empty")
    signals: tuple[str, ...]
    if any(token in normalized for token in ("offset", "comparable", "multi-hop")) and any(
        token in normalized for token in ("discount", "fee", "price", "meal")
    ):
        intent = QueryIntent.MULTI_HOP_ECONOMIC
        signals = ("comparison", "cross-domain")
    elif any(token in normalized for token in ("prove", "show evidence", "source for")):
        intent = QueryIntent.EVIDENCE_REQUEST
        signals = ("evidence-language",)
    elif normalized.startswith(("find ", "search ", "locate ")) or (
        "containing" in normalized or "invoice rows" in normalized
    ):
        intent = QueryIntent.LEXICAL_LOOKUP
        signals = ("lexical-language",)
    elif any(token in normalized for token in ("felt ", "seemed ", "which orders")):
        intent = QueryIntent.SEMANTIC_DISCOVERY
        signals = ("semantic-language",)
    elif any(
        token in normalized
        for token in ("how much", "total fee", "total spend", "did i pay", "sum of")
    ):
        intent = QueryIntent.FINANCIAL_AGGREGATION
        signals = ("aggregation-language",)
    else:
        intent = QueryIntent.EXACT_GRAPH
        signals = ("exact-default",)
    return QueryClassification(intent=intent, confidence=Decimal("0.95"), signals=signals)


class GovernedQuery(ContractModel):
    template: QueryTemplate
    cypher: str = Field(min_length=1)
    parameters: dict[str, str | int]
    row_limit: int = Field(ge=1, le=200)
    read_only: bool = True
    policy_version: str = RETRIEVAL_POLICY_VERSION

    @model_validator(mode="after")
    def query_is_read_only(self) -> GovernedQuery:
        if not self.read_only or _WRITE_KEYWORDS.search(self.cypher):
            raise ValueError("governed retrieval queries must remain read-only")
        return self


_TEMPLATES: dict[QueryTemplate, tuple[str, frozenset[str]]] = {
    QueryTemplate.MERCHANT_ORDER_RANKING: (
        "MATCH (merchant:Merchant)<-[:OUTLET_OF]-(outlet:Outlet)"
        "<-[:ORDERED_FROM]-(order:Order) "
        "OPTIONAL MATCH (order)-[:DOCUMENTED_BY]->(source:LunarbitNode)-[:HAS_CHUNK]->"
        "(chunk:EvidenceChunk) "
        "WITH merchant, count(DISTINCT order) AS order_count, "
        "collect(DISTINCT {chunk_id: chunk.node_id, source_id: source.node_id, "
        "source_hash: chunk.source_hash})[..$limit] AS evidence "
        "UNWIND CASE WHEN size(evidence) = 0 THEN [null] ELSE evidence END AS item "
        "RETURN merchant.display_name_private AS merchant_name, order_count, "
        "item.chunk_id AS chunk_id, item.source_id AS source_id, item.source_hash AS source_hash "
        "ORDER BY order_count DESC, merchant_name LIMIT $limit",
        frozenset({"limit"}),
    ),
    QueryTemplate.MERCHANT_ORDER_COUNT: (
        "MATCH (merchant:Merchant)<-[:OUTLET_OF]-(outlet:Outlet)"
        "<-[:ORDERED_FROM]-(order:Order) "
        "WHERE merchant.normalized_name_private = $normalized_name "
        "MATCH (order)-[:DOCUMENTED_BY]->(source:LunarbitNode)-[:HAS_CHUNK]->"
        "(chunk:EvidenceChunk) "
        "WITH count(DISTINCT order) AS order_count, "
        "collect(DISTINCT {chunk_id: chunk.node_id, source_id: source.node_id, "
        "source_hash: chunk.source_hash})[..$limit] AS evidence "
        "UNWIND evidence AS item RETURN order_count, item.chunk_id AS chunk_id, "
        "item.source_id AS source_id, item.source_hash AS source_hash",
        frozenset({"normalized_name", "limit"}),
    ),
    QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY: (
        "MATCH (merchant:Merchant)<-[:OUTLET_OF]-(outlet:Outlet)"
        "<-[:ORDERED_FROM]-(order:Order)-[:HAS_ITEM_OBSERVATION]->"
        "(observation:ItemObservation)-[:LISTING_OF]->(item:MerchantItem) "
        "WHERE merchant.normalized_name_private = $merchant_name "
        "AND item.normalized_name_private CONTAINS $item_name "
        "MATCH (observation)-[:EVIDENCED_BY]->(chunk:EvidenceChunk) "
        "MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
        "OPTIONAL MATCH (order)-[:DOCUMENTED_BY]->(message:SourceMessage) "
        "RETURN order.node_id AS order_id, observation.observed_amount AS amount, "
        "observation.currency AS currency, min(message.occurred_at) AS occurred_at, "
        "chunk.node_id AS chunk_id, chunk.source_hash AS source_hash, "
        "source.node_id AS source_id ORDER BY occurred_at, order.node_id LIMIT $limit",
        frozenset({"merchant_name", "item_name", "limit"}),
    ),
    QueryTemplate.DELIVERY_MENTION_COUNT: (
        "MATCH (order:Order)-[:HAS_DELIVERY_MENTION]->(mention:PersonMention) "
        "MATCH (mention)-[:MENTIONED_IN]->(chunk:EvidenceChunk) "
        "MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
        "WHERE mention.normalized_value_private = $normalized_name "
        "RETURN order.node_id AS order_id, mention.node_id AS mention_id, "
        "chunk.node_id AS chunk_id, chunk.source_hash AS source_hash, "
        "source.node_id AS source_id LIMIT $limit",
        frozenset({"normalized_name", "limit"}),
    ),
    QueryTemplate.FINANCIAL_COMPONENT_SUM: (
        "MATCH (order:Order)-[:HAS_COMPONENT]->(component:MoneyComponent) "
        "WHERE component.component_type = $component_type "
        "AND order.platform = $platform "
        "OPTIONAL MATCH (component)-[:EVIDENCED_BY]->(chunk:EvidenceChunk) "
        "OPTIONAL MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
        "RETURN component.node_id AS component_id, component.amount AS amount, "
        "component.currency AS currency, chunk.node_id AS chunk_id, "
        "chunk.source_hash AS source_hash, source.node_id AS source_id "
        "ORDER BY component.node_id SKIP $offset LIMIT $limit",
        frozenset({"component_type", "platform", "offset", "limit"}),
    ),
    QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT: (
        "MATCH (component:MoneyComponent)-[:EVIDENCED_BY]->(chunk:EvidenceChunk) "
        "WHERE component.node_id = $component_id "
        "MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(chunk) "
        "RETURN component.node_id AS component_id, component.amount AS amount, "
        "component.currency AS currency, chunk.node_id AS chunk_id, "
        "chunk.source_hash AS source_hash, source.node_id AS source_id LIMIT $limit",
        frozenset({"component_id", "limit"}),
    ),
    QueryTemplate.ORDER_RECONSTRUCTION: (
        "MATCH (order:Order) WHERE order.node_id = $order_id "
        "OPTIONAL MATCH (order)-[relationship]->(neighbor:LunarbitNode) "
        "OPTIONAL MATCH (order)-[:DOCUMENTED_BY]->(source:LunarbitNode)"
        "-[:HAS_CHUNK]->(chunk:EvidenceChunk) "
        "RETURN order.node_id AS order_id, type(relationship) AS relationship_type, "
        "neighbor.node_id AS neighbor_id, chunk.node_id AS chunk_id, "
        "chunk.source_hash AS source_hash, source.node_id AS source_id LIMIT $limit",
        frozenset({"order_id", "limit"}),
    ),
    QueryTemplate.FULLTEXT_EVIDENCE: (
        "CALL db.index.fulltext.queryNodes('evidence_lexical', $query) "
        "YIELD node, score MATCH (source:LunarbitNode)-[:HAS_CHUNK]->(node) "
        "RETURN node.node_id AS chunk_id, node.source_hash AS source_hash, "
        "source.node_id AS source_id, score ORDER BY score DESC LIMIT $limit",
        frozenset({"query", "limit"}),
    ),
}


def governed_query(
    template: QueryTemplate,
    parameters: Mapping[str, str | int],
) -> GovernedQuery:
    cypher, expected = _TEMPLATES[template]
    supplied = set(parameters)
    if supplied != expected:
        missing = expected - supplied
        extra = supplied - expected
        detail = "unexpected parameters" if extra else "missing parameters"
        raise ValueError(f"{detail}: {sorted(extra or missing)}")
    limit = parameters["limit"]
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("row limit must be between 1 and 200")
    if any(
        not isinstance(value, (str, int)) or isinstance(value, bool)
        for value in parameters.values()
    ):
        raise ValueError("query parameters must be strings or integers")
    return GovernedQuery(
        template=template,
        cypher=cypher,
        parameters=dict(parameters),
        row_limit=limit,
    )


class RetrievalCandidate(ContractModel):
    candidate_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    rank: int = Field(ge=1)


class FusedCandidate(ContractModel):
    candidate_id: str = Field(min_length=1)
    score: Decimal = Field(gt=Decimal("0"))
    channels: tuple[str, ...] = Field(min_length=1)
    channel_ranks: dict[str, int]


def reciprocal_rank_fusion(
    ranked_channels: Iterable[Sequence[RetrievalCandidate]],
    *,
    rank_constant: int = 60,
    limit: int = 30,
) -> tuple[FusedCandidate, ...]:
    if rank_constant < 1 or limit < 1:
        raise ValueError("fusion rank constant and limit must be positive")
    scores: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    ranks: dict[str, dict[str, int]] = defaultdict(dict)
    for channel in ranked_channels:
        seen: set[str] = set()
        for candidate in channel:
            if candidate.candidate_id in seen:
                raise ValueError("a retrieval channel cannot repeat a candidate")
            seen.add(candidate.candidate_id)
            scores[candidate.candidate_id] += Decimal(1) / Decimal(rank_constant + candidate.rank)
            previous = ranks[candidate.candidate_id].get(candidate.channel)
            ranks[candidate.candidate_id][candidate.channel] = (
                candidate.rank if previous is None else min(previous, candidate.rank)
            )
    fused = tuple(
        FusedCandidate(
            candidate_id=candidate_id,
            score=score,
            channels=tuple(sorted(ranks[candidate_id])),
            channel_ranks=dict(sorted(ranks[candidate_id].items())),
        )
        for candidate_id, score in scores.items()
    )
    return tuple(sorted(fused, key=lambda item: (-item.score, item.candidate_id))[:limit])


class EvidenceCitation(ContractModel):
    citation_id: str = Field(min_length=1)
    chunk_node_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    supports_claim_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...]


class EvidencePack(ContractModel):
    claim_ids: tuple[str, ...] = Field(min_length=1)
    citations: tuple[EvidenceCitation, ...]


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    ABSTAINED = "abstained"


class EvidenceVerification(ContractModel):
    status: VerificationStatus
    covered_claim_ids: tuple[str, ...]
    missing_claim_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]
    abstention_reason: str | None = None


def verify_evidence_pack(pack: EvidencePack) -> EvidenceVerification:
    claims = set(pack.claim_ids)
    covered = {
        claim_id
        for citation in pack.citations
        for claim_id in citation.supports_claim_ids
        if claim_id in claims
    }
    missing = claims - covered
    conflict = any("conflicting" in citation.quality_flags for citation in pack.citations)
    if conflict:
        status = VerificationStatus.ABSTAINED
        reason = "conflicting_evidence"
    elif missing:
        status = VerificationStatus.ABSTAINED
        reason = "incomplete_evidence_coverage"
    elif not pack.citations:
        status = VerificationStatus.ABSTAINED
        reason = "no_evidence"
    else:
        status = VerificationStatus.VERIFIED
        reason = None
    return EvidenceVerification(
        status=status,
        covered_claim_ids=tuple(sorted(covered)),
        missing_claim_ids=tuple(sorted(missing)),
        citation_ids=tuple(sorted(citation.citation_id for citation in pack.citations)),
        abstention_reason=reason,
    )
