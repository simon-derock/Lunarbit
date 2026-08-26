from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
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


class MissingQuerySlotError(ValueError):
    """Raised when a governed template needs an explicit runtime slot."""


class RuntimeRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)
    slots: QuerySlots


def _require(value: str | None, name: str) -> str:
    if value is None:
        raise MissingQuerySlotError(f"{name} is required for the selected governed query")
    return value


def _parameters(template: QueryTemplate, slots: QuerySlots) -> dict[str, str | int]:
    limit = slots.limit
    if template is QueryTemplate.MERCHANT_ORDER_RANKING:
        return {"limit": limit}
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
            "offset": 0,
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
    direct_answer: str | None = Field(default=None, max_length=2_000)
    calculation: str | None = Field(default=None, max_length=2_000)
    limitations: tuple[str, ...]
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


def _money_calculation(
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[int, str | None, Decimal | None, str | None]:
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
        return 0, None, None, None
    currencies = {currency for _, currency in components.values()}
    if len(currencies) != 1:
        raise ValueError("runtime refuses to aggregate mixed currencies")
    currency = currencies.pop()
    ordered_ids = tuple(sorted(components))
    ordered = tuple(components[key][0] for key in ordered_ids)
    total = sum(ordered, start=Decimal("0"))
    if len(ordered) <= 20:
        terms = " + ".join(f"{currency} {amount:.2f}" for amount in ordered)
        calculation = f"{terms} = {currency} {total:.2f}"
    else:
        canonical_terms = "\n".join(
            f"{component_id}|{currency}|{components[component_id][0]}"
            for component_id in ordered_ids
        )
        digest = sha256(canonical_terms.encode()).hexdigest()
        calculation = (
            f"Decimal sum of {len(ordered)} distinct source-backed components = "
            f"{currency} {total:.2f}; ordered-term SHA-256={digest}"
        )
    return len(components), calculation, total, currency


def _price_history_synthesis(
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[int, str | None, str | None, tuple[str, ...]]:
    observations: dict[str, tuple[datetime, Decimal, str]] = {}
    for row in rows:
        order_id = row.get("order_id")
        amount = row.get("amount")
        currency = row.get("currency")
        occurred_at = row.get("occurred_at")
        if not all(
            value is not None and str(value).strip()
            for value in (order_id, amount, currency, occurred_at)
        ):
            continue
        timestamp = datetime.fromisoformat(str(occurred_at))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("price-history rows require timezone-aware occurrence times")
        candidate = (timestamp, Decimal(str(amount)), str(currency))
        previous = observations.get(str(order_id))
        if previous is not None and previous != candidate:
            raise ValueError("one order returned conflicting item-price observations")
        observations[str(order_id)] = candidate
    if not observations:
        return 0, None, None, ()
    currencies = {currency for _, _, currency in observations.values()}
    if len(currencies) != 1:
        raise ValueError("runtime refuses to compare mixed-currency item prices")
    ordered = tuple(sorted(observations.values(), key=lambda value: value[0]))
    currency = currencies.pop()
    if len(ordered) == 1:
        occurred_at, amount, _ = ordered[0]
        return (
            1,
            f"The source-backed item price was {currency} {amount:.2f} on "
            f"{occurred_at.date().isoformat()}.",
            None,
            ("Only one matching price observation was available for this scope.",),
        )
    earliest, latest = ordered[0], ordered[-1]
    delta = latest[1] - earliest[1]
    if earliest[1] == 0:
        calculation = f"{currency} {latest[1]:.2f} - {currency} 0.00 = {currency} {delta:.2f}"
    else:
        percentage = delta / earliest[1] * Decimal("100")
        calculation = (
            f"{currency} {latest[1]:.2f} - {currency} {earliest[1]:.2f} = "
            f"{currency} {delta:.2f} ({percentage:.2f}%)"
        )
    return (
        len(ordered),
        f"The source-backed item price changed from {currency} {earliest[1]:.2f} on "
        f"{earliest[0].date().isoformat()} to {currency} {latest[1]:.2f} on "
        f"{latest[0].date().isoformat()}.",
        calculation,
        (
            "The comparison covers matched merchant-item observations, not a causal "
            "inflation estimate.",
        ),
    )


def _synthesize(
    plan: QueryPlan,
    slots: QuerySlots,
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[int, str | None, str | None, tuple[str, ...]]:
    if QueryTemplate.MERCHANT_ORDER_RANKING in plan.selected_templates:
        ranked: dict[str, int] = {}
        for row in rows:
            name = row.get("merchant_name")
            count = row.get("order_count")
            if isinstance(name, str) and isinstance(count, int):
                ranked[name] = count
        if not ranked:
            return 0, None, None, ()
        ordered = sorted(ranked.items(), key=lambda item: (-item[1], item[0]))
        preview = "; ".join(f"{name}: {count}" for name, count in ordered[:10])
        return (
            len(ordered),
            f"Restaurants ranked by source-backed order count: {preview}.",
            None,
            (
                "Counts use distinct reconstructed orders linked to reviewed "
                "merchant identities.",
            ),
        )
    if QueryTemplate.FINANCIAL_COMPONENT_SUM in plan.selected_templates:
        count, calculation, total, currency = _money_calculation(rows)
        if total is None or currency is None:
            return count, None, calculation, ()
        component = _require(slots.component_type, "component_type").replace("_", " ")
        platform = _require(slots.platform, "platform").title()
        noun = "component" if count == 1 else "components"
        return (
            count,
            f"The evidence-backed {component} total for {platform} is "
            f"{currency} {total:.2f} across {count} distinct {noun}.",
            calculation,
            ("This is a sum of source-asserted components, not a bank-confirmed debit.",),
        )
    if QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY in plan.selected_templates:
        return _price_history_synthesis(rows)
    if QueryTemplate.MERCHANT_ORDER_COUNT in plan.selected_templates:
        counts = {int(row["order_count"]) for row in rows if row.get("order_count") is not None}
        if len(counts) > 1:
            raise ValueError("merchant-order rows returned conflicting aggregate counts")
        count = counts.pop() if counts else 0
        noun = "order" if count == 1 else "orders"
        return (
            count,
            f"The graph links this merchant to {count} source-backed {noun}." if count else None,
            None,
            ("Merchant identity follows the current reviewed resolution state.",),
        )
    if QueryTemplate.DELIVERY_MENTION_COUNT in plan.selected_templates:
        order_ids = {str(row["order_id"]) for row in rows if row.get("order_id") is not None}
        count = len(order_ids)
        noun = "order" if count == 1 else "orders"
        return (
            count,
            (
                f"The source evidence links this delivery-person mention to {count} "
                f"distinct {noun}."
                if count
                else None
            ),
            None,
            (
                "Repeated names are mention-level evidence unless a reviewed person identity "
                "resolution exists.",
            ),
        )
    count = len(rows)
    direct_answer = (
        f"The governed graph query returned {count} source-backed facts." if count else None
    )
    return count, direct_answer, None, ()


def _execute_bounded(
    plan: QueryPlan,
    queries: tuple[GovernedQuery, ...],
    reader: GraphReader,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    rows: list[Mapping[str, Any]] = []
    actions = 0
    complete = True
    for query in queries:
        current = query
        while True:
            if actions >= plan.policy.maximum_actions:
                complete = False
                break
            page = reader.run(current)
            actions += 1
            rows.extend(page)
            if (
                current.template is not QueryTemplate.FINANCIAL_COMPONENT_SUM
                or len(page) < current.row_limit
            ):
                break
            if actions >= plan.policy.maximum_actions:
                complete = False
                break
            parameters = dict(current.parameters)
            parameters["offset"] = int(parameters["offset"]) + current.row_limit
            current = governed_query(current.template, parameters)
        if not complete:
            break
    return tuple(rows), complete


def retrieve_grounded_context(
    request: RuntimeRequest,
    reader: GraphReader,
    *,
    plan: QueryPlan | None = None,
) -> GroundedContext:
    plan = plan or build_query_plan(request.question)
    queries = bind_query_plan(plan, request.slots)
    rows, query_complete = _execute_bounded(plan, queries, reader)
    claim_id = _claim_id(request, plan)
    citations = tuple(
        citation
        for index, row in enumerate(rows, start=1)
        if (citation := _citation_from_row(row, claim_id=claim_id, index=index)) is not None
    )
    fact_count, proposed_answer, calculation, limitations = _synthesize(
        plan,
        request.slots,
        rows,
    )
    verification = verify_evidence_pack(EvidencePack(claim_ids=(claim_id,), citations=citations))
    if not query_complete:
        verification = EvidenceVerification(
            status=VerificationStatus.ABSTAINED,
            covered_claim_ids=(),
            missing_claim_ids=(claim_id,),
            citation_ids=verification.citation_ids,
            abstention_reason="query_action_budget_exhausted",
        )
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
        direct_answer=proposed_answer if status is RuntimeStatus.VERIFIED else None,
        calculation=calculation if status is RuntimeStatus.VERIFIED else None,
        limitations=limitations,
        citations=citations,
        verification=verification,
        abstention_reason=reason,
    )
