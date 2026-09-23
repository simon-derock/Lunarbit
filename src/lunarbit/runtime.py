from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol, Self

from neo4j import READ_ACCESS, Driver, GraphDatabase
from pydantic import Field

from lunarbit.agent import QueryDisposition, QueryPlan, build_query_plan
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

    def __init__(self, slot: str) -> None:
        self.slot = slot
        super().__init__(f"{slot} is required for the selected governed query")


class RuntimeRequest(ContractModel):
    question: str = Field(min_length=3, max_length=500)
    slots: QuerySlots


def _require(value: str | None, name: str) -> str:
    if value is None:
        raise MissingQuerySlotError(name)
    return value


def _parameters(template: QueryTemplate, slots: QuerySlots) -> dict[str, str | int]:
    limit = slots.limit
    if template is QueryTemplate.MERCHANT_ORDER_RANKING:
        return {"limit": limit}
    if template is QueryTemplate.MERCHANT_ORDER_COUNT:
        return {"normalized_name": _require(slots.merchant_name, "merchant_name"), "limit": limit}
    if template is QueryTemplate.MERCHANT_SPEND_TOTAL:
        return {"merchant_name": _require(slots.merchant_name, "merchant_name"), "limit": limit}
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
    if template is QueryTemplate.YEARLY_SPEND_TOTAL:
        return {"limit": limit}
    if template is QueryTemplate.FEE_DISCOUNT_ANALYSIS:
        return {"merchant_name": _require(slots.merchant_name, "merchant_name"), "limit": limit}
    if template is QueryTemplate.SPENDING_CHANGE_DECOMPOSITION:
        return {"limit": limit}
    if template is QueryTemplate.DELIVERY_FEE_COUNTERFACTUAL:
        return {"merchant_name": _require(slots.merchant_name, "merchant_name"), "limit": limit}
    if template is QueryTemplate.ITEM_PRICE_CHANGE_RANKING:
        return {"limit": limit}
    if template is QueryTemplate.PERSONAL_FOOD_PRICE_INDEX:
        return {"limit": limit}
    if template is QueryTemplate.SPENDING_ANOMALY_DETECTION:
        return {"limit": limit}
    if template is QueryTemplate.SPENDING_CONCENTRATION:
        return {"limit": limit}
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
    review_required: bool = False
    review_reason: str | None = None


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
            ("Counts use distinct reconstructed orders linked to reviewed merchant identities.",),
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
    if QueryTemplate.YEARLY_SPEND_TOTAL in plan.selected_templates:
        priority = {"customer_total": 3, "invoice_total": 2, "payment_assertion": 1}
        yearly_selected: dict[str, tuple[int, Decimal, str, str]] = {}
        for row in rows:
            order_id = row.get("order_id")
            year = row.get("year")
            amount = row.get("amount")
            currency = row.get("currency")
            component_type = str(row.get("component_type", ""))
            if order_id is None or year is None or amount is None or currency is None:
                continue
            yearly_candidate = (int(year), Decimal(str(amount)), str(currency), component_type)
            current = yearly_selected.get(str(order_id))
            if current is None or priority.get(component_type, 0) > priority.get(current[3], 0):
                yearly_selected[str(order_id)] = yearly_candidate
            elif (
                current[0] == yearly_candidate[0]
                and current[1] != yearly_candidate[1]
                and priority.get(component_type, 0) == priority.get(current[3], 0)
            ):
                yearly_selected.pop(str(order_id), None)
        if not yearly_selected:
            return 0, None, None, ("No source-backed customer totals were available.",)
        currencies = {value[2] for value in yearly_selected.values()}
        if len(currencies) != 1:
            return 0, None, None, ("Yearly totals use multiple currencies and cannot be combined.",)
        currency = currencies.pop()
        totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        counts: dict[int, int] = defaultdict(int)
        terms: dict[int, list[str]] = defaultdict(list)
        for year, amount, _currency, _component_type in yearly_selected.values():
            totals[year] += amount
            counts[year] += 1
            terms[year].append(f"{currency} {amount:.2f}")
        ordered_years = sorted(totals)
        preview = "; ".join(
            f"{year}: {currency} {totals[year]:.2f} across {counts[year]} "
            f"{'order' if counts[year] == 1 else 'orders'}"
            for year in ordered_years
        )
        calculation = "; ".join(
            f"{year}: {' + '.join(sorted(terms[year]))} = {currency} {totals[year]:.2f}"
            for year in ordered_years
        )
        return (
            len(yearly_selected),
            f"Yearly source-backed spending: {preview}.",
            calculation,
            ("Customer totals are preferred; invoice totals are used only when needed.",),
        )
    if QueryTemplate.FEE_DISCOUNT_ANALYSIS in plan.selected_templates:
        charges = {
            "packing_charge",
            "handling_fee",
            "delivery_charge",
            "platform_fee",
            "other_charge",
        }
        discounts = {"item_discount", "coupon_discount", "membership_benefit"}
        merchant_names = {
            str(row["merchant_name"]) for row in rows if row.get("merchant_name") is not None
        }
        if len(merchant_names) != 1:
            return 0, None, None, ("The merchant phrase matched multiple reviewed identities.",)
        currencies = {str(row["currency"]) for row in rows if row.get("currency") is not None}
        if len(currencies) != 1:
            return 0, None, None, ("Fee and discount components use multiple currencies.",)
        currency = currencies.pop()
        fee_total = sum(
            (Decimal(str(row["amount"])) for row in rows if row.get("component_type") in charges),
            Decimal("0"),
        )
        discount_total = sum(
            (Decimal(str(row["amount"])) for row in rows if row.get("component_type") in discounts),
            Decimal("0"),
        )
        if fee_total <= 0 and discount_total <= 0:
            return 0, None, None, ("No source-backed fee or discount components were available.",)
        net = fee_total - discount_total
        offset = (discount_total / fee_total * Decimal("100")) if fee_total else Decimal("0")
        merchant = next(iter(merchant_names))
        return (
            len(rows),
            f"At {merchant}, {currency} {fee_total:.2f} of fees were offset by "
            f"{currency} {discount_total:.2f} in discounts ({offset:.2f}% offset), "
            f"leaving a net fee burden of {currency} {net:.2f}.",
            f"{currency} {fee_total:.2f} - {currency} {discount_total:.2f} = {currency} {net:.2f}",
            ("Fees and discounts are source-asserted components, not an inferred promotion ROI.",),
        )
    if QueryTemplate.SPENDING_CHANGE_DECOMPOSITION in plan.selected_templates:
        priority = {"customer_total": 3, "invoice_total": 2, "payment_assertion": 1}
        decomposition_selected: dict[str, tuple[int, Decimal, str, str]] = {}
        for row in rows:
            order_id = row.get("order_id")
            year = row.get("year")
            amount = row.get("amount")
            currency = row.get("currency")
            component_type = str(row.get("component_type", ""))
            if order_id is None or year is None or amount is None or currency is None:
                continue
            decomposition_candidate = (
                int(year),
                Decimal(str(amount)),
                str(currency),
                component_type,
            )
            current = decomposition_selected.get(str(order_id))
            if current is None or priority.get(component_type, 0) > priority.get(current[3], 0):
                decomposition_selected[str(order_id)] = decomposition_candidate
        if not decomposition_selected:
            return 0, None, None, ("No source-backed order totals were available.",)
        currencies = {value[2] for value in decomposition_selected.values()}
        if len(currencies) != 1:
            return 0, None, None, ("Spending periods use multiple currencies.",)
        by_year: dict[int, list[Decimal]] = defaultdict(list)
        currency = currencies.pop()
        for year, amount, _currency, _component_type in decomposition_selected.values():
            by_year[year].append(amount)
        years = sorted(by_year)
        if len(years) < 2:
            return (
                len(decomposition_selected),
                None,
                None,
                ("At least two spending years are required.",),
            )
        base_year, current_year = years[-2:]
        base_count = Decimal(len(by_year[base_year]))
        current_count = Decimal(len(by_year[current_year]))
        base_total = sum(by_year[base_year], Decimal("0"))
        current_total = sum(by_year[current_year], Decimal("0"))
        base_average = base_total / base_count
        current_average = current_total / current_count
        volume_effect = (current_count - base_count) * base_average
        average_effect = current_count * (current_average - base_average)
        change = current_total - base_total
        if volume_effect + average_effect != change:
            return 0, None, None, ("The spending decomposition did not close exactly.",)
        return (
            len(decomposition_selected),
            f"Between {base_year} and {current_year}, spending increased by "
            f"{currency} {change:.2f}: {currency} {volume_effect:.2f} from order volume "
            f"and {currency} {average_effect:.2f} from average order cost.",
            f"{currency} {change:.2f} = {currency} {volume_effect:.2f} volume effect + "
            f"{currency} {average_effect:.2f} average-order effect",
            (
                "This decomposition separates order volume from average order cost; "
                "item-level price and mix attribution requires matched item observations.",
            ),
        )
    if QueryTemplate.ITEM_PRICE_CHANGE_RANKING in plan.selected_templates:
        observations: dict[str, list[tuple[datetime, Decimal, str]]] = defaultdict(list)
        for row in rows:
            item_name = row.get("item_name")
            amount = row.get("amount")
            currency = row.get("currency")
            occurred_at = row.get("occurred_at")
            if not all(
                value is not None and str(value).strip()
                for value in (item_name, amount, currency, occurred_at)
            ):
                continue
            timestamp = datetime.fromisoformat(str(occurred_at))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("item-price ranking rows require timezone-aware occurrence times")
            observations[str(item_name)].append((timestamp, Decimal(str(amount)), str(currency)))
        if not observations:
            return 0, None, None, ("No source-backed item price observations were available.",)
        changes: list[tuple[Decimal, Decimal, str, Decimal, Decimal, str]] = []
        currencies = {
            currency for values in observations.values() for _timestamp, _amount, currency in values
        }
        if len(currencies) != 1:
            return 0, None, None, ("Item price observations use multiple currencies.",)
        currency = currencies.pop()
        for item_name, values in observations.items():
            price_ordered = sorted(values, key=lambda value: value[0])
            earliest = price_ordered[0]
            latest = price_ordered[-1]
            if latest[1] <= earliest[1]:
                continue
            delta = latest[1] - earliest[1]
            percentage = (delta / earliest[1] * Decimal("100")) if earliest[1] else Decimal("0")
            changes.append((percentage, delta, item_name, earliest[1], latest[1], currency))
        if not changes:
            return 0, None, None, ("No item had a source-backed price increase.",)
        changes.sort(key=lambda value: (-value[0], -value[1], value[2]))
        preview = "; ".join(
            f"{item}: {currency} {earliest:.2f} to {currency} {latest:.2f} "
            f"(+{currency} {delta:.2f}, +{percentage:.2f}%)"
            for percentage, delta, item, earliest, latest, currency in changes[:10]
        )
        return (
            len(changes),
            f"Largest source-backed item price increases: {preview}.",
            None,
            (
                "This ranks observed earliest-to-latest item prices; it is not a causal "
                "inflation estimate and does not infer missing observations.",
            ),
        )
    if QueryTemplate.PERSONAL_FOOD_PRICE_INDEX in plan.selected_templates:
        basket_observations: dict[str, list[tuple[datetime, Decimal, str]]] = defaultdict(list)
        for row in rows:
            item_name = row.get("item_name")
            amount = row.get("amount")
            currency = row.get("currency")
            occurred_at = row.get("occurred_at")
            if not all(
                value is not None and str(value).strip()
                for value in (item_name, amount, currency, occurred_at)
            ):
                continue
            timestamp = datetime.fromisoformat(str(occurred_at))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("food-index rows require timezone-aware occurrence times")
            basket_observations[str(item_name)].append(
                (timestamp, Decimal(str(amount)), str(currency))
            )
        currencies = {
            currency
            for values in basket_observations.values()
            for _timestamp, _amount, currency in values
        }
        if len(currencies) != 1:
            return 0, None, None, ("Food-basket observations use multiple currencies.",)
        currency = currencies.pop()
        matched: list[tuple[str, Decimal, Decimal]] = []
        for item_name, values in basket_observations.items():
            basket_ordered = sorted(values, key=lambda value: value[0])
            if len(basket_ordered) < 2 or basket_ordered[0][1] <= 0:
                continue
            matched.append((item_name, basket_ordered[0][1], basket_ordered[-1][1]))
        if not matched:
            return (
                0,
                None,
                None,
                (
                    "At least two source-backed observations per item are required for a "
                    "matched food-basket index.",
                ),
            )
        index = sum(
            (latest / earliest * Decimal("100") for _item, earliest, latest in matched),
            Decimal("0"),
        ) / Decimal(len(matched))
        change = index - Decimal("100")
        direction = "increased" if change >= 0 else "decreased"
        return (
            len(matched),
            f"The matched personal food-basket price index is {index:.2f} "
            f"({direction} {abs(change):.2f}% from the observed baseline).",
            f"Equal-weighted index across {len(matched)} matched items: "
            f"{index:.2f} = average(latest price / earliest price x 100)",
            (
                f"The index compares {len(matched)} items with repeated observations in "
                f"{currency}; it is an observed basket signal, not an official CPI or "
                "causal inflation estimate.",
            ),
        )
    if QueryTemplate.SPENDING_ANOMALY_DETECTION in plan.selected_templates:
        priority = {"customer_total": 3, "invoice_total": 2, "payment_assertion": 1}
        anomaly_selected: dict[str, tuple[datetime, Decimal, str, str]] = {}
        anomaly_ambiguous: set[str] = set()
        for row in rows:
            order_id = row.get("order_id")
            amount = row.get("amount")
            currency = row.get("currency")
            occurred_at = row.get("occurred_at")
            component_type = str(row.get("component_type", ""))
            if not all(
                value is not None and str(value).strip()
                for value in (order_id, amount, currency, occurred_at)
            ):
                continue
            timestamp = datetime.fromisoformat(str(occurred_at))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("anomaly rows require timezone-aware occurrence times")
            anomaly_candidate = (timestamp, Decimal(str(amount)), str(currency), component_type)
            key = str(order_id)
            anomaly_current = anomaly_selected.get(key)
            if anomaly_current is None or priority.get(component_type, 0) > priority.get(
                anomaly_current[3], 0
            ):
                anomaly_selected[key] = anomaly_candidate
            elif (
                anomaly_current[3] == component_type
                and anomaly_current[1:] != anomaly_candidate[1:]
            ):
                anomaly_ambiguous.add(key)
        for order_id in anomaly_ambiguous:
            anomaly_selected.pop(order_id, None)
        if len(anomaly_selected) < 5:
            return (
                len(anomaly_selected),
                None,
                None,
                (
                    "At least five unambiguous source-backed order totals are required for "
                    "robust anomaly detection.",
                ),
            )
        anomaly_ordered = sorted(anomaly_selected.items(), key=lambda item: (item[1][0], item[0]))
        currencies = {value[2] for value in anomaly_selected.values()}
        if len(currencies) != 1:
            return 0, None, None, ("Spending observations use multiple currencies.",)
        currency = currencies.pop()
        anomaly_values = sorted(value[1] for value in anomaly_selected.values())
        midpoint = len(anomaly_values) // 2
        median = (
            anomaly_values[midpoint]
            if len(anomaly_values) % 2
            else (anomaly_values[midpoint - 1] + anomaly_values[midpoint]) / Decimal("2")
        )
        deviations = sorted(abs(value - median) for value in anomaly_values)
        mad_midpoint = len(deviations) // 2
        mad = (
            deviations[mad_midpoint]
            if len(deviations) % 2
            else (deviations[mad_midpoint - 1] + deviations[mad_midpoint]) / Decimal("2")
        )
        anomalies: list[tuple[Decimal, str, datetime, Decimal]] = []
        for order_id, (timestamp, amount, _currency, _component_type) in anomaly_selected.items():
            if mad:
                score = Decimal("0.6745") * (amount - median) / mad
                is_anomaly = abs(score) >= Decimal("3.5")
            else:
                score = Decimal("0")
                is_anomaly = median > 0 and abs(amount - median) >= median / Decimal("2")
            if is_anomaly:
                anomalies.append((abs(score), order_id, timestamp, amount))
        anomalies.sort(key=lambda value: (-value[0], value[1]))
        change_points: list[tuple[datetime, Decimal, Decimal]] = []
        minimum_segment = 3
        for split in range(minimum_segment, len(anomaly_ordered) - minimum_segment + 1):
            before = sorted(value[1] for _order_id, value in anomaly_ordered[:split])
            after = sorted(value[1] for _order_id, value in anomaly_ordered[split:])
            before_mid = len(before) // 2
            after_mid = len(after) // 2
            before_median = (
                before[before_mid]
                if len(before) % 2
                else (before[before_mid - 1] + before[before_mid]) / Decimal("2")
            )
            after_median = (
                after[after_mid]
                if len(after) % 2
                else (after[after_mid - 1] + after[after_mid]) / Decimal("2")
            )
            denominator = abs(before_median)
            relative_change = (
                abs(after_median - before_median) / denominator
                if denominator
                else Decimal("1")
                if after_median != before_median
                else Decimal("0")
            )
            if relative_change >= Decimal("0.50"):
                change_points.append((anomaly_ordered[split][1][0], before_median, after_median))
        change_preview = "; ".join(
            f"{timestamp.date().isoformat()} ({currency} {before:.2f} → {after:.2f})"
            for timestamp, before, after in change_points[:5]
        )
        if not anomalies and not change_points:
            return (
                len(anomaly_selected),
                f"No robust source-backed spending anomalies were detected across "
                f"{len(anomaly_selected)} orders.",
                f"Median order total = {currency} {median:.2f}; MAD = {currency} {mad:.2f}",
                (
                    "Anomalies use a robust modified-z threshold of 3.5 over selected "
                    "source-backed order totals.",
                ),
            )
        if not anomalies:
            return (
                len(anomaly_selected),
                f"Detected {len(change_points)} source-backed spending regime "
                f"{'shift' if len(change_points) == 1 else 'shifts'} at {change_preview}.",
                f"Change point{'s' if len(change_points) != 1 else ''}: {change_preview}; "
                "median segment change threshold = 50.00%",
                (
                    "Change points compare chronological median spending segments; this is "
                    "a descriptive signal, not a causal explanation or fraud judgment.",
                ),
            )
        preview = "; ".join(
            f"{order_id}: {currency} {amount:.2f} on {timestamp.date().isoformat()} "
            f"(modified z {score:.2f})"
            for score, order_id, timestamp, amount in anomalies[:10]
        )
        answer = (
            len(anomaly_selected),
            f"Detected {len(anomalies)} source-backed spending "
            f"{'anomaly' if len(anomalies) == 1 else 'anomalies'}: {preview}.",
            f"Median order total = {currency} {median:.2f}; MAD = {currency} {mad:.2f}; "
            "threshold = |modified z| >= 3.50",
            (
                "This is a robust statistical signal, not a claim of fraud, error, or cause; "
                "ambiguous totals are excluded.",
            ),
        )
        if change_points:
            return (
                answer[0],
                f"{answer[1]} Also detected {len(change_points)} spending regime "
                f"{'shift' if len(change_points) == 1 else 'shifts'} at {change_preview}.",
                f"{answer[2]}; change points: {change_preview}",
                answer[3],
            )
        return answer
    if QueryTemplate.SPENDING_CONCENTRATION in plan.selected_templates:
        priority = {"customer_total": 3, "invoice_total": 2, "payment_assertion": 1}
        concentration_selected: dict[str, tuple[str, Decimal, str, str]] = {}
        concentration_ambiguous: set[str] = set()
        for row in rows:
            order_id = row.get("order_id")
            merchant_name = row.get("merchant_name")
            amount = row.get("amount")
            currency = row.get("currency")
            component_type = str(row.get("component_type", ""))
            if not all(
                value is not None and str(value).strip()
                for value in (order_id, merchant_name, amount, currency)
            ):
                continue
            concentration_candidate = (
                str(merchant_name),
                Decimal(str(amount)),
                str(currency),
                component_type,
            )
            key = str(order_id)
            concentration_current = concentration_selected.get(key)
            if concentration_current is None or priority.get(component_type, 0) > priority.get(
                concentration_current[3], 0
            ):
                concentration_selected[key] = concentration_candidate
            elif (
                concentration_current[3] == component_type
                and concentration_current[1:] != concentration_candidate[1:]
            ):
                concentration_ambiguous.add(key)
        for order_id in concentration_ambiguous:
            concentration_selected.pop(order_id, None)
        if not concentration_selected:
            return 0, None, None, ("No unambiguous source-backed merchant spend was available.",)
        currencies = {value[2] for value in concentration_selected.values()}
        if len(currencies) != 1:
            return 0, None, None, ("Merchant spending observations use multiple currencies.",)
        currency = currencies.pop()
        by_merchant: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for merchant, amount, _currency, _component_type in concentration_selected.values():
            by_merchant[merchant] += amount
        total = sum(by_merchant.values(), Decimal("0"))
        if total <= 0:
            return 0, None, None, ("Merchant spending totals must be positive for concentration.",)
        shares = {
            merchant: amount / total * Decimal("100") for merchant, amount in by_merchant.items()
        }
        hhi = sum((share * share for share in shares.values()), Decimal("0"))
        top_merchant, top_share = max(shares.items(), key=lambda item: (-item[1], item[0]))
        top_preview = "; ".join(
            f"{merchant}: {share:.2f}%"
            for merchant, share in sorted(shares.items(), key=lambda item: (-item[1], item[0]))[:5]
        )
        return (
            len(concentration_selected),
            f"Food spending concentration is {hhi:.2f} HHI; {top_merchant} represents "
            f"{top_share:.2f}% of source-backed spend. Merchant shares: {top_preview}.",
            f"HHI = sum of squared merchant shares = {hhi:.2f}; total spend = "
            f"{currency} {total:.2f}",
            (
                "HHI is a descriptive concentration signal over reviewed order totals, "
                "not a credit-risk or causal dependence judgment; ambiguous orders are excluded.",
            ),
        )
    if QueryTemplate.DELIVERY_FEE_COUNTERFACTUAL in plan.selected_templates:
        merchant_names = {
            str(row["merchant_name"]) for row in rows if row.get("merchant_name") is not None
        }
        currencies = {str(row["currency"]) for row in rows if row.get("currency") is not None}
        if len(merchant_names) != 1:
            return 0, None, None, ("The merchant phrase matched multiple reviewed identities.",)
        if len(currencies) != 1:
            return 0, None, None, ("Delivery-fee evidence uses multiple currencies.",)
        if not rows:
            return 0, None, None, ("No source-backed delivery charges were available.",)
        currency = currencies.pop()
        by_order: dict[str, Decimal] = {}
        for row in rows:
            order_id = row.get("order_id")
            amount = row.get("amount")
            if order_id is not None and amount is not None:
                by_order[str(order_id)] = Decimal(str(amount))
        total = sum(by_order.values(), Decimal("0"))
        merchant = next(iter(merchant_names))
        fee_terms = " + ".join(f"{currency} {amount:.2f}" for amount in by_order.values())
        return (
            len(by_order),
            f"Waiving observed delivery fees at {merchant} would have saved "
            f"{currency} {total:.2f} across {len(by_order)} "
            f"{'order' if len(by_order) == 1 else 'orders'}.",
            f"{fee_terms} = {currency} {total:.2f} simulated saving",
            (
                "This is a bounded counterfactual over observed delivery charges; "
                "order history is unchanged.",
            ),
        )
    if QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY in plan.selected_templates:
        return _price_history_synthesis(rows)
    if QueryTemplate.MERCHANT_SPEND_TOTAL in plan.selected_templates:
        merchant_names = {
            str(row["merchant_name"]) for row in rows if row.get("merchant_name") is not None
        }
        if len(merchant_names) > 1:
            return (
                0,
                None,
                None,
                ("The merchant phrase matched multiple reviewed restaurant identities.",),
            )
        totals_by_order: dict[str, tuple[Decimal, str, str]] = {}
        ambiguous_orders: set[str] = set()
        priority = {"customer_total": 3, "invoice_total": 2, "payment_assertion": 1}
        for row in rows:
            order_id = row.get("order_id")
            amount = row.get("amount")
            currency = row.get("currency")
            component_type = str(row.get("component_type", ""))
            if order_id is None or amount is None or currency is None:
                continue
            spend_candidate = (Decimal(str(amount)), str(currency), component_type)
            spend_current = totals_by_order.get(str(order_id))
            candidate_priority = priority.get(component_type, 0)
            current_priority = (
                priority.get(spend_current[2], 0) if spend_current is not None else -1
            )
            if spend_current is None or candidate_priority > current_priority:
                totals_by_order[str(order_id)] = spend_candidate
            elif candidate_priority == current_priority and (
                spend_current[0] != spend_candidate[0] or spend_current[1] != spend_candidate[1]
            ):
                ambiguous_orders.add(str(order_id))
        for order_id in ambiguous_orders:
            totals_by_order.pop(order_id, None)
        if not totals_by_order:
            return (0, None, None, ("No source-backed customer total was available.",))
        currencies = {value[1] for value in totals_by_order.values()}
        if len(currencies) != 1:
            return (0, None, None, ("The merchant totals use multiple currencies.",))
        currency = currencies.pop()
        total = sum((value[0] for value in totals_by_order.values()), Decimal("0"))
        limitations = ["Customer totals are preferred; invoice totals are used only when needed."]
        if ambiguous_orders:
            limitations.append(
                f"{len(ambiguous_orders)} orders were excluded because their source totals "
                "conflict."
            )
        return (
            len(totals_by_order),
            f"Source-backed spend at this merchant is {currency} {total:.2f} "
            f"across {len(totals_by_order)} orders.",
            None,
            tuple(limitations),
        )
    if QueryTemplate.MERCHANT_ORDER_COUNT in plan.selected_templates:
        merchant_names = {
            str(row["merchant_name"]) for row in rows if row.get("merchant_name") is not None
        }
        if len(merchant_names) > 1:
            return (
                0,
                None,
                None,
                ("The merchant phrase matched multiple reviewed restaurant identities.",),
            )
        order_counts = {
            int(row["order_count"]) for row in rows if row.get("order_count") is not None
        }
        if len(order_counts) > 1:
            raise ValueError("merchant-order rows returned conflicting aggregate counts")
        count = order_counts.pop() if order_counts else 0
        noun = "order" if count == 1 else "orders"
        return (
            count,
            f"The graph links this merchant to {count} source-backed {noun}." if count else None,
            None,
            ("Merchant identity follows the current reviewed resolution state.",),
        )
    if QueryTemplate.DELIVERY_MENTION_COUNT in plan.selected_templates:
        order_ids = {str(row["order_id"]) for row in rows if row.get("order_id") is not None}
        person_ids = {
            str(row["person_public_id"]) for row in rows if row.get("person_public_id") is not None
        }
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
                (
                    f"Reviewed pseudonymous delivery participant {next(iter(person_ids))} "
                    "is linked by the graph."
                    if len(person_ids) == 1
                    else "Repeated names are mention-level evidence unless a reviewed person "
                    "identity resolution exists."
                ),
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


def _review_state(limitations: tuple[str, ...]) -> tuple[bool, str | None]:
    """Translate deterministic ambiguity signals into an explicit HITL state."""
    joined = " ".join(limitations).lower()
    if "matched multiple reviewed restaurant identities" in joined:
        return True, "identity_ambiguity"
    if "source totals conflict" in joined or "multiple currencies" in joined:
        return True, "financial_conflict"
    return False, None


def retrieve_grounded_context(
    request: RuntimeRequest,
    reader: GraphReader,
    *,
    plan: QueryPlan | None = None,
) -> GroundedContext:
    plan = plan or build_query_plan(request.question)
    if plan.disposition is not QueryDisposition.SUPPORTED:
        claim_id = _claim_id(request, plan)
        reason: str | None = plan.disposition.value
        return GroundedContext(
            status=RuntimeStatus.ABSTAINED,
            question=request.question,
            plan=plan,
            fact_count=0,
            limitations=(plan.disposition_reason or "The question needs a governed operation.",),
            citations=(),
            verification=EvidenceVerification(
                status=VerificationStatus.ABSTAINED,
                covered_claim_ids=(),
                missing_claim_ids=(claim_id,),
                citation_ids=(),
                abstention_reason=reason,
            ),
            abstention_reason=reason,
            review_required=plan.disposition is QueryDisposition.CLARIFICATION_REQUIRED,
            review_reason=(
                "clarification_required"
                if plan.disposition is QueryDisposition.CLARIFICATION_REQUIRED
                else None
            ),
        )
    try:
        queries = bind_query_plan(plan, request.slots)
    except MissingQuerySlotError as error:
        # A model proposal can identify a financial family without supplying
        # every bounded slot. Treat that as a governed clarification state,
        # never as an internal server failure or an unbounded fallback.
        claim_id = _claim_id(request, plan)
        return GroundedContext(
            status=RuntimeStatus.ABSTAINED,
            question=request.question,
            plan=plan,
            fact_count=0,
            limitations=("The question needs a more specific financial scope.",),
            citations=(),
            verification=EvidenceVerification(
                status=VerificationStatus.ABSTAINED,
                covered_claim_ids=(),
                missing_claim_ids=(claim_id,),
                citation_ids=(),
                abstention_reason=f"missing_query_slot:{error.slot}",
            ),
            abstention_reason=f"missing_query_slot:{error.slot}",
            review_required=True,
            review_reason="missing_query_slot",
        )
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
    review_required, review_reason = _review_state(limitations)
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
        review_required=review_required,
        review_reason=review_reason,
    )
