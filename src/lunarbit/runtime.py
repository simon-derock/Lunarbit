from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol, Self

from neo4j import READ_ACCESS, Driver, GraphDatabase
from pydantic import Field

from lunarbit.agent import QueryPlan, build_query_plan
from lunarbit.models import ContractModel
from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    EvidenceVerification,
    GovernedQuery,
    QueryTemplate,
    VerificationStatus,
    governed_query,
    verify_evidence_pack,
)


class QuerySlots(ContractModel):
    merchant_name: str | None = Field(default=None, min_length=1, max_length=160)
    item_name: str | None = Field(default=None, min_length=1, max_length=160)
    delivery_name: str | None = Field(default=None, min_length=1, max_length=160)
    platform: str | None = Field(default=None, min_length=1, max_length=40)
    component_type: str | None = Field(default=None, min_length=1, max_length=80)
    component_id: str | None = Field(default=None, min_length=1, max_length=160)
    order_id: str | None = Field(default=None, min_length=1, max_length=160)
    lexical_query: str | None = Field(default=None, min_length=1, max_length=300)
    limit: int = Field(default=50, ge=1, le=200)


class RuntimeRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)
    slots: QuerySlots


def _require(value: str | None, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is required for the selected governed query")
    return value


def _parameters(template: QueryTemplate, slots: QuerySlots) -> dict[str, str | int]:
    limit = slots.limit
    if template is QueryTemplate.MERCHANT_ORDER_COUNT:
        return {"normalized_name": _require(slots.merchant_name, "merchant_name"), "limit": limit}
    if template is QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY:
        return {
            "merchant_name": _require(slots.merchant_name, "merchant_name"),
            "item_name": _require(slots.item_name, "item_name"),
            "limit": limit,
        }
    if template is QueryTemplate.DELIVERY_MENTION_COUNT:
        return {"normalized_name": _require(slots.delivery_name, "delivery_name"), "limit": limit}
    if template is QueryTemplate.FINANCIAL_COMPONENT_SUM:
        return {
            "component_type": _require(slots.component_type, "component_type"),
            "platform": _require(slots.platform, "platform"),
            "limit": limit,
        }
    if template is QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT:
        return {"component_id": _require(slots.component_id, "component_id"), "limit": limit}
    if template is QueryTemplate.ORDER_RECONSTRUCTION:
        return {"order_id": _require(slots.order_id, "order_id"), "limit": limit}
    if template is QueryTemplate.FULLTEXT_EVIDENCE:
        return {"query": _require(slots.lexical_query, "lexical_query"), "limit": limit}
    raise ValueError(f"unsupported governed template: {template}")


def bind_query_plan(plan: QueryPlan, slots: QuerySlots) -> tuple[GovernedQuery, ...]:
    return tuple(
        governed_query(template, _parameters(template, slots))
        for template in plan.selected_templates
    )


class GraphReader(Protocol):
    def run(self, query: GovernedQuery) -> tuple[Mapping[str, Any], ...]: ...


class Neo4jGraphReader:
    """Execute only prevalidated read queries through a Neo4j read session."""

    def __init__(self, driver: Driver, *, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

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

    def run(self, query: GovernedQuery) -> tuple[Mapping[str, Any], ...]:
        if not query.read_only:
            raise ValueError("runtime graph reader rejected a non-read query")
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return tuple(record.data() for record in session.run(query.cypher, query.parameters))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class RuntimeStatus(StrEnum):
    VERIFIED = "verified"
    ABSTAINED = "abstained"


class GroundedContext(ContractModel):
    status: RuntimeStatus
    question: str
    plan: QueryPlan
    fact_count: int = Field(ge=0)
    calculation: str | None
    citations: tuple[EvidenceCitation, ...]
    verification: EvidenceVerification
    abstention_reason: str | None = None


def _claim_id(request: RuntimeRequest, plan: QueryPlan) -> str:
    identity = "|".join((request.question, *(item.value for item in plan.selected_templates)))
    return f"runtime:claim:{sha256(identity.encode()).hexdigest()[:24]}"


def _citation_from_row(
    row: Mapping[str, Any],
    *,
    claim_id: str,
    index: int,
) -> EvidenceCitation | None:
    chunk_id = row.get("chunk_id")
    source_id = row.get("source_id")
    source_hash = row.get("source_hash")
    if not all(isinstance(value, str) and value for value in (chunk_id, source_id, source_hash)):
        return None
    flags = row.get("quality_flags", ())
    quality_flags = tuple(str(value) for value in flags) if isinstance(flags, (list, tuple)) else ()
    return EvidenceCitation(
        citation_id=f"runtime:citation:{index}",
        chunk_node_id=str(chunk_id),
        source_node_id=str(source_id),
        source_hash=str(source_hash),
        authority_score=Decimal("0.90"),
        supports_claim_ids=(claim_id,),
        quality_flags=quality_flags,
    )


def _money_calculation(rows: tuple[Mapping[str, Any], ...]) -> tuple[int, str | None]:
    components: dict[str, tuple[Decimal, str]] = {}
    for row in rows:
        component_id = row.get("component_id")
        amount = row.get("amount")
        currency = row.get("currency")
        if not all(isinstance(value, str) and value for value in (component_id, currency)):
            continue
        parsed = Decimal(str(amount))
        previous = components.get(str(component_id))
        candidate = (parsed, str(currency))
        if previous is not None and previous != candidate:
            raise ValueError("one money component returned conflicting normalized values")
        components[str(component_id)] = candidate
    if not components:
        return 0, None
    currencies = {currency for _, currency in components.values()}
    if len(currencies) != 1:
        raise ValueError("runtime refuses to aggregate mixed currencies")
    currency = currencies.pop()
    ordered = [components[key][0] for key in sorted(components)]
    total = sum(ordered, start=Decimal("0"))
    terms = " + ".join(f"{currency} {amount:.2f}" for amount in ordered)
    return len(components), f"{terms} = {currency} {total:.2f}"


def retrieve_grounded_context(request: RuntimeRequest, reader: GraphReader) -> GroundedContext:
    plan = build_query_plan(request.question)
    queries = bind_query_plan(plan, request.slots)
    rows = tuple(row for query in queries for row in reader.run(query))
    claim_id = _claim_id(request, plan)
    citations = tuple(
        citation
        for index, row in enumerate(rows, start=1)
        if (citation := _citation_from_row(row, claim_id=claim_id, index=index)) is not None
    )
    if QueryTemplate.FINANCIAL_COMPONENT_SUM in plan.selected_templates:
        fact_count, calculation = _money_calculation(rows)
    else:
        fact_count, calculation = len(rows), None
    verification = verify_evidence_pack(EvidencePack(claim_ids=(claim_id,), citations=citations))
    status = (
        RuntimeStatus.VERIFIED
        if verification.status is VerificationStatus.VERIFIED and fact_count > 0
        else RuntimeStatus.ABSTAINED
    )
    reason = verification.abstention_reason
    if status is RuntimeStatus.ABSTAINED and reason is None:
        reason = "no_graph_facts"
    return GroundedContext(
        status=status,
        question=request.question,
        plan=plan,
        fact_count=fact_count,
        calculation=calculation,
        citations=citations,
        verification=verification,
        abstention_reason=reason,
    )
