from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field, model_validator

from lunarbit.models import ContractModel

type GraphProperty = str | int | float | bool | None


class NodeLabel(StrEnum):
    SOURCE_MESSAGE = "SourceMessage"
    DOCUMENT = "Document"
    EVIDENCE_CHUNK = "EvidenceChunk"
    AGENTIC_REGION = "AgenticRegion"
    ASSERTION = "Assertion"
    ORDER = "Order"
    PLATFORM = "Platform"
    MERCHANT = "Merchant"
    OUTLET = "Outlet"
    LEGAL_ENTITY = "LegalEntity"
    ENTITY_MENTION = "EntityMention"
    PERSON_MENTION = "PersonMention"
    PERSON_IDENTITY = "PersonIdentity"
    RESOLUTION_DECISION = "ResolutionDecision"
    ITEM_OBSERVATION = "ItemObservation"
    MERCHANT_ITEM = "MerchantItem"
    CANONICAL_ITEM = "CanonicalItem"
    COMPARABLE_ITEM_GROUP = "ComparableItemGroup"
    MONEY_COMPONENT = "MoneyComponent"
    RECONCILIATION_RUN = "ReconciliationRun"


class RelationshipType(StrEnum):
    PLACED_ON = "PLACED_ON"
    DOCUMENTED_BY = "DOCUMENTED_BY"
    HAS_CHUNK = "HAS_CHUNK"
    GROUPED_INTO = "GROUPED_INTO"
    ORDERED_FROM = "ORDERED_FROM"
    OUTLET_OF = "OUTLET_OF"
    ISSUED_BY = "ISSUED_BY"
    MENTIONED_IN = "MENTIONED_IN"
    EVALUATED_BY = "EVALUATED_BY"
    RESOLVES_TO = "RESOLVES_TO"
    HAS_DELIVERY_MENTION = "HAS_DELIVERY_MENTION"
    HAS_ITEM_OBSERVATION = "HAS_ITEM_OBSERVATION"
    OBSERVED_AS = "OBSERVED_AS"
    LISTING_OF = "LISTING_OF"
    RESOLVED_TO = "RESOLVED_TO"
    MEMBER_OF = "MEMBER_OF"
    HAS_COMPONENT = "HAS_COMPONENT"
    EVIDENCED_BY = "EVIDENCED_BY"
    RECONCILED_BY = "RECONCILED_BY"
    USED = "USED"


class GraphNode(ContractModel):
    node_id: str = Field(min_length=1)
    labels: tuple[NodeLabel, ...] = Field(min_length=1)
    properties: Mapping[str, GraphProperty]

    @model_validator(mode="after")
    def labels_are_unique(self) -> GraphNode:
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("node labels must be unique")
        return self


class GraphRelationship(ContractModel):
    relationship_id: str = Field(min_length=1)
    relationship_type: RelationshipType
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    properties: Mapping[str, GraphProperty]


class CanonicalGraph(ContractModel):
    nodes: tuple[GraphNode, ...]
    relationships: tuple[GraphRelationship, ...]

    @model_validator(mode="after")
    def graph_references_are_closed(self) -> CanonicalGraph:
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("node IDs must be unique")
        relationship_ids = {relationship.relationship_id for relationship in self.relationships}
        if len(relationship_ids) != len(self.relationships):
            raise ValueError("relationship IDs must be unique")
        if any(
            relationship.source_node_id not in node_ids
            or relationship.target_node_id not in node_ids
            for relationship in self.relationships
        ):
            raise ValueError("relationships must reference existing graph nodes")
        return self


@dataclass(frozen=True, slots=True)
class Neo4jWriteBatch:
    cypher: str
    parameters: dict[str, list[dict[str, object]]]


def _batched[T](values: list[T], size: int) -> tuple[list[T], ...]:
    return tuple(values[index : index + size] for index in range(0, len(values), size))


def neo4j_write_batches(
    graph: CanonicalGraph,
    *,
    batch_size: int = 500,
) -> tuple[Neo4jWriteBatch, ...]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batches: list[Neo4jWriteBatch] = []
    nodes_by_labels: dict[tuple[NodeLabel, ...], list[GraphNode]] = defaultdict(list)
    for node in sorted(graph.nodes, key=lambda value: value.node_id):
        labels = tuple(sorted(node.labels, key=lambda label: label.value))
        nodes_by_labels[labels].append(node)
    for labels in sorted(nodes_by_labels, key=lambda values: tuple(item.value for item in values)):
        label_expression = ":".join(label.value for label in labels)
        cypher = (
            f"UNWIND $rows AS row MERGE (n:LunarbitNode:{label_expression} "
            "{node_id: row.node_id}) "
            "SET n += row.properties"
        )
        for node_batch in _batched(nodes_by_labels[labels], batch_size):
            rows: list[dict[str, object]] = [
                {"node_id": node.node_id, "properties": dict(node.properties)}
                for node in node_batch
            ]
            batches.append(Neo4jWriteBatch(cypher=cypher, parameters={"rows": rows}))

    relationships_by_type: dict[RelationshipType, list[GraphRelationship]] = defaultdict(list)
    for relationship in sorted(graph.relationships, key=lambda value: value.relationship_id):
        relationships_by_type[relationship.relationship_type].append(relationship)
    for relationship_type in sorted(relationships_by_type, key=lambda value: value.value):
        cypher = (
            "UNWIND $rows AS row "
            "MATCH (source:LunarbitNode {node_id: row.source_node_id}) "
            "MATCH (target:LunarbitNode {node_id: row.target_node_id}) "
            f"MERGE (source)-[r:{relationship_type.value} "
            "{relationship_id: row.relationship_id}]->(target) SET r += row.properties"
        )
        for relationship_batch in _batched(relationships_by_type[relationship_type], batch_size):
            relationship_rows: list[dict[str, object]] = [
                {
                    "relationship_id": relationship.relationship_id,
                    "source_node_id": relationship.source_node_id,
                    "target_node_id": relationship.target_node_id,
                    "properties": dict(relationship.properties),
                }
                for relationship in relationship_batch
            ]
            batches.append(Neo4jWriteBatch(cypher=cypher, parameters={"rows": relationship_rows}))
    return tuple(batches)
