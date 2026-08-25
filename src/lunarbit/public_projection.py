"""Privacy-safe aggregate topology projected from the canonical Neo4j graph.

The public graph is deliberately not a redacted copy of the canonical graph.  It
never selects a graph ``node_id`` or any node property; it exposes only schema
classes and aggregate relationship counts.  That makes the browser projection
useful for explaining the architecture without publishing commerce records.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Protocol, Self

from neo4j import READ_ACCESS, Driver, GraphDatabase

from lunarbit.public import PublicEdge, PublicMetric, PublicNode, PublicNodeLabel, PublicSnapshot

_RELATIONSHIP = re.compile(r"^[A-Z_]+$")

_NODE_TITLES: dict[PublicNodeLabel, tuple[str, str]] = {
    PublicNodeLabel.PLATFORM: ("Commerce platforms", "Aggregate platform topology"),
    PublicNodeLabel.ORDER: ("Reconstructed orders", "Aggregate order topology"),
    PublicNodeLabel.MERCHANT: ("Merchant entities", "Aggregate merchant and outlet topology"),
    PublicNodeLabel.ITEM: ("Item observations", "Aggregate product and comparable-item topology"),
    PublicNodeLabel.MONEY_COMPONENT: ("Money components", "Aggregate financial-component topology"),
    PublicNodeLabel.EVIDENCE: (
        "Evidence structures",
        "Aggregate document, chunk, and assertion topology",
    ),
    PublicNodeLabel.RECONCILIATION: (
        "Reconciliation runs",
        "Aggregate deterministic reconciliation topology",
    ),
}

_PUBLIC_NODE_ORDER = tuple(PublicNodeLabel)


class PublicProjectionUnavailable(RuntimeError):
    """The canonical graph has no safe, navigable public aggregate projection."""


@dataclass(frozen=True, slots=True)
class AggregateRelationship:
    source_label: PublicNodeLabel
    target_label: PublicNodeLabel
    relationship: str
    count: int

    def __post_init__(self) -> None:
        if not _RELATIONSHIP.fullmatch(self.relationship):
            raise ValueError("aggregate relationship must be an uppercase relationship type")
        if self.count < 1:
            raise ValueError("aggregate relationship count must be positive")


class AggregateReader(Protocol):
    """Read only counts; implementations must never return canonical identifiers or properties."""

    def graph_totals(self) -> tuple[int, int]: ...

    def node_counts(self) -> Mapping[PublicNodeLabel, int]: ...

    def relationship_counts(self, limit: int) -> tuple[AggregateRelationship, ...]: ...


class NavigationReader(AggregateReader, Protocol):
    """Read a bounded, allowlisted public navigation slice."""

    def navigation_nodes(self, *, per_class: int) -> tuple[Mapping[str, object], ...]: ...

    def navigation_relationships(
        self,
        *,
        canonical_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[Mapping[str, object], ...]: ...


def _class_case(variable: str) -> str:
    """Return a fixed Cypher CASE mapping from canonical labels to safe public classes."""
    return (
        f"CASE "
        f"WHEN {variable}:Platform THEN 'Platform' "
        f"WHEN {variable}:Order THEN 'Order' "
        f"WHEN {variable}:Merchant OR {variable}:Outlet THEN 'Merchant' "
        f"WHEN {variable}:ItemObservation OR {variable}:MerchantItem "
        f"OR {variable}:CanonicalItem OR {variable}:ComparableItemGroup THEN 'Item' "
        f"WHEN {variable}:MoneyComponent OR {variable}:FinancialEvent THEN 'MoneyComponent' "
        f"WHEN {variable}:ReconciliationRun THEN 'Reconciliation' "
        f"WHEN {variable}:Document OR {variable}:SourceMessage OR {variable}:EvidenceChunk "
        f"OR {variable}:AgenticRegion OR {variable}:Assertion THEN 'Evidence' "
        f"ELSE NULL END"
    )


_NODE_COUNTS_CYPHER = (
    "MATCH (node:LunarbitNode) "
    f"WITH {_class_case('node')} AS public_label "
    "WHERE public_label IS NOT NULL "
    "RETURN public_label, count(*) AS count ORDER BY public_label"
)

_GRAPH_TOTALS_CYPHER = (
    "CALL { MATCH (node:LunarbitNode) RETURN count(node) AS graph_node_count } "
    "CALL { MATCH (source:LunarbitNode)-[relationship]->(target:LunarbitNode) "
    "RETURN count(relationship) AS graph_relationship_count } "
    "RETURN graph_node_count, graph_relationship_count"
)

_RELATIONSHIP_COUNTS_CYPHER = (
    "MATCH (source:LunarbitNode)-[relationship]->(target:LunarbitNode) "
    f"WITH {_class_case('source')} AS source_label, "
    f"{_class_case('target')} AS target_label, type(relationship) AS relationship "
    "WHERE source_label IS NOT NULL AND target_label IS NOT NULL "
    "RETURN source_label, target_label, relationship, count(*) AS count "
    "ORDER BY count DESC, source_label, target_label, relationship LIMIT $limit"
)

_NAVIGATION_LABELS = (
    "Platform",
    "Order",
    "Merchant",
    "Outlet",
    "ItemObservation",
    "MerchantItem",
    "MoneyComponent",
    "FinancialEvent",
    "ReconciliationRun",
    "PersonMention",
    "EvidenceChunk",
    "AgenticRegion",
    "EntityMention",
    "ResolutionDecision",
    "Document",
    "SourceMessage",
    "LegalEntity",
)

_NAVIGATION_NODE_CYPHER = (
    "MATCH (node:LunarbitNode) "
    "WHERE $label IN labels(node) "
    "RETURN node.node_id AS canonical_id, labels(node) AS labels, "
    "node.platform AS platform, node.order_type AS order_type, "
    "node.display_name_private AS display_name_private, "
    "node.raw_name_private AS raw_name_private, "
    "node.observed_amount AS observed_amount, node.amount AS amount, "
    "node.currency AS currency, node.component_type AS component_type, "
    "node.status AS status, node.scope AS scope "
    "ORDER BY COUNT { (node)--() } DESC, node.node_id LIMIT $limit"
)

_NAVIGATION_RELATIONSHIP_CYPHER = (
    "MATCH (source:LunarbitNode)-[relationship]->(target:LunarbitNode) "
    "WHERE source.node_id IN $canonical_ids AND target.node_id IN $canonical_ids "
    "RETURN source.node_id AS source_id, target.node_id AS target_id, "
    "type(relationship) AS relationship ORDER BY source.node_id, target.node_id "
    "LIMIT $limit"
)


class Neo4jAggregateReader:
    """Neo4j implementation whose queries select only labels, types, and counts."""

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

    def graph_totals(self) -> tuple[int, int]:
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            row = session.run(_GRAPH_TOTALS_CYPHER).single(strict=True)
        return (int(row["graph_node_count"]), int(row["graph_relationship_count"]))

    def node_counts(self) -> Mapping[PublicNodeLabel, int]:
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            rows = tuple(session.run(_NODE_COUNTS_CYPHER))
        return {
            PublicNodeLabel(str(row["public_label"])): int(row["count"])
            for row in rows
            if int(row["count"]) > 0
        }

    def relationship_counts(self, limit: int) -> tuple[AggregateRelationship, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("relationship projection limit must be between 1 and 100")
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            rows = tuple(session.run(_RELATIONSHIP_COUNTS_CYPHER, {"limit": limit}))
        return tuple(
            AggregateRelationship(
                source_label=PublicNodeLabel(str(row["source_label"])),
                target_label=PublicNodeLabel(str(row["target_label"])),
                relationship=str(row["relationship"]),
                count=int(row["count"]),
            )
            for row in rows
            if int(row["count"]) > 0
        )

    def navigation_nodes(self, *, per_class: int) -> tuple[Mapping[str, object], ...]:
        if not 1 <= per_class <= 100:
            raise ValueError("navigation per-class limit must be between 1 and 100")
        rows: list[Mapping[str, object]] = []
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            for label in _NAVIGATION_LABELS:
                rows.extend(
                    session.run(
                        _NAVIGATION_NODE_CYPHER,
                        {"label": label, "limit": per_class},
                    )
                )
        return tuple(rows)

    def navigation_relationships(
        self,
        *,
        canonical_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[Mapping[str, object], ...]:
        if not canonical_ids:
            return ()
        if not 1 <= limit <= 2_000:
            raise ValueError("navigation relationship limit must be between 1 and 2000")
        with self._driver.session(
            database=self._database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return tuple(
                session.run(
                    _NAVIGATION_RELATIONSHIP_CYPHER,
                    {"canonical_ids": canonical_ids, "limit": limit},
                )
            )

    def close(self) -> None:
        self._driver.close()


def _public_class_id(label: PublicNodeLabel) -> str:
    return label.value.replace("Component", "-component").replace(" ", "-").casefold()


def build_aggregate_snapshot(
    *,
    node_counts: Mapping[PublicNodeLabel, int],
    relationships: tuple[AggregateRelationship, ...],
    graph_node_count: int,
    graph_relationship_count: int,
) -> PublicSnapshot:
    """Build a closed public graph from aggregate counts alone."""
    if graph_node_count < 1 or graph_relationship_count < 1:
        raise PublicProjectionUnavailable("canonical graph has no nodes or relationships")
    safe_counts = {label: int(count) for label, count in node_counts.items() if int(count) > 0}
    if not safe_counts:
        raise PublicProjectionUnavailable("canonical graph has no public aggregate node classes")
    visible_relationships = tuple(
        relationship
        for relationship in relationships
        if relationship.source_label in safe_counts and relationship.target_label in safe_counts
    )
    if not visible_relationships:
        raise PublicProjectionUnavailable("canonical graph has no public aggregate relationships")

    nodes = tuple(
        PublicNode(
            id=f"pub:class:{_public_class_id(label)}",
            label=label,
            title=_NODE_TITLES[label][0],
            subtitle=_NODE_TITLES[label][1],
            properties={"count": safe_counts[label], "projection": "aggregate"},
        )
        for label in _PUBLIC_NODE_ORDER
        if label in safe_counts
    )
    edges = tuple(
        PublicEdge(
            id=f"pub:edge:aggregate-{index}",
            source=f"pub:class:{_public_class_id(relationship.source_label)}",
            target=f"pub:class:{_public_class_id(relationship.target_label)}",
            relationship=relationship.relationship,
            properties={"count": relationship.count},
        )
        for index, relationship in enumerate(visible_relationships, start=1)
    )
    return PublicSnapshot(
        mode="neo4j_aggregate_projection",
        disclosure=(
            "Live aggregate topology from the canonical graph. No canonical identifiers, "
            "node properties, source text, or private commerce records are published."
        ),
        metrics=(
            PublicMetric(
                label="Graph nodes",
                value=str(graph_node_count),
                detail="canonical aggregate",
            ),
            PublicMetric(
                label="Graph relationships",
                value=str(graph_relationship_count),
                detail="canonical aggregate",
            ),
            PublicMetric(
                label="Orders reconstructed",
                value=str(safe_counts.get(PublicNodeLabel.ORDER, 0)),
                detail="aggregate class count",
            ),
            PublicMetric(
                label="Evidence structures",
                value=str(safe_counts.get(PublicNodeLabel.EVIDENCE, 0)),
                detail="aggregate class count",
            ),
        ),
        sample_questions=(
            "How does an order connect to its financial components and evidence?",
            "Which graph relationships support deterministic reconciliation?",
            "What evidence topology underpins a financial component claim?",
            "How does the public graph separate evidence from money facts?",
            "Which graph classes participate in product comparability?",
            "How does a query remain bounded before touching the private graph?",
            "Which paths require evidence verification before an answer is emitted?",
            "How are entity-resolution classes isolated from public topology?",
            "Where do temporal financial events attach to the commerce graph?",
            "Which schema classes make a price-history claim auditable?",
        ),
        nodes=nodes,
        edges=edges,
    )


class AggregateSnapshotSource:
    """Serve a short-lived, bounded public aggregate snapshot.

    The cache contains only the already-safe aggregate projection. A lock avoids
    concurrent browser requests multiplying the three count queries at refresh
    boundaries.
    """

    def __init__(
        self,
        reader: AggregateReader,
        *,
        relationship_limit: int = 40,
        refresh_seconds: float = 15.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not 1 <= relationship_limit <= 100:
            raise ValueError("relationship projection limit must be between 1 and 100")
        if not 0 <= refresh_seconds <= 3_600:
            raise ValueError("public projection refresh must be between 0 and 3600 seconds")
        self._reader = reader
        self._relationship_limit = relationship_limit
        self._refresh_seconds = refresh_seconds
        self._clock = clock
        self._snapshot: PublicSnapshot | None = None
        self._expires_at = 0.0
        self._lock = Lock()

    def snapshot(self) -> PublicSnapshot:
        now = self._clock()
        cached = self._snapshot
        if cached is not None and now < self._expires_at:
            return cached
        with self._lock:
            now = self._clock()
            cached = self._snapshot
            if cached is not None and now < self._expires_at:
                return cached
            snapshot = self._build_snapshot()
            self._snapshot = snapshot
            self._expires_at = now + self._refresh_seconds
            return snapshot

    def _build_snapshot(self) -> PublicSnapshot:
        graph_node_count, graph_relationship_count = self._reader.graph_totals()
        return build_aggregate_snapshot(
            node_counts=self._reader.node_counts(),
            relationships=self._reader.relationship_counts(self._relationship_limit),
            graph_node_count=graph_node_count,
            graph_relationship_count=graph_relationship_count,
        )


def _navigation_label(labels: object) -> PublicNodeLabel:
    values = {str(value) for value in labels} if isinstance(labels, (list, tuple)) else set()
    if "Platform" in values:
        return PublicNodeLabel.PLATFORM
    if "Order" in values:
        return PublicNodeLabel.ORDER
    if values & {"Merchant", "Outlet"}:
        return PublicNodeLabel.MERCHANT
    if values & {"ItemObservation", "MerchantItem"}:
        return PublicNodeLabel.ITEM
    if values & {"MoneyComponent", "FinancialEvent"}:
        return PublicNodeLabel.MONEY_COMPONENT
    if "ReconciliationRun" in values:
        return PublicNodeLabel.RECONCILIATION
    return PublicNodeLabel.EVIDENCE


def _public_alias(canonical_id: str) -> str:
    digest = sha256(f"lunarbit-public-v1:{canonical_id}".encode()).hexdigest()[:12]
    # Public payload validation rejects long digit runs; an alpha-only alias
    # remains opaque while staying stable across projection refreshes.
    alpha_digest = digest.translate(str.maketrans("0123456789", "abcdefghij"))
    return f"pub:node:{alpha_digest}"


def _navigation_node(row: Mapping[str, object]) -> PublicNode:
    canonical_id = row.get("canonical_id")
    if not isinstance(canonical_id, str) or not canonical_id:
        raise PublicProjectionUnavailable("navigation row omitted its canonical identity")
    label = _navigation_label(row.get("labels"))
    raw_labels = row.get("labels")
    label_values = (
        tuple(str(value) for value in raw_labels)
        if isinstance(raw_labels, (list, tuple))
        else ()
    )
    alias = _public_alias(canonical_id)
    platform = str(row.get("platform") or "").title()
    if label is PublicNodeLabel.MERCHANT:
        title = str(row.get("display_name_private") or "Merchant alias")
        subtitle = f"{platform} merchant" if platform else "Merchant entity"
    elif label is PublicNodeLabel.ITEM:
        title = str(row.get("raw_name_private") or row.get("display_name_private") or "Food item")
        subtitle = f"{platform} item" if platform else "Food item observation"
    elif label is PublicNodeLabel.PLATFORM:
        title = str(row.get("display_name_private") or platform or "Food-commerce platform")
        subtitle = "Food-commerce platform"
    elif label is PublicNodeLabel.ORDER:
        title = f"Order {alias[-6:].upper()}"
        subtitle = f"{platform} order" if platform else "Commerce order"
    elif label is PublicNodeLabel.MONEY_COMPONENT:
        component = str(row.get("component_type") or "financial component").replace("_", " ")
        amount = row.get("amount") or row.get("observed_amount")
        currency = str(row.get("currency") or "")
        title = f"{component.title()} {currency} {amount}".strip()
        subtitle = "Source-backed financial event"
    elif label is PublicNodeLabel.RECONCILIATION:
        title = "Deterministic reconciliation"
        subtitle = str(row.get("status") or "reviewed run")
    elif "PersonMention" in label_values:
        title = f"Delivery participant {alias[-6:].upper()}"
        subtitle = "Anonymized delivery mention"
    else:
        evidence_kind = next(
            (
                kind
                for kind in (
                    "AgenticRegion",
                    "EntityMention",
                    "ResolutionDecision",
                    "Document",
                    "SourceMessage",
                    "EvidenceChunk",
                )
                if kind in label_values
            ),
            "Evidence",
        )
        title = evidence_kind.replace("SourceMessage", "Source message")
        subtitle = "Redacted source lineage"
    properties: dict[str, str | int | float | bool | None] = {"projection": "navigation"}
    if platform:
        properties["platform"] = platform
    if label is PublicNodeLabel.MONEY_COMPONENT:
        properties.update(
            {
                "amount": str(row.get("amount") or row.get("observed_amount") or ""),
                "currency": str(row.get("currency") or ""),
                "component_type": str(row.get("component_type") or ""),
            }
        )
    return PublicNode(
        id=alias,
        label=label,
        title=title[:80],
        subtitle=subtitle[:120],
        properties=properties,
    )


class NavigationSnapshotSource:
    """Serve a dense, bounded, anonymized graph slice for visual navigation."""

    def __init__(
        self,
        reader: NavigationReader,
        *,
        per_class: int = 24,
        relationship_limit: int = 600,
    ) -> None:
        if not 1 <= per_class <= 100:
            raise ValueError("navigation per-class limit must be between 1 and 100")
        if not 1 <= relationship_limit <= 2_000:
            raise ValueError("navigation relationship limit must be between 1 and 2000")
        self._reader = reader
        self._per_class = per_class
        self._relationship_limit = relationship_limit

    def snapshot(self) -> PublicSnapshot:
        rows = self._reader.navigation_nodes(per_class=self._per_class)
        nodes = tuple(_navigation_node(row) for row in rows)
        if not nodes:
            raise PublicProjectionUnavailable("canonical graph has no navigable public nodes")
        aliases = {
            str(row["canonical_id"]): _public_alias(str(row["canonical_id"]))
            for row in rows
            if isinstance(row.get("canonical_id"), str)
        }
        relationships = self._reader.navigation_relationships(
            canonical_ids=tuple(aliases),
            limit=self._relationship_limit,
        )
        edges = tuple(
            PublicEdge(
                id=(
                    "pub:edge:"
                    + sha256(f"{source}:{target}:{relationship}".encode())
                    .hexdigest()[:16]
                    .translate(str.maketrans("0123456789", "abcdefghij"))
                ),
                source=aliases[source],
                target=aliases[target],
                relationship=relationship,
            )
            for row in relationships
            if (source := row.get("source_id")) in aliases
            and (target := row.get("target_id")) in aliases
            and isinstance(relationship := row.get("relationship"), str)
            and _RELATIONSHIP.fullmatch(relationship)
        )
        if not edges:
            raise PublicProjectionUnavailable("navigable public nodes have no relationships")
        graph_nodes, graph_relationships = self._reader.graph_totals()
        return PublicSnapshot(
            mode="neo4j_navigation_projection",
            disclosure=(
                "Bounded live food-commerce navigation projection. Names and amounts are drawn "
                "from reviewed evidence; personal identifiers and source text are withheld."
            ),
            metrics=(
                PublicMetric(
                    label="Visible nodes",
                    value=str(len(nodes)),
                    detail="bounded navigation",
                ),
                PublicMetric(
                    label="Visible relationships",
                    value=str(len(edges)),
                    detail="bounded navigation",
                ),
                PublicMetric(
                    label="Graph nodes",
                    value=str(graph_nodes),
                    detail="canonical aggregate",
                ),
                PublicMetric(
                    label="Graph relationships",
                    value=str(graph_relationships),
                    detail="canonical aggregate",
                ),
            ),
            sample_questions=(
                "Which merchant and item observations connect to this order?",
                "How do fees, discounts, and item prices connect through evidence?",
                "Which delivery participant aliases recur across source-backed orders?",
                "What temporal path connects an item price to its reconciliation?",
                "Which evidence structures support this financial component?",
                "Where do merchant, order, item, and money layers intersect?",
                "Which relationships survive deterministic validation?",
                "How does a promotion alter the effective order economics?",
                "Which orders share a reviewed merchant identity?",
                "What graph path proves this food-commerce finding?",
            ),
            nodes=nodes,
            edges=edges,
        )
