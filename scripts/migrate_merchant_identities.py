#!/usr/bin/env python3
"""Add canonical merchant identities without deleting provider listings."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from lunarbit.identity import _identity_uuid


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aliases", type=Path, default=Path("config/merchant_aliases.json"))
    parser.add_argument("--uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--apply", action="store_true", help="Write identities and edges.")
    return parser.parse_args()


def _aliases(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()
    ):
        raise ValueError("merchant aliases must be a JSON object of string-to-string values")
    return {" ".join(key.split()).casefold(): value.strip() for key, value in payload.items()}


def _connection(args: argparse.Namespace) -> tuple[str, str, tuple[str, str] | None]:
    uri = args.uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = args.username or os.environ.get("NEO4J_USERNAME")
    password = args.password or os.environ.get("NEO4J_PASSWORD")
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    return uri, database, None if username is None else (username, password)


def _plan(tx: Any, aliases: dict[str, str]) -> dict[str, Any]:
    rows = list(
        tx.run(
            "MATCH (merchant:Merchant) "
            "RETURN merchant.node_id AS node_id, merchant.display_name_private AS name, "
            "merchant.normalized_name_private AS normalized, merchant.platform AS platform "
            "ORDER BY merchant.node_id"
        )
    )
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_key = " ".join(str(row["normalized"]).split()).casefold()
        canonical = aliases.get(source_key, str(row["name"]))
        canonical_name = " ".join(canonical.split())
        group = groups.setdefault(
            canonical_name.casefold(),
            {"canonical_name": canonical_name, "listings": []},
        )
        group["listings"].append(dict(row))
    return {
        "merchant_listings": len(rows),
        "canonical_identities": len(groups),
        "provider_edges": sum(len(group["listings"]) for group in groups.values()),
        "groups": [
            {
                "canonical_name": str(group["canonical_name"]),
                "listings": [
                    {
                        "node_id": listing["node_id"],
                        "name": listing["name"],
                        "platform": listing["platform"],
                    }
                    for listing in group["listings"]
                ],
            }
            for group in groups.values()
        ],
    }


def _apply(tx: Any, aliases: dict[str, str]) -> dict[str, int]:
    plan = _plan(tx, aliases)
    legacy_rows = list(
        tx.run(
            "MATCH (legacy:MerchantIdentity) "
            "WHERE NOT legacy:LunarbitNode "
            "MATCH (keeper:LunarbitNode:MerchantIdentity {node_id: legacy.node_id}) "
            "WITH legacy, keeper "
            "MATCH (listing:Merchant)-[:CANONICAL_OF]->(legacy) "
            "MERGE (listing)-[:CANONICAL_OF]->(keeper) "
            "WITH DISTINCT legacy "
            "DETACH DELETE legacy "
            "RETURN count(*) AS removed"
        )
    )
    for group in plan["groups"]:
        canonical_name = str(group["canonical_name"])
        key = " ".join(canonical_name.split()).casefold()
        identity_id = f"merchant_identity:{_identity_uuid(key)}"
        platforms = sorted({str(listing["platform"]) for listing in group["listings"]})
        alias_names = sorted({str(listing["name"]) for listing in group["listings"]})
        tx.run(
            "MERGE (identity:LunarbitNode:MerchantIdentity {node_id: $node_id}) "
            "SET identity.canonical_name_private = $canonical_name, "
            "identity.normalized_name_private = $normalized_name, "
            "identity.aliases_private = $aliases, identity.platforms = $platforms, "
            "identity.privacy_class = 'private' "
            "WITH identity "
            "UNWIND $listing_ids AS listing_id "
            "MATCH (listing:Merchant {node_id: listing_id}) "
            "OPTIONAL MATCH (listing)-[stale:CANONICAL_OF]->(other:MerchantIdentity) "
            "WHERE other.node_id <> identity.node_id "
            "DELETE stale "
            "MERGE (listing)-[:CANONICAL_OF]->(identity)",
            node_id=identity_id,
            canonical_name=canonical_name,
            normalized_name=key,
            aliases=" | ".join(alias_names),
            platforms=",".join(platforms),
            listing_ids=[str(listing["node_id"]) for listing in group["listings"]],
        ).consume()
    cleanup = list(
        tx.run(
            "MATCH (identity:MerchantIdentity) "
            "WHERE NOT (()-[:CANONICAL_OF]->(identity)) "
            "WITH collect(identity) AS stale "
            "FOREACH (identity IN stale | DETACH DELETE identity) "
            "RETURN size(stale) AS removed"
        )
    )
    return {
        "merchant_listings": int(plan["merchant_listings"]),
        "canonical_identities": int(plan["canonical_identities"]),
        "provider_edges": int(plan["provider_edges"]),
        "legacy_identities_removed": int(legacy_rows[0]["removed"]) if legacy_rows else 0,
        "stale_identities_removed": int(cleanup[0]["removed"]) if cleanup else 0,
    }


def main() -> int:
    args = _args()
    aliases = _aliases(args.aliases)
    uri, database, auth = _connection(args)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            if args.apply:
                result = session.execute_write(_apply, aliases)
            else:
                result = session.execute_read(_plan, aliases)
    finally:
        driver.close()
    print(json.dumps({"apply": args.apply, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
