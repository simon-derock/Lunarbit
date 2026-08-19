// Frontend data-frame DTOs. These mirror the public FastAPI projection only.
// No Neo4j access, no Cypher, no money math, no private artifacts here.

export type LayerId =
  "evidence" | "commerce" | "product" | "identity" | "financial" | "intelligence";

export type PrivacyState = "public" | "redacted";

export interface Metric {
  label: string;
  value: string;
  delta: string;
  unit: string;
  temporal_scope: string;
}

export interface GraphNode {
  id: string;
  type: string;
  layer: LayerId;
  label: string;
  detail: string;
  weight: number;
  source_count: number;
  confidence: number;
  public_only: boolean;
  privacy_state: PrivacyState;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  provenance_label: string;
  aggregate_count?: number;
}

export interface Finding {
  id: string;
  title: string;
  detail: string;
  confidence: number;
  status: "verified" | "residual" | "conflict" | "abstained";
  graph_path: string[];
  evidence_ids: string[];
  calculation: string;
  limitations: string;
}

export interface EvidenceCard {
  id: string;
  title: string;
  authority: string;
  truth_scope: string;
  source_type: string;
  disclosure: string;
  verification_status: "passed" | "bounded" | "pending";
}

export interface Snapshot {
  metrics: Metric[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  findings: Finding[];
  evidence_cards: EvidenceCard[];
  disclosure: string;
}
