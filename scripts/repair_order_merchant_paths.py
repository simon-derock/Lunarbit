#!/usr/bin/env python3
"""Repair order-to-merchant paths using only source-backed merchant evidence.

The repair is deliberately conservative:

* Evidence is order-local. Chunks from a source that documents several orders, such as a
  provider order-history report, name many restaurants and never identify one order's merchant.
* A unique canonical identity reached through the order's resolved outlet is authoritative.
  Order-local text that names a different reviewed merchant is reported as a conflict for
  review; the planner never chooses between two deterministic signals.
* Orders without an outlet path resolve from exactly one reviewed merchant named in their own
  evidence, then from an existing direct link, then from the source receipt's merchant name.
  Anything else is quarantined instead of guessed.
* Every change is reversible from the printed plan: removed direct links carry the identity they
  pointed to, and ``ORDERED_FROM`` relationship IDs are deterministic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from neo4j import GraphDatabase

_SPACE = re.compile(r"[^\w]+", re.UNICODE)
_SOURCE_MERCHANT_PATTERNS = (
    re.compile(
        r"\b(?:ordering|ordered)\s+(?:dinner|lunch|food)?\s*from\s+(.+?)\s+we hope\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmeal from\s+(.+?)(?:\s+\.|\s+we hope\b)", re.IGNORECASE),
    re.compile(r"\brestaurant:\s*([^.;]+?)(?:\s+(?:cancelation|cancellation)\b|$)", re.IGNORECASE),
)


_QUARANTINED = "quarantined_missing_merchant_evidence"


def _normalize(value: object) -> str:
    return " ".join(_SPACE.sub(" ", str(value or "")).casefold().split())


def _source_merchant_name(order: Mapping[str, object]) -> str | None:
    evidence = " ".join(str(value or "") for value in order.get("evidence", ()))
    for pattern in _SOURCE_MERCHANT_PATTERNS:
        match = pattern.search(evidence)
        if match:
            candidate = " ".join(match.group(1).split()).strip(" .,:;-")
            if len(candidate) >= 3:
                display = candidate.title()
                return display.replace("Csk", "CSK").replace("Pl.A", "PL.A")
    return None


def _identity_id(name: str) -> str:
    return f"merchant_identity:{uuid5(NAMESPACE_URL, f'lunarbit:merchant:{_normalize(name)}')}"


def _relationship_id(source: str, target: str) -> str:
    digest = sha256(f"ORDERED_FROM|{source}|{target}".encode()).hexdigest()[:24]
    return f"relationship:ordered_from:{digest}"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--apply", action="store_true", help="Write the deterministic repair.")
    return parser.parse_args()


def _config(args: argparse.Namespace) -> tuple[str, str, tuple[str, str] | None]:
    uri = args.uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = args.username or os.environ.get("NEO4J_USERNAME")
    password = args.password or os.environ.get("NEO4J_PASSWORD")
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    return uri, database, None if username is None else (username, password)


def _merchant_catalog(session: Any) -> tuple[dict[str, object], ...]:
    rows = session.run(
        "MATCH (merchant:Merchant)-[:CANONICAL_OF]->(identity:MerchantIdentity) "
        "OPTIONAL MATCH (outlet:Outlet)-[:OUTLET_OF]->(merchant) "
        "RETURN merchant.node_id AS merchant_id, merchant.platform AS platform, "
        "merchant.display_name_private AS listing_name, "
        "identity.node_id AS identity_id, identity.canonical_name_private AS canonical_name, "
        "identity.aliases_private AS aliases, collect(outlet.node_id) AS outlets "
        "ORDER BY merchant.node_id"
    )
    return tuple(dict(row) for row in rows)


def _identity_names(session: Any) -> dict[str, str]:
    """Return every canonical identity, including ones created from source receipts."""

    rows = session.run(
        "MATCH (identity:MerchantIdentity) "
        "RETURN identity.node_id AS identity_id, "
        "identity.canonical_name_private AS canonical_name "
        "ORDER BY identity.node_id"
    )
    return {str(row["identity_id"]): str(row["canonical_name"] or "") for row in rows}


def _orders(session: Any) -> tuple[dict[str, object], ...]:
    rows = session.run(
        "MATCH (order:Order) "
        "OPTIONAL MATCH (order)-[:ORDERED_FROM]->(outlet:Outlet)-[:OUTLET_OF]->"
        "(merchant:Merchant)-[:CANONICAL_OF]->(identity:MerchantIdentity) "
        "WITH order, collect(DISTINCT {outlet_id: outlet.node_id, "
        "identity_id: identity.node_id}) AS paths "
        "OPTIONAL MATCH (order)-[:ORDERED_FROM]->(direct:MerchantIdentity) "
        "WITH order, paths, collect(DISTINCT direct.node_id) AS direct_identity_ids "
        "OPTIONAL MATCH (order)-[:DOCUMENTED_BY]->(source:LunarbitNode)-[:HAS_CHUNK]->"
        "(chunk:EvidenceChunk) "
        "WITH order, paths, direct_identity_ids, chunk, "
        "CASE WHEN source IS NULL THEN 0 "
        "ELSE COUNT { (:Order)-[:DOCUMENTED_BY]->(source) } END AS source_orders "
        "RETURN order.node_id AS order_id, order.platform AS platform, "
        "order.order_type AS order_type, "
        "order.identity_status AS identity_status, paths, direct_identity_ids, "
        "collect(DISTINCT {text: chunk.normalized_text_private, "
        "source_orders: source_orders}) AS evidence_items "
        "ORDER BY order.node_id"
    )
    return tuple(dict(row) for row in rows)


def _order_local_evidence(order: Mapping[str, object]) -> tuple[str, ...]:
    """Keep only evidence from sources that document this order alone."""

    items = order.get("evidence_items")
    if not isinstance(items, list | tuple):
        return ()
    return tuple(
        str(item["text"])
        for item in items
        if item and item.get("text") and item.get("source_orders") == 1
    )


def _candidate_identities(
    order: Mapping[str, object], catalog: tuple[dict[str, object], ...]
) -> tuple[str, ...]:
    evidence = _normalize(" ".join(str(value or "") for value in order.get("evidence", ())))
    if not evidence:
        return ()
    scores: dict[str, int] = {}
    for listing in catalog:
        names = [listing.get("listing_name"), listing.get("canonical_name")]
        aliases = str(listing.get("aliases") or "")
        names.extend(aliases.split(" | "))
        for name in names:
            normalized = _normalize(name)
            if len(normalized) < 4 or normalized not in evidence:
                continue
            # Prefer longer, more specific evidence matches over generic words.
            identity_id = str(listing["identity_id"])
            scores[identity_id] = max(scores.get(identity_id, 0), len(normalized))
    if not scores:
        return ()
    highest = max(scores.values())
    return tuple(sorted(identity for identity, score in scores.items() if score == highest))


def _exact_source_identities(
    source_name: str, catalog: tuple[dict[str, object], ...]
) -> tuple[str, ...]:
    normalized = _normalize(source_name)
    return tuple(
        sorted(
            {
                str(row["identity_id"])
                for row in catalog
                if normalized
                in {
                    _normalize(row.get("listing_name")),
                    _normalize(row.get("canonical_name")),
                    *(_normalize(value) for value in str(row.get("aliases") or "").split(" | ")),
                }
            }
        )
    )


def plan_repair(session: Any) -> dict[str, object]:
    catalog = _merchant_catalog(session)
    identity_names = _identity_names(session)
    orders = _orders(session)
    actions: list[dict[str, str]] = []
    unresolved: list[str] = []
    conflicting: list[str] = []
    for raw_order in orders:
        order = {**raw_order, "evidence": _order_local_evidence(raw_order)}
        order_id = str(order["order_id"])
        paths = tuple(path for path in order.get("paths", ()) if path and path.get("outlet_id"))
        outlet_identities = {str(path["identity_id"]) for path in paths if path.get("identity_id")}
        direct_identities = {
            str(identity) for identity in order.get("direct_identity_ids", ()) if identity
        }
        source_name = _source_merchant_name(order)
        candidates = _candidate_identities(order, catalog)
        if not candidates and source_name:
            candidates = _exact_source_identities(source_name, catalog)
        evidence_identity = candidates[0] if len(candidates) == 1 else None

        target_identity: str | None
        if len(outlet_identities) == 1:
            target_identity = next(iter(outlet_identities))
            if evidence_identity is not None and evidence_identity != target_identity:
                conflicting.append(order_id)
                continue
        elif outlet_identities:
            if evidence_identity not in outlet_identities:
                conflicting.append(order_id)
                continue
            target_identity = evidence_identity
        elif evidence_identity is not None:
            target_identity = evidence_identity
        elif len(direct_identities) == 1:
            target_identity = next(iter(direct_identities))
        elif source_name:
            target_identity = _identity_id(source_name)
        else:
            target_identity = None

        if target_identity is None:
            if order.get("order_type") != "instamart":
                unresolved.append(order_id)
                if order.get("identity_status") != _QUARANTINED:
                    actions.append({"order_id": order_id, "action": "quarantine"})
            continue
        if (
            source_name
            and target_identity == _identity_id(source_name)
            and identity_names.get(target_identity) != source_name
        ):
            actions.append(
                {
                    "identity_id": target_identity,
                    "identity_name": source_name,
                    "action": "ensure_identity",
                }
            )
            identity_names[target_identity] = source_name
        for path in paths:
            if path.get("identity_id") != target_identity:
                actions.append(
                    {"order_id": order_id, "outlet_id": str(path["outlet_id"]), "action": "remove"}
                )
        for identity_id in sorted(direct_identities - {target_identity}):
            actions.append(
                {"order_id": order_id, "identity_id": identity_id, "action": "remove_direct"}
            )
        if target_identity not in direct_identities:
            actions.append(
                {
                    "order_id": order_id,
                    "identity_id": target_identity,
                    "identity_name": source_name or "",
                    "action": "add_direct",
                }
            )
    return {
        "orders_scanned": len(orders),
        "actions": actions,
        "unresolved_order_ids": unresolved,
        "conflicting_order_ids": conflicting,
        "remove_count": sum(action["action"] == "remove" for action in actions),
        "remove_direct_count": sum(action["action"] == "remove_direct" for action in actions),
        "add_count": sum(action["action"] == "add_direct" for action in actions),
    }


def apply_repair(tx: Any, actions: list[dict[str, str]]) -> int:
    changed = 0
    for action in actions:
        if action["action"] == "quarantine":
            result = tx.run(
                "MATCH (order:Order {node_id: $order_id}) "
                "SET order.identity_status = $status RETURN count(*) AS changed",
                order_id=action["order_id"],
                status=_QUARANTINED,
            ).single()
        elif action["action"] == "ensure_identity":
            result = tx.run(
                "MERGE (identity:LunarbitNode:MerchantIdentity {node_id: $identity_id}) "
                "SET identity.canonical_name_private = $identity_name, "
                "identity.normalized_name_private = $normalized_name, "
                "identity.aliases_private = $identity_name, identity.platforms = '', "
                "identity.privacy_class = 'private' RETURN count(*) AS changed",
                identity_id=action["identity_id"],
                identity_name=action["identity_name"],
                normalized_name=_normalize(action["identity_name"]),
            ).single()
        elif action["action"] == "remove":
            result = tx.run(
                "MATCH (order:Order {node_id: $order_id})-[edge:ORDERED_FROM]->"
                "(outlet:Outlet {node_id: $outlet_id}) DELETE edge RETURN count(*) AS changed",
                order_id=action["order_id"],
                outlet_id=action["outlet_id"],
            ).single()
        elif action["action"] == "remove_direct":
            result = tx.run(
                "MATCH (order:Order {node_id: $order_id})-[edge:ORDERED_FROM]->"
                "(identity:MerchantIdentity {node_id: $identity_id}) "
                "DELETE edge RETURN count(*) AS changed",
                order_id=action["order_id"],
                identity_id=action["identity_id"],
            ).single()
        elif action["action"] == "add_direct":
            result = tx.run(
                "MATCH (order:Order {node_id: $order_id}), "
                "(identity:MerchantIdentity {node_id: $identity_id}) "
                "MERGE (order)-[edge:ORDERED_FROM]->(identity) "
                "ON CREATE SET edge.relationship_id = $relationship_id "
                "RETURN count(*) AS changed",
                order_id=action["order_id"],
                identity_id=action["identity_id"],
                relationship_id=_relationship_id(action["order_id"], action["identity_id"]),
            ).single()
        changed += int(result["changed"] if result else 0)
    return changed


def main() -> int:
    args = _args()
    uri, database, auth = _config(args)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            plan = plan_repair(session)
            if args.apply:
                changed = session.execute_write(apply_repair, list(plan["actions"]))
                plan["changed"] = changed
    finally:
        driver.close()
    print(json.dumps({"apply": args.apply, **plan}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
