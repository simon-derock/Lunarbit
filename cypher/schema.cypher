// Lunarbit canonical graph schema — Neo4j 5.x
// All writes use node_id/relationship_id MERGE keys and remain idempotent.

CREATE CONSTRAINT document_node_id IF NOT EXISTS
FOR (node:Document) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT evidence_chunk_node_id IF NOT EXISTS
FOR (node:EvidenceChunk) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT agentic_region_node_id IF NOT EXISTS
FOR (node:AgenticRegion) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT assertion_node_id IF NOT EXISTS
FOR (node:Assertion) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT order_node_id IF NOT EXISTS
FOR (node:Order) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT platform_node_id IF NOT EXISTS
FOR (node:Platform) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT merchant_node_id IF NOT EXISTS
FOR (node:Merchant) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT outlet_node_id IF NOT EXISTS
FOR (node:Outlet) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT legal_entity_node_id IF NOT EXISTS
FOR (node:LegalEntity) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT entity_mention_node_id IF NOT EXISTS
FOR (node:EntityMention) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT person_mention_node_id IF NOT EXISTS
FOR (node:PersonMention) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT person_identity_node_id IF NOT EXISTS
FOR (node:PersonIdentity) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT resolution_decision_node_id IF NOT EXISTS
FOR (node:ResolutionDecision) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT item_observation_node_id IF NOT EXISTS
FOR (node:ItemObservation) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT merchant_item_node_id IF NOT EXISTS
FOR (node:MerchantItem) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT canonical_item_node_id IF NOT EXISTS
FOR (node:CanonicalItem) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT comparable_item_group_node_id IF NOT EXISTS
FOR (node:ComparableItemGroup) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT money_component_node_id IF NOT EXISTS
FOR (node:MoneyComponent) REQUIRE node.node_id IS UNIQUE;
CREATE CONSTRAINT reconciliation_run_node_id IF NOT EXISTS
FOR (node:ReconciliationRun) REQUIRE node.node_id IS UNIQUE;

CREATE FULLTEXT INDEX evidence_lexical IF NOT EXISTS
FOR (node:EvidenceChunk) ON EACH [node.normalized_text_private, node.semantic_summary_private];
CREATE FULLTEXT INDEX merchant_item_lexical IF NOT EXISTS
FOR (node:MerchantItem) ON EACH [node.normalized_name_private, node.display_name_private];
CREATE FULLTEXT INDEX entity_alias_lexical IF NOT EXISTS
FOR (node:Merchant|LegalEntity) ON EACH [node.normalized_name_private, node.display_name_private];
