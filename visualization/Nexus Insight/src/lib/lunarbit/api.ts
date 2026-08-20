import type {
  EvidenceCard,
  Finding,
  GraphEdge,
  GraphNode,
  LayerId,
  Metric,
  Snapshot,
} from "./types";

/** Browser-safe DTOs served by FastAPI. Neo4j never crosses this boundary. */
interface PublicMetricDto {
  label: string;
  value: string;
  detail?: string | null;
}

interface PublicNodeDto {
  id: string;
  label:
    "Platform" | "Order" | "Merchant" | "Item" | "MoneyComponent" | "Evidence" | "Reconciliation";
  title: string;
  subtitle: string;
  properties: Record<string, string | number | boolean | null>;
}

interface PublicEdgeDto {
  id: string;
  source: string;
  target: string;
  relationship: string;
  properties?: Record<string, string | number | boolean | null>;
}

interface PublicSnapshotDto {
  mode: string;
  disclosure: string;
  metrics: PublicMetricDto[];
  sample_questions: string[];
  nodes: PublicNodeDto[];
  edges: PublicEdgeDto[];
}

export interface QueryPlanDto {
  intent: string;
  selected_tools: string[];
  actions: string[];
  action_budget: number;
  maximum_depth: number;
  candidate_paths_per_step: number;
  verification_required: boolean;
}

export interface PublicEvidenceCardDto {
  id: string;
  title: string;
  authority: string;
  truth_scope: string;
  disclosure: string;
}

export interface PublicDemoAnswerDto {
  status: "verified";
  direct_answer: string;
  calculation: string;
  confidence_scope: string;
  graph_path: string[];
  evidence: PublicEvidenceCardDto[];
  limitations: string[];
}

export interface PublicShowcaseAnswerDto {
  status: "verified" | "abstained";
  plan: QueryPlanDto;
  answer: PublicDemoAnswerDto | null;
  limitations: string[];
}

// Lovable's sandbox intentionally strips Vite proxies. In development we therefore
// use FastAPI directly (CORS is allowlisted); deployed builds use `/api` unless an
// explicit public API origin is supplied at build time.
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "/api")
).replace(/\/$/, "");

function numberProperty(properties: PublicNodeDto["properties"], key: string, fallback: number) {
  const value = properties[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function layerFor(label: PublicNodeDto["label"]): LayerId {
  if (label === "Evidence") return "evidence";
  if (label === "Item") return "product";
  if (label === "MoneyComponent" || label === "Reconciliation") return "financial";
  return "commerce";
}

function nodeDetail(node: PublicNodeDto) {
  const visible = Object.entries(node.properties)
    .filter(([, value]) => value !== null)
    .slice(0, 3)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
  return visible ? `${node.subtitle} · ${visible}` : node.subtitle;
}

function normalizeSnapshot(payload: PublicSnapshotDto): Snapshot {
  const graph_nodes: GraphNode[] = payload.nodes.map((node) => {
    const layer = layerFor(node.label);
    return {
      id: node.id,
      type: node.label,
      layer,
      label: node.title,
      detail: nodeDetail(node),
      weight: numberProperty(node.properties, "weight", node.label === "Order" ? 4 : 2),
      source_count: numberProperty(node.properties, "source_count", 1),
      confidence: numberProperty(node.properties, "confidence", 0.94),
      public_only: true,
      privacy_state: node.properties.privacy_state === "redacted" ? "redacted" : "public",
    };
  });

  const graph_edges: GraphEdge[] = payload.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    relationship_type: edge.relationship,
    confidence: 0.94,
    provenance_label:
      typeof edge.properties?.count === "number"
        ? `${edge.properties.count.toLocaleString()} aggregate relationships`
        : "FastAPI public projection",
    aggregate_count: typeof edge.properties?.count === "number" ? edge.properties.count : undefined,
  }));

  const metrics: Metric[] = payload.metrics.map((metric) => ({
    label: metric.label,
    value: metric.value,
    delta: metric.detail ?? "verified projection",
    unit: "",
    temporal_scope: payload.mode.replaceAll("_", " "),
  }));

  const evidenceNodes = graph_nodes.filter((node) => node.type === "Evidence");
  const evidence_cards: EvidenceCard[] = evidenceNodes.map((node) => ({
    id: node.id,
    title: node.label,
    authority: "public projection",
    truth_scope: node.detail,
    source_type: "redacted evidence",
    disclosure: payload.disclosure,
    verification_status: "bounded",
  }));

  const findings: Finding[] = graph_nodes
    .filter((node) => node.type === "Reconciliation")
    .map((node) => ({
      id: `finding:${node.id}`,
      title: node.label,
      detail: node.detail,
      confidence: node.confidence,
      status: "verified",
      graph_path: [node.label],
      evidence_ids: evidenceNodes.map((evidence) => evidence.id),
      calculation: "Published by the deterministic public projection.",
      limitations: payload.disclosure,
    }));

  return {
    metrics,
    graph_nodes,
    graph_edges,
    findings,
    evidence_cards,
    disclosure: payload.disclosure,
  };
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) throw new Error(`Lunarbit API ${response.status}`);
  return (await response.json()) as T;
}

export function fetchPublicSnapshot(signal?: AbortSignal) {
  return getJson<PublicSnapshotDto>("/v1/public/snapshot", { signal }).then(normalizeSnapshot);
}

export function fetchQueryPlan(question: string, signal?: AbortSignal) {
  return getJson<QueryPlanDto>("/v1/query/plan", {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: question.slice(0, 500) }),
  });
}

export function fetchPublicShowcaseAnswer(question: string, signal?: AbortSignal) {
  return getJson<PublicShowcaseAnswerDto>("/v1/public/showcase-answer", {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: question.slice(0, 500) }),
  });
}
