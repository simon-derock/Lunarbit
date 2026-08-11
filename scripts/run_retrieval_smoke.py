#!/usr/bin/env python3
"""Exercise governed retrieval templates against a private local Neo4j graph."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from typing import Any

from neo4j import GraphDatabase, Session

from lunarbit.retrieval import (
    EvidenceCitation,
    EvidencePack,
    QueryTemplate,
    VerificationStatus,
    governed_query,
    verify_evidence_pack,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    return parser.parse_args()


def _run(
    session: Session, template: QueryTemplate, parameters: dict[str, str | int]
) -> list[dict[str, Any]]:
    query = governed_query(template, parameters)
    return [record.data() for record in session.run(query.cypher, query.parameters)]


def main() -> int:
    args = _args()
    driver = GraphDatabase.driver(args.uri, auth=None)
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            merchant_seed = session.run(
                "MATCH (merchant:Merchant)<-[:OUTLET_OF]-(:Outlet)"
                "<-[:ORDERED_FROM]-(order:Order) "
                "RETURN merchant.normalized_name_private AS name, count(DISTINCT order) AS orders "
                "ORDER BY orders DESC LIMIT 1"
            ).single(strict=True)
            merchant_count = _run(
                session,
                QueryTemplate.MERCHANT_ORDER_COUNT,
                {"normalized_name": str(merchant_seed["name"]), "limit": 20},
            )
            item_seed = session.run(
                "MATCH (merchant:Merchant)<-[:OUTLET_OF]-(:Outlet)"
                "<-[:ORDERED_FROM]-(:Order)-[:HAS_ITEM_OBSERVATION]->"
                "(:ItemObservation)-[:LISTING_OF]->(item:MerchantItem) "
                "WITH merchant, item, count(*) AS observations WHERE observations >= 2 "
                "RETURN merchant.normalized_name_private AS merchant_name, "
                "item.normalized_name_private AS item_name ORDER BY observations DESC LIMIT 1"
            ).single()
            price_history = (
                []
                if item_seed is None
                else _run(
                    session,
                    QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY,
                    {
                        "merchant_name": str(item_seed["merchant_name"]),
                        "item_name": str(item_seed["item_name"]),
                        "limit": 30,
                    },
                )
            )
            financial_rows = _run(
                session,
                QueryTemplate.FINANCIAL_COMPONENT_SUM,
                {"component_type": "platform_fee", "platform": "swiggy", "limit": 200},
            )
            financial_total = sum(
                (Decimal(str(row["amount"])) for row in financial_rows),
                start=Decimal("0"),
            )
            evidence_seed = session.run(
                "MATCH (component:MoneyComponent)-[:EVIDENCED_BY]->(chunk:EvidenceChunk) "
                "RETURN component.node_id AS component_id LIMIT 1"
            ).single(strict=True)
            evidence_rows = _run(
                session,
                QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT,
                {"component_id": str(evidence_seed["component_id"]), "limit": 10},
            )
            evidence_row = evidence_rows[0]
            citation = EvidenceCitation(
                citation_id="smoke:citation:1",
                chunk_node_id=str(evidence_row["chunk"]["node_id"]),
                source_node_id=str(evidence_row["source"]["node_id"]),
                source_hash=str(evidence_row["chunk"]["source_hash"]),
                authority_score=Decimal("0.90"),
                supports_claim_ids=("smoke:claim:1",),
                quality_flags=(),
            )
            verification = verify_evidence_pack(
                EvidencePack(claim_ids=("smoke:claim:1",), citations=(citation,))
            )
            lexical_rows = _run(
                session,
                QueryTemplate.FULLTEXT_EVIDENCE,
                {"query": "order", "limit": 10},
            )
            delivery_seed = session.run(
                "MATCH (:Order)-[:HAS_DELIVERY_MENTION]->(mention:PersonMention) "
                "RETURN mention.normalized_value_private AS name LIMIT 1"
            ).single()
            delivery_rows = (
                []
                if delivery_seed is None
                else _run(
                    session,
                    QueryTemplate.DELIVERY_MENTION_COUNT,
                    {"normalized_name": str(delivery_seed["name"]), "limit": 20},
                )
            )
    finally:
        driver.close()
    result = {
        "merchant_order_count_rows": len(merchant_count),
        "merchant_order_count_positive": bool(merchant_count[0]["order_count"]),
        "price_history_rows": len(price_history),
        "financial_component_rows": len(financial_rows),
        "financial_decimal_total_positive": financial_total > 0,
        "evidence_rows": len(evidence_rows),
        "evidence_verification": verification.status.value,
        "lexical_rows": len(lexical_rows),
        "delivery_query_rows": len(delivery_rows),
    }
    if verification.status is not VerificationStatus.VERIFIED or not all(
        (
            result["merchant_order_count_positive"],
            result["financial_decimal_total_positive"],
            result["evidence_rows"],
            result["lexical_rows"],
        )
    ):
        raise ValueError("governed retrieval smoke suite failed")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
