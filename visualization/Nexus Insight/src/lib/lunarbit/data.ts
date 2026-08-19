import type {
  EvidenceCard,
  Finding,
  GraphEdge,
  GraphNode,
  LayerId,
  Metric,
  Snapshot,
} from "./types";
import type { GraphProfile } from "./presets";

/* Deterministic PRNG so a profile always projects the same shape. */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const LAYER_TYPES: Record<LayerId, string[]> = {
  evidence: [
    "Document",
    "Page",
    "EvidenceChunk",
    "EvidenceCell",
    "SourceAssertion",
    "SourceMessage",
  ],
  commerce: ["Order", "OrderLine", "Merchant", "Outlet", "Platform"],
  product: ["ItemObservation", "MerchantItem", "ComparableItemGroup"],
  identity: ["Alias", "LegalEntity", "DeliveryMention", "IdentityDecision", "ProvisionalIdentity"],
  financial: [
    "MoneyComponent",
    "Fee",
    "Tax",
    "Promotion",
    "Discount",
    "Payment",
    "Reconciliation",
    "TemporalFinancialEvent",
  ],
  intelligence: [
    "Finding",
    "Metric",
    "QueryTrace",
    "Hypothesis",
    "Experiment",
    "EvidenceBackedConclusion",
  ],
};

const SCOPES = ["2026-Q1", "2026-Q2", "trailing-90d", "trailing-30d", "lifetime"];

function label(type: string, i: number, r: () => number) {
  const n = 1000 + Math.floor(r() * 8999);
  switch (type) {
    case "Order":
      return `ORD-${n}`;
    case "OrderLine":
      return `LINE-${n}-${i % 7}`;
    case "Merchant":
      return `merchant.${["kestrel", "nimbus", "orbital", "harbour", "solene"][i % 5]}`;
    case "Outlet":
      return `outlet.${["north", "quay", "central", "depot"][i % 4]}`;
    case "Platform":
      return `platform.${["alpha", "meridian", "helix"][i % 3]}`;
    case "MoneyComponent":
      return `component.${["subtotal", "delivery", "service", "packaging"][i % 4]}`;
    case "Fee":
      return `fee.${["platform", "handling", "surge"][i % 3]}`;
    case "Tax":
      return `tax.${["gst", "vat", "levy"][i % 3]}`;
    case "Alias":
      return `alias.${["j.moreau", "d.k.", "ops-desk", "n.r.a."][i % 4]}`;
    case "LegalEntity":
      return `entity.${["kestrel-ltd", "nimbus-bv", "solene-sa"][i % 3]}`;
    default:
      return `${type.toLowerCase()}.${n}`;
  }
}

export function buildSnapshot(profile: GraphProfile): Snapshot {
  const r = rng(profile.id.split("").reduce((a, c) => a + c.charCodeAt(0) * 31, 7));
  const total = Math.round(46 + profile.density * 92);
  const nodes: GraphNode[] = [];

  for (let i = 0; i < total; i++) {
    const layer = profile.layers[i % profile.layers.length]!;
    const types = LAYER_TYPES[layer];
    const type = types[Math.floor(r() * types.length)]!;
    const hub = r() > 0.88;
    nodes.push({
      id: `${layer}-${i}`,
      type,
      layer,
      label: label(type, i, r),
      detail: `${type} · scope ${SCOPES[Math.floor(r() * SCOPES.length)]!}`,
      weight: hub ? 7 + r() * 5 : 1 + r() * 3,
      source_count: 1 + Math.floor(r() * 9),
      confidence: Number((0.62 + r() * 0.37).toFixed(2)),
      public_only: true,
      privacy_state: r() > 0.9 ? "redacted" : "public",
    });
  }

  const hubs = nodes.filter((n) => n.weight > 6);
  const edges: GraphEdge[] = [];
  nodes.forEach((node, i) => {
    const fanout = node.weight > 6 ? 4 + Math.floor(r() * 5) : 1 + Math.floor(r() * 2);
    for (let k = 0; k < fanout; k++) {
      const toHub = r() > 0.45 && hubs.length > 0;
      const target = toHub
        ? hubs[Math.floor(r() * hubs.length)]
        : nodes[Math.floor(r() * nodes.length)];
      if (!target || target.id === node.id) continue;
      const rel = profile.relationships[Math.floor(r() * profile.relationships.length)]!;
      edges.push({
        id: `e-${i}-${k}`,
        source: node.id,
        target: target.id,
        relationship_type: rel,
        confidence: Number((0.55 + r() * 0.44).toFixed(2)),
        provenance_label: `chunk#${1000 + Math.floor(r() * 8999)}`,
      });
    }
  });

  const metrics: Metric[] = [
    {
      label: "Nodes projected",
      value: String(nodes.length),
      delta: "+4.2%",
      unit: "nodes",
      temporal_scope: "live",
    },
    {
      label: "Edges projected",
      value: String(edges.length),
      delta: "+6.8%",
      unit: "rels",
      temporal_scope: "live",
    },
    {
      label: "Citation coverage",
      value: `${88 + Math.floor(r() * 10)}`,
      delta: "+1.1",
      unit: "%",
      temporal_scope: "trailing-30d",
    },
    {
      label: "Abstention rate",
      value: `${3 + Math.floor(r() * 5)}`,
      delta: "-0.6",
      unit: "%",
      temporal_scope: "trailing-30d",
    },
    {
      label: "Fusion channels",
      value: "4",
      delta: "RRF",
      unit: "exact·lex·dense·graph",
      temporal_scope: "live",
    },
    {
      label: "Reranked candidates",
      value: String(120 + Math.floor(r() * 80)),
      delta: "bounded",
      unit: "cands",
      temporal_scope: "per query",
    },
  ];

  const statuses: Finding["status"][] = ["verified", "residual", "conflict", "abstained"];
  const findings: Finding[] = Array.from({ length: 6 }).map((_, i) => {
    const path = Array.from({ length: 3 + (i % 2) }).map(
      () => nodes[Math.floor(r() * nodes.length)]!.label,
    );
    return {
      id: `finding-${i}`,
      title: [
        "Delivery fee drifts above merchant-declared scope",
        "Alias cluster resolves to a single legal entity",
        "Promotion applied twice on one order line",
        "Tax component missing source assertion",
        "Comparable item priced apart across platforms",
        "Reconciliation residual persists after fee netting",
      ][i]!,
      detail:
        "Derived from bounded traversal over reconciled money components with citation-gated verification.",
      confidence: Number((0.6 + r() * 0.39).toFixed(2)),
      status: statuses[i % statuses.length]!,
      graph_path: path,
      evidence_ids: [`chunk#${2000 + i * 17}`, `chunk#${3000 + i * 29}`],
      calculation: "Σ(component) − Σ(fee, tax, promotion) at source Decimal scope",
      limitations: "Scoped to public projection; private source claims excluded.",
    };
  });

  const evidence_cards: EvidenceCard[] = Array.from({ length: 4 }).map((_, i) => ({
    id: `evidence-${i}`,
    title: [
      "Merchant statement extract",
      "Platform settlement table",
      "Order confirmation",
      "Reconciliation ledger",
    ][i]!,
    authority: ["primary", "primary", "secondary", "derived"][i]!,
    truth_scope: ["source-declared", "platform-declared", "source-declared", "normalized"][i]!,
    source_type: ["table", "table", "message", "computed"][i]!,
    disclosure: "Redacted public projection · identifiers hashed",
    verification_status: (["passed", "bounded", "passed", "pending"] as const)[i]!,
  }));

  return {
    metrics,
    graph_nodes: nodes,
    graph_edges: edges,
    findings,
    evidence_cards,
    disclosure:
      "Public projection only. Values pass privacy validation before render; no raw documents, identifiers or tokens are exposed.",
  };
}

export const PLAN_SAMPLE = {
  intent: "financial_scope_reconciliation",
  selected_tools: ["exact_lookup", "lexical_bm25", "dense_embed_v4", "graph_traverse", "rerank_v4"],
  actions: 6,
  action_budget: 8,
  maximum_depth: 4,
  candidate_paths_per_step: 12,
  verification_required: true,
};
