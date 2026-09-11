#!/usr/bin/env python3
"""Run read-only integrity checks over the canonical Lunarbit Neo4j graph."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from neo4j import GraphDatabase

AUDITS: dict[str, str] = {
    "food_orders_missing_outlet": (
        "MATCH (order:Order) "
        "WHERE order.order_type <> 'instamart' "
        "AND NOT (order)-[:ORDERED_FROM]->(:Outlet) "
        "RETURN count(order) AS count"
    ),
    "orders_without_platform": (
        "MATCH (order:Order) WHERE NOT (order)-[:PLACED_ON]->(:Platform) "
        "RETURN count(order) AS count"
    ),
    "orders_without_resolution": (
        "MATCH (order:Order) WHERE NOT (order)<-[:RESOLVES_TO]-(:ResolutionDecision) "
        "RETURN count(order) AS count"
    ),
    "item_observations_without_evidence": (
        "MATCH (observation:ItemObservation) WHERE NOT (observation)-[:EVIDENCED_BY]->"
        "(:EvidenceChunk) RETURN count(observation) AS count"
    ),
    "money_components_without_evidence": (
        "MATCH (component:MoneyComponent) WHERE NOT (component)-[:EVIDENCED_BY]->"
        "(:EvidenceChunk) RETURN count(component) AS count"
    ),
    "orders_with_multiple_outlets": (
        "MATCH (order:Order)-[:ORDERED_FROM]->(:Outlet) "
        "WITH order, count(*) AS outlets WHERE outlets > 1 "
        "RETURN count(order) AS count"
    ),
    "orders_with_duplicate_canonical_outlet_paths": (
        "MATCH (order:Order)-[:ORDERED_FROM]->(outlet:Outlet)-[:OUTLET_OF]->"
        "(merchant:Merchant)-[:CANONICAL_OF]->(identity:MerchantIdentity) "
        "WITH order, identity, count(outlet) AS paths WHERE paths > 1 "
        "RETURN count(*) AS count"
    ),
    "orders_with_multiple_canonical_merchants": (
        "MATCH (order:Order)-[:ORDERED_FROM]->(outlet:Outlet)-[:OUTLET_OF]->"
        "(merchant:Merchant)-[:CANONICAL_OF]->(identity:MerchantIdentity) "
        "WITH order, count(DISTINCT identity) AS merchants WHERE merchants > 1 "
        "RETURN count(order) AS count"
    ),
    "numeric_only_item_names": (
        "MATCH (item:MerchantItem) "
        "WHERE item.display_name_private =~ '[0-9]+([.,][0-9]+)?' "
        "RETURN count(item) AS count"
    ),
    "merchant_listings_without_one_identity": (
        "MATCH (merchant:Merchant) "
        "OPTIONAL MATCH (merchant)-[:CANONICAL_OF]->(identity:MerchantIdentity) "
        "WITH merchant, count(identity) AS identities WHERE identities <> 1 "
        "RETURN count(merchant) AS count"
    ),
    "delivery_mentions_without_normalized_name": (
        "MATCH (mention:PersonMention) "
        "WHERE mention.normalized_value_private IS NULL "
        "OR trim(mention.normalized_value_private) = '' "
        "RETURN count(mention) AS count"
    ),
    "pseudonymous_delivery_identities": (
        "MATCH (identity:PersonIdentity) RETURN count(identity) AS count"
    ),
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    return parser.parse_args()


def _config(args: argparse.Namespace) -> tuple[str, str, tuple[str, str] | None]:
    uri = args.uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = args.username or os.environ.get("NEO4J_USERNAME")
    password = args.password or os.environ.get("NEO4J_PASSWORD")
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    return uri, database, None if username is None else (username, password)


def run_audits(session: Any) -> dict[str, int]:
    """Execute only the allowlisted read-only audit statements."""

    return {
        name: int(session.run(query).single(strict=True)["count"]) for name, query in AUDITS.items()
    }


def main() -> int:
    args = _args()
    uri, database, auth = _config(args)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            result = run_audits(session)
    finally:
        driver.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
