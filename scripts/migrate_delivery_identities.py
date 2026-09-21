#!/usr/bin/env python3
"""Materialize stable pseudonymous delivery identities in Neo4j."""

from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from lunarbit.delivery_identity import build_delivery_identities
from lunarbit.resolve import DeliveryPartnerMention


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
    parser.add_argument("--uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--apply", action="store_true", help="Write identities and edges.")
    return parser.parse_args()


def _relationship_id(kind: str, source: str, target: str) -> str:
    digest = sha256(f"{kind}|{source}|{target}".encode()).hexdigest()[:24]
    return f"relationship:{kind.casefold()}:{digest}"


def _mentions(path: Path) -> tuple[DeliveryPartnerMention, ...]:
    return tuple(
        DeliveryPartnerMention.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _connection(args: argparse.Namespace) -> tuple[str, str, tuple[str, str] | None]:
    load_dotenv(".env", override=False)
    uri = args.uri or os.environ.get("NEO4J_URI")
    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")
    username = args.username or os.environ.get("NEO4J_USERNAME")
    password = args.password or os.environ.get("NEO4J_PASSWORD")
    if not uri:
        raise ValueError("NEO4J_URI or --uri is required")
    if (username is None) != (password is None):
        raise ValueError("NEO4J_USERNAME and NEO4J_PASSWORD must be supplied together")
    return uri, database, None if username is None else (username, password)


def _plan(mentions: tuple[DeliveryPartnerMention, ...]) -> dict[str, int]:
    identities = build_delivery_identities(mentions)
    return {
        "mentions": len(mentions),
        "identities": len(identities),
        "resolved_order_links": sum(len(identity.order_ids) for identity in identities),
        "mention_resolution_links": sum(len(identity.mention_ids) for identity in identities),
    }


def _apply(tx: Any, mentions: tuple[DeliveryPartnerMention, ...]) -> dict[str, int]:
    identities = build_delivery_identities(mentions)
    for identity in identities:
        identity_node = f"person_identity:{identity.person_id}"
        tx.run(
            "MERGE (person:LunarbitNode:PersonIdentity {node_id: $node_id}) "
            "SET person.public_id = $public_id, person.public_label = $public_label, "
            "person.identity_status = 'stable_pseudonymous_projection', "
            "person.privacy_class = 'pseudonymous'",
            node_id=identity_node,
            public_id=identity.public_id,
            public_label=f"Delivery participant {identity.public_id}",
        ).consume()
        for mention_id in identity.mention_ids:
            mention_node = f"mention:{mention_id}"
            tx.run(
                "MATCH (mention:LunarbitNode {node_id: $mention_id}) "
                "MATCH (person:LunarbitNode:PersonIdentity {node_id: $person_id}) "
                "MERGE (mention)-[edge:RESOLVED_TO {relationship_id: $relationship_id}]->(person)",
                mention_id=mention_node,
                person_id=identity_node,
                relationship_id=_relationship_id("RESOLVED_TO", mention_node, identity_node),
            ).consume()
        for order_id in identity.order_ids:
            order_node = f"order:{order_id}"
            tx.run(
                "MATCH (order:LunarbitNode {node_id: $order_id}) "
                "MATCH (person:LunarbitNode:PersonIdentity {node_id: $person_id}) "
                "MERGE (order)-[edge:DELIVERED_BY {relationship_id: $relationship_id}]->(person)",
                order_id=order_node,
                person_id=identity_node,
                relationship_id=_relationship_id("DELIVERED_BY", order_node, identity_node),
            ).consume()
    row = tx.run(
        "MATCH (person:LunarbitNode:PersonIdentity) "
        "OPTIONAL MATCH (order:LunarbitNode:Order)-[:DELIVERED_BY]->(person) "
        "RETURN count(DISTINCT person) AS identities, count(order) AS order_links"
    ).single(strict=True)
    return {"identities": int(row["identities"]), "order_links": int(row["order_links"])}


def main() -> int:
    args = _args()
    mentions = _mentions(args.mentions)
    summary = _plan(mentions)
    if args.apply:
        uri, database, auth = _connection(args)
        driver = GraphDatabase.driver(uri, auth=auth)
        try:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                summary.update(session.execute_write(_apply, mentions))
        finally:
            driver.close()
    print(json.dumps({**summary, "applied": args.apply}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
