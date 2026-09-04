import type { Finding, GraphEdge, GraphNode, LayerId, Metric, Snapshot } from "./graph";

const API_BASE = import.meta.env.VITE_LUNARBIT_API_URL ?? "http://127.0.0.1:8000";

async function fetchWithRetry(input: RequestInfo | URL, init?: RequestInit, attempts = 3): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(input, init);
      if (response.ok || attempt === attempts - 1) return response;
      lastError = new Error(`request failed: ${response.status}`);
    } catch (error) {
      lastError = error;
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      if (attempt === attempts - 1) throw error;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 400 * (attempt + 1)));
  }
  throw lastError instanceof Error ? lastError : new Error("request failed");
}

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

export interface StreamAnswer {
  status: string;
  direct_answer: string | null;
  calculation: string | null;
  fact_count: number;
  citation_ids: string[];
  citations: { citation_id: string; chunk_node_id: string; source_node_id: string; authority_score: number; supports_claim_ids: string[]; quality_flags: string[] }[];
  verification_status: string;
  limitations: string[];
  abstention_reason: string | null;
}

export interface ChatStreamResult {
  session_id: string;
  turn_index: number;
  context_reused: boolean;
  answer: StreamAnswer;
}

export interface SessionHistory {
  session_id: string;
  turns: { turn_index: number; question: string; status: string }[];
}

export function parseSseFrame(frame: string): { event: string; data: Record<string, unknown> } | null {
  const event = frame.match(/^event:\s*(\S+)/m)?.[1];
  const raw = frame.match(/^data:\s*(.*)$/m)?.[1];
  if (!event || !raw) return null;
  const data = JSON.parse(raw) as Record<string, unknown>;
  return { event, data };
}

export async function fetchSessionHistory(sessionId: string): Promise<SessionHistory> {
  const response = await fetchWithRetry(`/api/private/chat/${encodeURIComponent(sessionId)}/history`);
  if (!response.ok) throw new Error(`history request failed: ${response.status}`);
  return (await response.json()) as SessionHistory;
}

export async function streamPrivateChat(
  question: string,
  onStage: (stage: string) => void,
  onCitation: (citation: StreamAnswer["citations"][number]) => void,
  onGraphFocus: (nodeIds: string[]) => void,
  sessionId?: string,
  signal?: AbortSignal,
): Promise<ChatStreamResult> {
  // A POST stream is deliberately never retried: replaying it could duplicate a turn.
  const response = await fetchWithRetry("/api/private/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, ...(sessionId ? { session_id: sessionId } : {}) }),
    signal,
  }, 1);
  if (!response.ok || !response.body) throw new Error(`chat stream failed: ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatStreamResult | null = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const parsed = parseSseFrame(frame);
      if (!parsed) continue;
      const { event, data: payload } = parsed;
      if (event === "thinking") onStage(String(payload.stage ?? "thinking"));
      if (event === "calculation") onStage("calculation");
      if (event === "citation") onCitation(payload as unknown as StreamAnswer["citations"][number]);
      if (event === "graph_focus") onGraphFocus(Array.isArray(payload.node_ids) ? payload.node_ids.map(String) : []);
      if (event === "answer") result = payload as unknown as ChatStreamResult;
      if (event === "error") throw new Error(String(payload.detail ?? payload.code ?? "chat failed"));
    }
    if (done) break;
  }
  if (!result) throw new Error("chat stream ended without an answer");
  return result;
}

export async function fetchPublicSnapshot(signal?: AbortSignal): Promise<PublicSnapshotPayload> {
  const response = await fetchWithRetry(`${API_BASE}/v1/public/snapshot`, { signal });
  if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
  return (await response.json()) as PublicSnapshotPayload;
}

export async function fetchQueryPlan(question: string): Promise<PublicQueryPlanPayload> {
  const response = await fetchWithRetry(`${API_BASE}/v1/query/plan`, {
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
