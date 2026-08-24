import type { Finding, GraphEdge, GraphNode, LayerId, Metric, Snapshot } from "./graph";

const API_BASE = import.meta.env.VITE_LUNARBIT_API_URL ?? "http://127.0.0.1:8000";

export interface PublicSnapshotPayload {
  mode: string;
  disclosure: string;
  metrics: { label: string; value: string; detail?: string | null }[];
  sample_questions: string[];
  nodes: {
    id: string;
    label: string;
    title: string;
    subtitle: string;
    properties: Record<string, string | number | boolean | null>;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    relationship: string;
    properties: Record<string, string | number | boolean | null>;
  }[];
}

export interface PublicQueryPlanPayload {
  intent: string;
  selected_tools: string[];
  actions: string[];
  action_budget: number;
  maximum_depth: number;
  candidate_paths_per_step: number;
  verification_required: boolean;
}

export async function fetchPublicSnapshot(signal?: AbortSignal): Promise<PublicSnapshotPayload> {
  const response = await fetch(`${API_BASE}/v1/public/snapshot`, { signal });
  if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
  return (await response.json()) as PublicSnapshotPayload;
}

export async function fetchQueryPlan(question: string): Promise<PublicQueryPlanPayload> {
  const response = await fetch(`${API_BASE}/v1/query/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) throw new Error(`query plan request failed: ${response.status}`);
  return (await response.json()) as PublicQueryPlanPayload;
}

const LAYER_BY_LABEL: Record<string, LayerId> = {
  Platform: "commerce",
  Order: "commerce",
  Merchant: "commerce",
  Item: "product",
  MoneyComponent: "financial",
  Evidence: "evidence",
  Reconciliation: "financial",
};

function layerFor(label: string): LayerId {
  return LAYER_BY_LABEL[label] ?? "intelligence";
}

export function mapPublicSnapshot(payload: PublicSnapshotPayload): Snapshot {
  const graph_nodes: GraphNode[] = payload.nodes.map((node, index) => {
    const layer = layerFor(node.label);
    const confidence = Number(node.properties.confidence ?? 0.95);
    return {
      id: node.id,
      type: node.label,
      layer,
      label: node.title,
      weight: 2 + Math.min(8, Number(node.properties.weight ?? 2)),
      source_count: Number(node.properties.source_count ?? 1),
      confidence: Number.isFinite(confidence) ? confidence : 0.95,
      privacy_state: "public",
      scope: node.subtitle || `public-${index + 1}`,
    };
  });
  const graph_edges: GraphEdge[] = payload.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    relationship_type: edge.relationship,
    confidence: Number(edge.properties.confidence ?? 0.95),
    provenance_label: "public projection",
  }));
  const metrics: Metric[] = payload.metrics.map((metric) => ({
    label: metric.label,
    value: metric.value,
    unit: metric.detail ?? "aggregate",
    scope: payload.mode,
  }));
  const findings: Finding[] = payload.sample_questions.slice(0, 6).map((question, index) => ({
    id: `public-question-${index + 1}`,
    title: question,
    confidence: 0.95,
    status: "verified",
    graph_path: graph_nodes.slice(index, index + 3).map((node) => node.label),
  }));
  return { metrics, graph_nodes, graph_edges, findings, disclosure: payload.disclosure };
}
