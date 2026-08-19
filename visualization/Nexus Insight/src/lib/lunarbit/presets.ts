import type { LayerId } from "./types";

/* ------------------------------------------------------------------ *
 * Theme presets — page chrome + graph palette in one source of truth
 * ------------------------------------------------------------------ */

export interface ThemePreset {
  id: string;
  name: string;
  hint: string;
  vars: Record<string, string>;
  graph: {
    background: string;
    edge: string;
    edgeHot: string;
    halo: string;
    text: string;
    layers: Record<LayerId, string>;
  };
}

export const THEMES: ThemePreset[] = [
  {
    id: "void",
    name: "Void Mono",
    hint: "Achromatic · hairline",
    vars: {
      "--background": "oklch(0.12 0 0)",
      "--surface": "oklch(0.16 0 0)",
      "--foreground": "oklch(0.97 0 0)",
      "--muted-foreground": "oklch(0.62 0 0)",
      "--border": "oklch(1 0 0 / 12%)",
      "--primary": "oklch(0.97 0 0)",
      "--primary-foreground": "oklch(0.12 0 0)",
      "--accent": "oklch(0.85 0 0)",
      "--glow": "oklch(1 0 0 / 22%)",
    },
    graph: {
      background: "#0a0a0a",
      edge: "rgba(255,255,255,0.16)",
      edgeHot: "rgba(255,255,255,0.85)",
      halo: "rgba(255,255,255,0.9)",
      text: "rgba(255,255,255,0.72)",
      layers: {
        evidence: "#f5f5f5",
        commerce: "#d4d4d4",
        product: "#b3b3b3",
        identity: "#8f8f8f",
        financial: "#ffffff",
        intelligence: "#6e6e6e",
      },
    },
  },
  {
    id: "lunar",
    name: "Lunar Ice",
    hint: "Cyan signal · deep slate",
    vars: {
      "--background": "oklch(0.16 0.03 240)",
      "--surface": "oklch(0.21 0.035 240)",
      "--foreground": "oklch(0.97 0.01 220)",
      "--muted-foreground": "oklch(0.68 0.03 225)",
      "--border": "oklch(0.85 0.12 200 / 18%)",
      "--primary": "oklch(0.85 0.14 197)",
      "--primary-foreground": "oklch(0.16 0.03 240)",
      "--accent": "oklch(0.78 0.16 175)",
      "--glow": "oklch(0.85 0.14 197 / 35%)",
    },
    graph: {
      background: "#0b1119",
      edge: "rgba(122,215,232,0.18)",
      edgeHot: "rgba(160,240,255,0.9)",
      halo: "rgba(120,230,255,0.9)",
      text: "rgba(207,235,245,0.75)",
      layers: {
        evidence: "#7fe7ff",
        commerce: "#5ad6c0",
        product: "#a9e8ff",
        identity: "#4f9ee8",
        financial: "#e8faff",
        intelligence: "#2f7fb5",
      },
    },
  },
  {
    id: "solar",
    name: "Solar Kraft",
    hint: "Amber terminal · warm carbon",
    vars: {
      "--background": "oklch(0.15 0.015 60)",
      "--surface": "oklch(0.2 0.02 60)",
      "--foreground": "oklch(0.96 0.02 85)",
      "--muted-foreground": "oklch(0.68 0.04 70)",
      "--border": "oklch(0.8 0.13 75 / 20%)",
      "--primary": "oklch(0.83 0.16 78)",
      "--primary-foreground": "oklch(0.15 0.015 60)",
      "--accent": "oklch(0.72 0.17 45)",
      "--glow": "oklch(0.83 0.16 78 / 32%)",
    },
    graph: {
      background: "#100d09",
      edge: "rgba(240,190,120,0.16)",
      edgeHot: "rgba(255,214,150,0.9)",
      halo: "rgba(255,205,130,0.9)",
      text: "rgba(245,225,196,0.75)",
      layers: {
        evidence: "#ffd58a",
        commerce: "#ffa95c",
        product: "#f5e3b8",
        identity: "#c98a4b",
        financial: "#fff3d6",
        intelligence: "#9a6b34",
      },
    },
  },
  {
    id: "flux",
    name: "Flux Reactor",
    hint: "Magenta / lime duotone",
    vars: {
      "--background": "oklch(0.14 0.03 320)",
      "--surface": "oklch(0.19 0.04 320)",
      "--foreground": "oklch(0.97 0.01 320)",
      "--muted-foreground": "oklch(0.68 0.04 320)",
      "--border": "oklch(0.75 0.2 340 / 22%)",
      "--primary": "oklch(0.75 0.22 340)",
      "--primary-foreground": "oklch(0.14 0.03 320)",
      "--accent": "oklch(0.86 0.2 130)",
      "--glow": "oklch(0.75 0.22 340 / 35%)",
    },
    graph: {
      background: "#0d0812",
      edge: "rgba(226,120,200,0.16)",
      edgeHot: "rgba(255,150,225,0.9)",
      halo: "rgba(255,140,215,0.9)",
      text: "rgba(240,215,240,0.75)",
      layers: {
        evidence: "#ff8fd6",
        commerce: "#c6f75f",
        product: "#f6b9ea",
        identity: "#8f6ce0",
        financial: "#ffe6f7",
        intelligence: "#6f4bb0",
      },
    },
  },
  {
    id: "chlor",
    name: "Chlorine",
    hint: "Acid green · CRT bloom",
    vars: {
      "--background": "oklch(0.14 0.02 150)",
      "--surface": "oklch(0.18 0.03 150)",
      "--foreground": "oklch(0.96 0.03 140)",
      "--muted-foreground": "oklch(0.66 0.05 145)",
      "--border": "oklch(0.85 0.19 140 / 20%)",
      "--primary": "oklch(0.87 0.2 140)",
      "--primary-foreground": "oklch(0.14 0.02 150)",
      "--accent": "oklch(0.8 0.13 190)",
      "--glow": "oklch(0.87 0.2 140 / 30%)",
    },
    graph: {
      background: "#070d09",
      edge: "rgba(140,240,160,0.16)",
      edgeHot: "rgba(170,255,190,0.9)",
      halo: "rgba(150,255,175,0.9)",
      text: "rgba(210,245,220,0.75)",
      layers: {
        evidence: "#9dffb4",
        commerce: "#5ce8a0",
        product: "#d7ffe3",
        identity: "#3fbf8f",
        financial: "#f0fff5",
        intelligence: "#2a7d5c",
      },
    },
  },
];

/* ------------------------------------------------------------------ *
 * Graph profiles — which slice of the knowledge graph is projected
 * ------------------------------------------------------------------ */

export interface GraphProfile {
  id: string;
  name: string;
  scope: string;
  layers: LayerId[];
  relationships: string[];
  density: number;
}

export const GRAPH_PROFILES: GraphProfile[] = [
  {
    id: "full",
    name: "Full Lineage",
    scope: "All six layers · bounded traversal depth 4",
    layers: ["evidence", "commerce", "product", "identity", "financial", "intelligence"],
    relationships: [
      "PLACED_ON",
      "HAS_ITEM_OBSERVATION",
      "HAS_COMPONENT",
      "RECONCILED_BY",
      "USED",
      "USES",
      "CONTAINS",
      "FULFILLED_BY",
      "ORDERED_FROM",
      "HAS_LINE",
      "HAS_ITEM",
      "HAS_MONEY_COMPONENT",
      "HAS_FEE",
      "HAS_TAX",
      "HAS_PROMOTION",
      "ASSERTS",
      "EVIDENCED_BY",
      "DERIVED_FROM",
      "RECONCILES_TO",
      "CONFLICTS_WITH",
      "RESOLVES_TO",
      "POSSIBLY_SAME_AS",
      "PRECEDES",
      "COMPARED_WITH",
      "SUPPORTS",
      "EXPLAINS",
    ],
    density: 1,
  },
  {
    id: "money",
    name: "Money Trace",
    scope: "Financial components reconciled to orders",
    layers: ["commerce", "financial", "evidence"],
    relationships: [
      "HAS_COMPONENT",
      "RECONCILED_BY",
      "USED",
      "HAS_LINE",
      "HAS_MONEY_COMPONENT",
      "HAS_FEE",
      "HAS_TAX",
      "HAS_PROMOTION",
      "RECONCILES_TO",
      "EVIDENCED_BY",
      "ORDERED_FROM",
    ],
    density: 0.9,
  },
  {
    id: "identity",
    name: "Identity Resolution",
    scope: "Alias → legal entity decisions and provisional links",
    layers: ["identity", "commerce", "evidence"],
    relationships: [
      "RESOLVES_TO",
      "POSSIBLY_SAME_AS",
      "ASSERTS",
      "EVIDENCED_BY",
      "FULFILLED_BY",
      "CONFLICTS_WITH",
    ],
    density: 0.75,
  },
  {
    id: "evidence",
    name: "Evidence Spine",
    scope: "Document → page → chunk → assertion provenance only",
    layers: ["evidence", "intelligence"],
    relationships: ["CONTAINS", "ASSERTS", "EVIDENCED_BY", "DERIVED_FROM", "SUPPORTS", "PLACED_ON"],
    density: 0.8,
  },
  {
    id: "conflict",
    name: "Conflict Surface",
    scope: "Residuals, conflicts and abstention triggers kept visible",
    layers: ["financial", "identity", "intelligence", "evidence"],
    relationships: [
      "CONFLICTS_WITH",
      "RECONCILES_TO",
      "POSSIBLY_SAME_AS",
      "EXPLAINS",
      "DERIVED_FROM",
    ],
    density: 0.6,
  },
  {
    id: "product",
    name: "Comparable Items",
    scope: "Item observations grouped across merchants and platforms",
    layers: ["product", "commerce", "financial"],
    relationships: [
      "HAS_ITEM",
      "HAS_ITEM_OBSERVATION",
      "COMPARED_WITH",
      "ORDERED_FROM",
      "HAS_COMPONENT",
      "PRECEDES",
    ],
    density: 0.85,
  },
];

/* ------------------------------------------------------------------ *
 * Visualization profiles — how the projection is drawn
 * ------------------------------------------------------------------ */

export type NodeShape = "orb" | "ring" | "glyph" | "pin" | "shard";
export type EdgeStyle = "hairline" | "beam" | "arc" | "dotted";

export interface VizProfile {
  id: string;
  name: string;
  hint: string;
  nodeShape: NodeShape;
  edgeStyle: EdgeStyle;
  labels: "hover" | "hubs" | "all";
  particles: boolean;
  charge: number;
  linkDistance: number;
  nodeScale: number;
  glow: number;
}

export const VIZ_PROFILES: VizProfile[] = [
  {
    id: "burst",
    name: "Radial Burst",
    hint: "Long spokes, pinpoint terminals",
    nodeShape: "pin",
    edgeStyle: "hairline",
    labels: "hubs",
    particles: false,
    charge: -220,
    linkDistance: 120,
    nodeScale: 0.75,
    glow: 0.35,
  },
  {
    id: "constellation",
    name: "Constellation",
    hint: "Soft orbs with luminous halos",
    nodeShape: "orb",
    edgeStyle: "beam",
    labels: "hover",
    particles: true,
    charge: -150,
    linkDistance: 70,
    nodeScale: 1,
    glow: 1,
  },
  {
    id: "lattice",
    name: "Signal Lattice",
    hint: "Hollow rings, taut orthogonal pull",
    nodeShape: "ring",
    edgeStyle: "dotted",
    labels: "hubs",
    particles: false,
    charge: -90,
    linkDistance: 44,
    nodeScale: 0.9,
    glow: 0.2,
  },
  {
    id: "telemetry",
    name: "Telemetry",
    hint: "Layer glyphs, all labels, flow particles",
    nodeShape: "glyph",
    edgeStyle: "arc",
    labels: "all",
    particles: true,
    charge: -300,
    linkDistance: 110,
    nodeScale: 1.1,
    glow: 0.5,
  },
  {
    id: "shatter",
    name: "Shard Field",
    hint: "Faceted shards, wide dispersion",
    nodeShape: "shard",
    edgeStyle: "hairline",
    labels: "hover",
    particles: false,
    charge: -420,
    linkDistance: 150,
    nodeScale: 1.05,
    glow: 0.7,
  },
];

export const SORTS = [
  { id: "weight", name: "Centrality" },
  { id: "confidence", name: "Confidence" },
  { id: "sources", name: "Source count" },
  { id: "label", name: "Label A–Z" },
] as const;

export type SortId = (typeof SORTS)[number]["id"];
