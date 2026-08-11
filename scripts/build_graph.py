#!/usr/bin/env python3
"""Compile private canonical archives into a closed, storage-neutral graph."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from lunarbit.agentic import _atomic_private_write, load_agentic_evidence_bundles
from lunarbit.agentic_quality import AgenticRegionRecord
from lunarbit.finance import MoneyComponent, ReconciliationRun
from lunarbit.graph import (
    CanonicalGraph,
    GraphNode,
    GraphRelationship,
    NodeLabel,
    RelationshipType,
)
from lunarbit.models import EntityType, SourceDocument, SourceMessage
from lunarbit.product import ItemEvidenceObservation, MerchantItem
from lunarbit.resolve import (
    CanonicalLegalEntity,
    CanonicalMerchant,
    CanonicalOrder,
    DeliveryPartnerMention,
    EntityEvidenceMention,
    OrderDocumentBundle,
    ProvisionalOutlet,
    ResolutionDecision,
)

GRAPH_ARCHIVE_VERSION = "1.0.0"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, required=True)
    parser.add_argument("--canonical-regions", type=Path, required=True)
    parser.add_argument("--order-root", type=Path, required=True)
    parser.add_argument("--entity-root", type=Path, required=True)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read[T: BaseModel](path: Path, model: type[T]) -> tuple[T, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _nid(kind: str, value: object) -> str:
    return f"{kind}:{value}"


def _rid(
    relationship_type: RelationshipType,
    source: str,
    target: str,
) -> str:
    digest = sha256(f"{relationship_type.value}|{source}|{target}".encode()).hexdigest()[:24]
    return f"relationship:{relationship_type.value.casefold()}:{digest}"


def _relationship(
    relationship_type: RelationshipType,
    source: str,
    target: str,
) -> GraphRelationship:
    return GraphRelationship(
        relationship_id=_rid(relationship_type, source, target),
        relationship_type=relationship_type,
        source_node_id=source,
        target_node_id=target,
        properties={},
    )


def _decision_node(decision: ResolutionDecision) -> GraphNode:
    return GraphNode(
        node_id=_nid("resolution", decision.resolution_id),
        labels=(NodeLabel.RESOLUTION_DECISION,),
        properties={
            "resolution_type": decision.resolution_type.value,
            "status": decision.status.value,
            "selected_score": str(decision.selected_score),
            "decision_margin": str(decision.decision_margin),
            "positive_signals": json.dumps([item.value for item in decision.positive_signals]),
            "negative_signals": json.dumps([item.value for item in decision.negative_signals]),
            "policy_version": decision.policy_version,
            "decided_at": decision.decided_at.isoformat(),
        },
    )


def main() -> int:
    args = _args()
    inventory = args.processed_root / "_inventory"
    messages = _read(inventory / "source_messages.jsonl", SourceMessage)
    documents = _read(inventory / "documents.jsonl", SourceDocument)
    chunks = tuple(
        chunk
        for bundle in load_agentic_evidence_bundles(args.processed_root)
        for chunk in bundle.chunks
    )
    regions = _read(args.canonical_regions, AgenticRegionRecord)
    orders = _read(args.order_root / "orders.jsonl", CanonicalOrder)
    order_bundles = _read(args.order_root / "bundles.jsonl", OrderDocumentBundle)
    order_decisions = _read(args.order_root / "decisions.jsonl", ResolutionDecision)
    mentions = _read(args.entity_root / "mentions.jsonl", EntityEvidenceMention)
    merchants = _read(args.entity_root / "merchants.jsonl", CanonicalMerchant)
    outlets = _read(args.entity_root / "outlets.jsonl", ProvisionalOutlet)
    legal_entities = _read(args.entity_root / "legal_entities.jsonl", CanonicalLegalEntity)
    delivery_mentions = _read(args.entity_root / "delivery_mentions.jsonl", DeliveryPartnerMention)
    entity_decisions = _read(args.entity_root / "decisions.jsonl", ResolutionDecision)
    item_observations = _read(args.product_root / "observations.jsonl", ItemEvidenceObservation)
    merchant_items = _read(args.product_root / "merchant_items.jsonl", MerchantItem)
    money_components = _read(args.finance_root / "money_components.jsonl", MoneyComponent)
    reconciliations = _read(args.finance_root / "reconciliation_runs.jsonl", ReconciliationRun)

    nodes: list[GraphNode] = []
    relationships: list[GraphRelationship] = []
    for platform in ("swiggy", "zomato"):
        nodes.append(
            GraphNode(
                node_id=_nid("platform", platform),
                labels=(NodeLabel.PLATFORM,),
                properties={"name": platform.title(), "platform_type": "commerce"},
            )
        )
    for message in messages:
        nodes.append(
            GraphNode(
                node_id=_nid("message", message.message_id),
                labels=(NodeLabel.SOURCE_MESSAGE,),
                properties={
                    "message_id": message.message_id,
                    "platform": message.platform.value,
                    "category": message.category.value,
                    "occurred_at": message.occurred_at.isoformat() if message.occurred_at else None,
                    "privacy_class": "private",
                },
            )
        )
    for document in documents:
        document_node = _nid("document", document.document_id)
        nodes.append(
            GraphNode(
                node_id=document_node,
                labels=(NodeLabel.DOCUMENT,),
                properties={
                    "document_id": document.document_id,
                    "sha256": document.sha256,
                    "document_type": document.role.value,
                    "platform": document.platform.value,
                    "page_count": document.page_count,
                    "privacy_class": "private",
                },
            )
        )
        relationships.append(
            _relationship(
                RelationshipType.DOCUMENTED_BY,
                _nid("message", document.message_id),
                document_node,
            )
        )
    for chunk in chunks:
        chunk_node = _nid("chunk", chunk.chunk_id)
        nodes.append(
            GraphNode(
                node_id=chunk_node,
                labels=(NodeLabel.EVIDENCE_CHUNK,),
                properties={
                    "chunk_id": str(chunk.chunk_id),
                    "chunk_type": chunk.chunk_type.value,
                    "semantic_role": chunk.semantic_role.value,
                    "financial_role": chunk.financial_role.value,
                    "normalized_text_private": chunk.normalized_text_private,
                    "semantic_summary_private": chunk.semantic_summary_private,
                    "source_hash": chunk.source_hash,
                    "privacy_class": "private",
                },
            )
        )
        source_node = _nid(
            "document" if chunk.document_id else "message",
            chunk.source_id,
        )
        relationships.append(_relationship(RelationshipType.HAS_CHUNK, source_node, chunk_node))
    for record in regions:
        region_node = _nid("region", record.region_id)
        nodes.append(
            GraphNode(
                node_id=region_node,
                labels=(NodeLabel.AGENTIC_REGION,),
                properties={
                    "region_id": str(record.region_id),
                    "title_private": record.region.region_title_private,
                    "summary_private": record.region.semantic_summary_private,
                    "embedding_text_private": record.region.embedding_text_private,
                    "origin": record.origin.value,
                    "quality_issues": json.dumps([item.value for item in record.quality_issues]),
                    "model": record.model,
                    "privacy_class": "private",
                },
            )
        )
        for chunk_id in record.region.source_chunk_ids:
            relationships.append(
                _relationship(RelationshipType.GROUPED_INTO, _nid("chunk", chunk_id), region_node)
            )
    for decision in (*order_decisions, *entity_decisions):
        nodes.append(_decision_node(decision))
    bundle_by_order = {bundle.order_id: bundle for bundle in order_bundles}
    for order in orders:
        order_node = _nid("order", order.order_id)
        nodes.append(
            GraphNode(
                node_id=order_node,
                labels=(NodeLabel.ORDER,),
                properties={
                    "order_id": str(order.order_id),
                    "platform": order.platform.value,
                    "order_type": order.category.value,
                    "identity_status": order.identity_status.value,
                    "privacy_class": "private",
                },
            )
        )
        relationships.append(
            _relationship(
                RelationshipType.PLACED_ON, order_node, _nid("platform", order.platform.value)
            )
        )
        relationships.append(
            _relationship(
                RelationshipType.RESOLVES_TO,
                _nid("resolution", order.resolution_id),
                order_node,
            )
        )
        bundle = bundle_by_order[order.order_id]
        for message_id in bundle.message_ids:
            relationships.append(
                _relationship(
                    RelationshipType.DOCUMENTED_BY, order_node, _nid("message", message_id)
                )
            )
        for document_id in bundle.document_ids:
            relationships.append(
                _relationship(
                    RelationshipType.DOCUMENTED_BY,
                    order_node,
                    _nid("document", document_id),
                )
            )
    for mention in mentions:
        label = (
            NodeLabel.PERSON_MENTION
            if mention.entity_type is EntityType.DELIVERY_PARTNER
            else NodeLabel.ENTITY_MENTION
        )
        mention_node = _nid("mention", mention.mention_id)
        nodes.append(
            GraphNode(
                node_id=mention_node,
                labels=(label,),
                properties={
                    "mention_id": str(mention.mention_id),
                    "entity_type": mention.entity_type.value,
                    "raw_value_private": mention.raw_value_private,
                    "normalized_value_private": mention.normalized_value_private,
                    "platform": mention.platform.value,
                    "privacy_class": "private",
                },
            )
        )
        relationships.append(
            _relationship(
                RelationshipType.MENTIONED_IN, mention_node, _nid("chunk", mention.source_chunk_id)
            )
        )
    canonical_entities = [
        (
            merchant.merchant_id,
            merchant.resolution_id,
            merchant.mention_ids,
            NodeLabel.MERCHANT,
            "merchant",
            {
                "display_name_private": merchant.display_name_private,
                "normalized_name_private": merchant.normalized_name_private,
                "platform": merchant.platform.value,
            },
        )
        for merchant in merchants
    ] + [
        (
            entity.legal_entity_id,
            entity.resolution_id,
            entity.mention_ids,
            NodeLabel.LEGAL_ENTITY,
            "legal_entity",
            {
                "legal_name_private": entity.legal_name_private,
                "normalized_name_private": entity.normalized_name_private,
                "platform": entity.platform.value,
                "identity_status": entity.identity_status.value,
            },
        )
        for entity in legal_entities
    ]
    for entity_id, resolution_id, mention_ids, label, kind, properties in canonical_entities:
        entity_node = _nid(kind, entity_id)
        nodes.append(GraphNode(node_id=entity_node, labels=(label,), properties=properties))
        relationships.append(
            _relationship(
                RelationshipType.RESOLVES_TO, _nid("resolution", resolution_id), entity_node
            )
        )
        for mention_id in mention_ids:
            relationships.append(
                _relationship(
                    RelationshipType.EVALUATED_BY,
                    _nid("mention", mention_id),
                    _nid("resolution", resolution_id),
                )
            )
    for outlet in outlets:
        outlet_node = _nid("outlet", outlet.outlet_id)
        nodes.append(
            GraphNode(
                node_id=outlet_node,
                labels=(NodeLabel.OUTLET,),
                properties={
                    "identity_status": outlet.identity_status.value,
                    "privacy_class": "private",
                },
            )
        )
        relationships.extend(
            (
                _relationship(
                    RelationshipType.ORDERED_FROM, _nid("order", outlet.order_id), outlet_node
                ),
                _relationship(
                    RelationshipType.OUTLET_OF, outlet_node, _nid("merchant", outlet.merchant_id)
                ),
                _relationship(
                    RelationshipType.RESOLVES_TO,
                    _nid("resolution", outlet.resolution_id),
                    outlet_node,
                ),
            )
        )
        for mention_id in outlet.mention_ids:
            relationships.append(
                _relationship(
                    RelationshipType.EVALUATED_BY,
                    _nid("mention", mention_id),
                    _nid("resolution", outlet.resolution_id),
                )
            )
    for delivery in delivery_mentions:
        for order_id in delivery.order_ids:
            relationships.append(
                _relationship(
                    RelationshipType.HAS_DELIVERY_MENTION,
                    _nid("order", order_id),
                    _nid("mention", delivery.mention_id),
                )
            )
    for observation in item_observations:
        observation_node = _nid("item_observation", observation.observation_id)
        nodes.append(
            GraphNode(
                node_id=observation_node,
                labels=(NodeLabel.ITEM_OBSERVATION,),
                properties={
                    "raw_name_private": observation.raw_name_private,
                    "normalized_name_private": observation.normalized_name_private,
                    "observed_amount": str(observation.observed_amount),
                    "currency": observation.currency,
                    "privacy_class": "private",
                },
            )
        )
        relationships.extend(
            (
                _relationship(
                    RelationshipType.HAS_ITEM_OBSERVATION,
                    _nid("order", observation.order_id),
                    observation_node,
                ),
                _relationship(
                    RelationshipType.EVIDENCED_BY,
                    observation_node,
                    _nid("chunk", observation.source_chunk_id),
                ),
            )
        )
    for item in merchant_items:
        item_node = _nid("merchant_item", item.merchant_item_id)
        nodes.append(
            GraphNode(
                node_id=item_node,
                labels=(NodeLabel.MERCHANT_ITEM,),
                properties={
                    "display_name_private": item.display_name_private,
                    "normalized_name_private": item.normalized_name_private,
                    "privacy_class": "private",
                },
            )
        )
        for observation_id in item.observation_ids:
            relationships.append(
                _relationship(
                    RelationshipType.LISTING_OF, _nid("item_observation", observation_id), item_node
                )
            )
    for component in money_components:
        component_node = _nid("money", component.component_id)
        nodes.append(
            GraphNode(
                node_id=component_node,
                labels=(NodeLabel.MONEY_COMPONENT,),
                properties={
                    "component_type": component.component_type.value,
                    "amount": str(component.amount),
                    "currency": component.currency,
                    "scope": component.scope.value,
                    "truth_scope": component.truth_scope.value,
                    "epistemic_mode": component.epistemic_mode.value,
                    "funding_status": component.funding_status.value,
                    "privacy_class": "private",
                },
            )
        )
        relationships.append(
            _relationship(
                RelationshipType.EVIDENCED_BY,
                component_node,
                _nid("chunk", component.source_chunk_id),
            )
        )
        for order_id in component.order_ids:
            relationships.append(
                _relationship(
                    RelationshipType.HAS_COMPONENT, _nid("order", order_id), component_node
                )
            )
    for run in reconciliations:
        run_node = _nid("reconciliation", run.reconciliation_id)
        nodes.append(
            GraphNode(
                node_id=run_node,
                labels=(NodeLabel.RECONCILIATION_RUN,),
                properties={
                    "status": run.status.value,
                    "formula": run.formula,
                    "expected_amount": str(run.expected_amount),
                    "calculated_amount": str(run.calculated_amount),
                    "residual": str(run.residual),
                    "algorithm_version": run.algorithm_version,
                },
            )
        )
        order_ids = {
            order_id
            for component in money_components
            if component.component_id in run.component_ids
            for order_id in component.order_ids
        }
        for order_id in order_ids:
            relationships.append(
                _relationship(RelationshipType.RECONCILED_BY, _nid("order", order_id), run_node)
            )
        for component_id in run.component_ids:
            relationships.append(
                _relationship(RelationshipType.USED, run_node, _nid("money", component_id))
            )

    relationship_by_id: dict[str, GraphRelationship] = {}
    for relationship in relationships:
        existing = relationship_by_id.get(relationship.relationship_id)
        if existing is not None and existing != relationship:
            raise ValueError("relationship identity collision")
        relationship_by_id[relationship.relationship_id] = relationship
    graph = CanonicalGraph(
        nodes=tuple(sorted(nodes, key=lambda node: node.node_id)),
        relationships=tuple(
            sorted(
                relationship_by_id.values(),
                key=lambda relationship: relationship.relationship_id,
            )
        ),
    )
    node_content = "".join(f"{node.model_dump_json()}\n" for node in graph.nodes).encode()
    relationship_content = "".join(
        f"{relationship.model_dump_json()}\n" for relationship in graph.relationships
    ).encode()
    output = args.output.resolve()
    _atomic_private_write(output / "nodes.jsonl", node_content)
    _atomic_private_write(output / "relationships.jsonl", relationship_content)
    manifest = {
        "archive_version": GRAPH_ARCHIVE_VERSION,
        "nodes": len(graph.nodes),
        "relationships": len(graph.relationships),
        "node_sha256": sha256(node_content).hexdigest(),
        "relationship_sha256": sha256(relationship_content).hexdigest(),
    }
    _atomic_private_write(
        output / "manifest.json",
        f"{json.dumps(manifest, indent=2, sort_keys=True)}\n".encode(),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
