/* ------------------------------------------------------------------ *
 * Lunarbit data-frame — DTOs, presets and deterministic projection.
 * Mirrors the public FastAPI projection only.
 * ------------------------------------------------------------------ */

export type LayerId =
  | "evidence"
  | "commerce"
  | "product"
  | "identity"
  | "financial"
  | "intelligence";

export interface GraphNode {
  id: string;
  type: string;
  layer: LayerId;
  label: string;
  weight: number;
  source_count: number;
  confidence: number;
  privacy_state: "public" | "redacted";
  scope: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  provenance_label: string;
}

export interface Metric {
  label: string;
  value: string;
  unit: string;
  scope: string;
}

export interface Finding {
  id: string;
  title: string;
  confidence: number;
  status: "verified" | "residual" | "conflict" | "abstained";
  graph_path: string[];
}

export interface Snapshot {
  metrics: Metric[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  findings: Finding[];
  disclosure: string;
}

/* ------------------------------------------------------------------ *
 * Themes — each preset is a distinct ink/paper gamut, not a filter.
 * ------------------------------------------------------------------ */

export interface Palette {
  paper: string;
  ink: string;
  edge: string;
  edgeHot: string;
  layers: Record<LayerId, string>;
  /** chromatic ramp used by multi-colour draw modes */
  chroma: string[];
}

export interface ThemePreset {
  id: string;
  name: string;
  hint: string;
  vars: Record<string, string>;
  palette: Palette;
}

export const THEMES: ThemePreset[] = [
  {
    id: "carbon",
    name: "Carbon",
    hint: "Ink-blue vellum · jewel signal",
    vars: {
      "--background": "#07080c",
      "--surface": "#0d0f15",
      "--foreground": "#e8ebf2",
      "--muted-foreground": "#8a93a4",
      "--border": "#1b1f29",
      "--primary": "#e8ebf2",
      "--primary-foreground": "#07080c",
      "--accent": "#cba36a",
    },
    palette: {
      paper: "#07080c",
      ink: "#e8ebf2",
      edge: "rgba(160,178,206,0.13)",
      edgeHot: "rgba(226,236,255,0.78)",
      layers: {
        evidence: "#eef2fa",
        commerce: "#cba36a",
        product: "#7fb3a6",
        identity: "#8f9ec4",
        financial: "#e7cf9a",
        intelligence: "#6a7490",
      },
      chroma: ["#eef2fa", "#cba36a", "#e0a37e", "#7fb3a6", "#8f9ec4", "#a98fb8"],
    },
  },

  {
    id: "bone",
    name: "Bone",
    hint: "Paper white · press black",
    vars: {
      "--background": "#f3f1ea",
      "--surface": "#eae7dd",
      "--foreground": "#16150f",
      "--muted-foreground": "#6d6a5c",
      "--border": "#cbc6b6",
      "--primary": "#16150f",
      "--primary-foreground": "#f3f1ea",
      "--accent": "#7a4b25",
    },
    palette: {
      paper: "#f3f1ea",
      ink: "#16150f",
      edge: "rgba(22,21,15,0.16)",
      edgeHot: "rgba(22,21,15,0.8)",
      layers: {
        evidence: "#16150f",
        commerce: "#7a4b25",
        product: "#9a7b3f",
        identity: "#4a5a49",
        financial: "#000000",
        intelligence: "#8a8574",
      },
      chroma: ["#16150f", "#7a4b25", "#9a7b3f", "#4a5a49", "#3c4c63", "#8a8574"],
    },
  },
  {
    id: "paper",
    name: "Paper White",
    hint: "Pure sheet · full spectrum plot",
    vars: {
      "--background": "#ffffff",
      "--surface": "#f5f5f6",
      "--foreground": "#101113",
      "--muted-foreground": "#74777d",
      "--border": "#e1e2e5",
      "--primary": "#101113",
      "--primary-foreground": "#ffffff",
      "--accent": "#2f6f6a",
    },
    palette: {
      paper: "#ffffff",
      ink: "#101113",
      edge: "rgba(16,17,19,0.13)",
      edgeHot: "rgba(16,17,19,0.68)",
      layers: {
        evidence: "#101113",
        commerce: "#c2483f",
        product: "#d68a2a",
        identity: "#2f6f6a",
        financial: "#1f3f7a",
        intelligence: "#8e8f95",
      },
      chroma: ["#c2483f", "#d68a2a", "#b8a52d", "#2f6f6a", "#1f3f7a", "#7a3f75"],
    },
  },
  {
    id: "pepper",
    name: "Pepper Drizzle",
    hint: "Charred husk · salt speckle",
    vars: {
      "--background": "#121110",
      "--surface": "#1b1917",
      "--foreground": "#f0e9df",
      "--muted-foreground": "#948b7f",
      "--border": "#2d2926",
      "--primary": "#f0e9df",
      "--primary-foreground": "#121110",
      "--accent": "#d9a05b",
    },
    palette: {
      paper: "#121110",
      ink: "#f0e9df",
      edge: "rgba(240,233,223,0.1)",
      edgeHot: "rgba(255,231,196,0.74)",
      layers: {
        evidence: "#f6f0e6",
        commerce: "#d9a05b",
        product: "#b8763c",
        identity: "#8d8577",
        financial: "#fff8ec",
        intelligence: "#5d564c",
      },
      chroma: ["#f6f0e6", "#d9a05b", "#b8763c", "#8f5a4a", "#7d8071", "#4f4a42"],
    },
  },
  {
    id: "chromatic",
    name: "Black Chromatic",
    hint: "Void field · six-hue signal",
    vars: {
      "--background": "#050506",
      "--surface": "#0d0d10",
      "--foreground": "#eceef2",
      "--muted-foreground": "#7d828c",
      "--border": "#1e2027",
      "--primary": "#eceef2",
      "--primary-foreground": "#050506",
      "--accent": "#5fd0c8",
    },
    palette: {
      paper: "#050506",
      ink: "#eceef2",
      edge: "rgba(236,238,242,0.1)",
      edgeHot: "rgba(236,238,242,0.7)",
      layers: {
        evidence: "#e8eaf0",
        commerce: "#f0674f",
        product: "#f0b83c",
        identity: "#5fd0c8",
        financial: "#6f8cf5",
        intelligence: "#c86ff0",
      },
      chroma: ["#f0674f", "#f0b83c", "#c6e04a", "#5fd0c8", "#6f8cf5", "#c86ff0"],
    },
  },
  {
    id: "monochrome-grain",
    name: "Monochrome Grain",
    hint: "Graphite field · silver grain",
    vars: {
      "--background": "#090a0b",
      "--surface": "#111315",
      "--foreground": "#e8e9e7",
      "--muted-foreground": "#85898a",
      "--border": "#292d2e",
      "--primary": "#e8e9e7",
      "--primary-foreground": "#090a0b",
      "--accent": "#b9bdba",
    },
    palette: {
      paper: "#090a0b",
      ink: "#e8e9e7",
      edge: "rgba(232,233,231,0.14)",
      edgeHot: "rgba(255,255,255,0.86)",
      layers: {
        evidence: "#e8e9e7",
        commerce: "#c8ccca",
        product: "#aeb3b1",
        identity: "#949a99",
        financial: "#f4f5f3",
        intelligence: "#707676",
      },
      chroma: ["#f4f5f3", "#e8e9e7", "#c8ccca", "#aeb3b1", "#949a99", "#707676"],
    },
  },
  {
    id: "grey",
    name: "Grey",
    hint: "Mid concrete · graphite plot",
    vars: {
      "--background": "#b9b9b6",
      "--surface": "#adadaa",
      "--foreground": "#1a1a19",
      "--muted-foreground": "#54544f",
      "--border": "#9a9a96",
      "--primary": "#1a1a19",
      "--primary-foreground": "#d6d6d3",
      "--accent": "#3a3a38",
    },
    palette: {
      paper: "#b9b9b6",
      ink: "#1a1a19",
      edge: "rgba(26,26,25,0.2)",
      edgeHot: "rgba(26,26,25,0.82)",
      layers: {
        evidence: "#111110",
        commerce: "#3b3b39",
        product: "#585856",
        identity: "#6f6f6c",
        financial: "#000000",
        intelligence: "#87877f",
      },
      chroma: ["#111110", "#31312f", "#4c4c49", "#666663", "#7f7f7a", "#96968f"],
    },
  },
  {
    id: "eclipse",
    name: "Eclipse",
    hint: "Night ground · ember corona",
    vars: {
      "--background": "#08070a",
      "--surface": "#100e13",
      "--foreground": "#f4e6dc",
      "--muted-foreground": "#998a83",
      "--border": "#241f27",
      "--primary": "#ff9153",
      "--primary-foreground": "#08070a",
      "--accent": "#e2663a",
    },
    palette: {
      paper: "#08070a",
      ink: "#f4e6dc",
      edge: "rgba(255,145,83,0.12)",
      edgeHot: "rgba(255,178,120,0.78)",
      layers: {
        evidence: "#ffd7b8",
        commerce: "#ff9153",
        product: "#e2663a",
        identity: "#a24730",
        financial: "#fff2e4",
        intelligence: "#6a3324",
      },
      chroma: ["#ffd7b8", "#ffab68", "#ff8a45", "#e2663a", "#b04a2c", "#7a3320"],
    },
  },
  {
    id: "fractal",
    name: "Fractal Violet",
    hint: "Bleached sheet · violet bloom · ember core",
    vars: {
      "--background": "#fbfaff",
      "--surface": "#f2eefb",
      "--foreground": "#150c25",
      "--muted-foreground": "#6c5c8a",
      "--border": "#ddd3f0",
      "--primary": "#3b0fa3",
      "--primary-foreground": "#fbfaff",
      "--accent": "#ff7a18",
    },
    palette: {
      paper: "#fbfaff",
      ink: "#150c25",
      edge: "rgba(70,20,160,0.16)",
      edgeHot: "rgba(90,20,200,0.72)",
      layers: {
        evidence: "#2d0a6b",
        commerce: "#7b16d6",
        product: "#ff7a18",
        identity: "#12b9c9",
        financial: "#c2158c",
        intelligence: "#5b4a86",
      },
      chroma: ["#3b0fa3", "#7b16d6", "#c2158c", "#ff7a18", "#12b9c9", "#f2c200"],
    },
  },
  {
    id: "nocturne",
    name: "Nocturne",
    hint: "Indigo plum · cold silver signal",
    vars: {
      "--background": "#0a0812",
      "--surface": "#120f1d",
      "--foreground": "#e9e4f2",
      "--muted-foreground": "#8b829e",
      "--border": "#221c31",
      "--primary": "#e9e4f2",
      "--primary-foreground": "#0a0812",
      "--accent": "#9d7bd8",
    },
    palette: {
      paper: "#0a0812",
      ink: "#e9e4f2",
      edge: "rgba(190,175,225,0.12)",
      edgeHot: "rgba(226,214,255,0.76)",
      layers: {
        evidence: "#efeaf8",
        commerce: "#9d7bd8",
        product: "#6f8ad8",
        identity: "#c48bb4",
        financial: "#d8cf9a",
        intelligence: "#5b5470",
      },
      chroma: ["#efeaf8", "#9d7bd8", "#6f8ad8", "#c48bb4", "#7fc0c4", "#d8cf9a"],
    },
  },
  {
    id: "bronze",
    name: "Bronze",
    hint: "Foundry dark · patina and brass",
    vars: {
      "--background": "#0c0a08",
      "--surface": "#151109",
      "--foreground": "#f2e7d3",
      "--muted-foreground": "#9a8a72",
      "--border": "#2a2318",
      "--primary": "#e8c98a",
      "--primary-foreground": "#0c0a08",
      "--accent": "#b98a45",
    },
    palette: {
      paper: "#0c0a08",
      ink: "#f2e7d3",
      edge: "rgba(226,197,142,0.12)",
      edgeHot: "rgba(245,214,156,0.78)",
      layers: {
        evidence: "#f6ecd8",
        commerce: "#e8c98a",
        product: "#b98a45",
        identity: "#7f9c86",
        financial: "#d9a05b",
        intelligence: "#5e4c33",
      },
      chroma: ["#f6ecd8", "#e8c98a", "#d9a05b", "#b98a45", "#7f9c86", "#8a5b3a"],
    },
  },
  {
    id: "mist",
    name: "Mist",
    hint: "Pale vapour · slate plot",
    vars: {
      "--background": "#e8ebee",
      "--surface": "#dee2e7",
      "--foreground": "#141a20",
      "--muted-foreground": "#5c6672",
      "--border": "#c3cad2",
      "--primary": "#141a20",
      "--primary-foreground": "#e8ebee",
      "--accent": "#2c5f74",
    },
    palette: {
      paper: "#e8ebee",
      ink: "#141a20",
      edge: "rgba(20,26,32,0.16)",
      edgeHot: "rgba(20,26,32,0.74)",
      layers: {
        evidence: "#141a20",
        commerce: "#2c5f74",
        product: "#6b7f52",
        identity: "#7a5f74",
        financial: "#1d3550",
        intelligence: "#7e8993",
      },
      chroma: ["#141a20", "#2c5f74", "#1d3550", "#6b7f52", "#7a5f74", "#8a6a3a"],
    },
  },
  {
    id: "cinnabar",
    name: "Cinnabar",
    hint: "Lacquer black · vermilion stencil",
    vars: {
      "--background": "#050404",
      "--surface": "#0e0807",
      "--foreground": "#f6e7e2",
      "--muted-foreground": "#9c7a72",
      "--border": "#2a1512",
      "--primary": "#ec2b16",
      "--primary-foreground": "#050404",
      "--accent": "#ff5a2e",
    },
    palette: {
      paper: "#050404",
      ink: "#f6e7e2",
      edge: "rgba(236,43,22,0.30)",
      edgeHot: "rgba(255,120,80,0.92)",
      layers: {
        evidence: "#ffe3d6",
        commerce: "#ec2b16",
        product: "#ff5a2e",
        identity: "#b41b0d",
        financial: "#ff8a5c",
        intelligence: "#7a1408",
      },
      chroma: ["#ec2b16", "#ff5a2e", "#b41b0d", "#ff8a5c", "#ffd0b8", "#7a1408"],
    },
  },
  {
    id: "corium",
    name: "Corium",
    hint: "Void black · plum tissue · silver myelin",
    vars: {
      "--background": "#040305",
      "--surface": "#0d0910",
      "--foreground": "#efe2e8",
      "--muted-foreground": "#9a8390",
      "--border": "#241825",
      "--primary": "#e8c9d4",
      "--primary-foreground": "#040305",
      "--accent": "#a4485f",
    },
    palette: {
      paper: "#040305",
      ink: "#efe2e8",
      edge: "rgba(198,146,160,0.22)",
      edgeHot: "rgba(255,226,232,0.9)",
      layers: {
        evidence: "#f3dfe4",
        commerce: "#c07285",
        product: "#a4485f",
        identity: "#7c3a4e",
        financial: "#d9a2ad",
        intelligence: "#5a2a38",
      },
      chroma: ["#f3dfe4", "#d9a2ad", "#c07285", "#a4485f", "#7a3346", "#4a2030"],
    },
  },
  {
    id: "golgi",
    name: "Golgi",
    hint: "Pure black · magenta stain",
    vars: {
      "--background": "#000000",
      "--surface": "#0b040a",
      "--foreground": "#fbe4f1",
      "--muted-foreground": "#a06f8c",
      "--border": "#2a0c1f",
      "--primary": "#f0329b",
      "--primary-foreground": "#000000",
      "--accent": "#ff6bbd",
    },
    palette: {
      paper: "#000000",
      ink: "#fbe4f1",
      edge: "rgba(240,50,155,0.28)",
      edgeHot: "rgba(255,130,200,0.95)",
      layers: {
        evidence: "#ffd3ea",
        commerce: "#f0329b",
        product: "#ff6bbd",
        identity: "#c01a77",
        financial: "#ff9ed0",
        intelligence: "#7d0b4c",
      },
      chroma: ["#f0329b", "#ff6bbd", "#c01a77", "#ff9ed0", "#ffd3ea", "#7d0b4c"],
    },
  },
  {
    id: "cerise",
    name: "Cerise",
    hint: "Blood black · rose myelin · silver beads",
    vars: {
      "--background": "#030203",
      "--surface": "#0f070b",
      "--foreground": "#f4dfe4",
      "--muted-foreground": "#a37b85",
      "--border": "#2b1319",
      "--primary": "#d4566f",
      "--primary-foreground": "#030203",
      "--accent": "#8e2b47",
    },
    palette: {
      paper: "#030203",
      ink: "#f8ebee",
      edge: "rgba(212,86,111,0.24)",
      edgeHot: "rgba(255,215,225,0.92)",
      layers: {
        evidence: "#f8ebee",
        commerce: "#d4566f",
        product: "#a83552",
        identity: "#6d2039",
        financial: "#e9a3ae",
        intelligence: "#421324",
      },
      chroma: ["#f8ebee", "#e9a3ae", "#d4566f", "#a83552", "#6d2039", "#421324"],
    },
  },

  {
    id: "rose",
    name: "Rose Quartz",
    hint: "Petal pink · warm graphite ground",
    vars: {
      "--background": "#0b0508",
      "--surface": "#160a0f",
      "--foreground": "#fbe4ec",
      "--muted-foreground": "#b1808f",
      "--border": "#31161f",
      "--primary": "#ff8fb8",
      "--primary-foreground": "#0b0508",
      "--accent": "#ff5f9e",
    },
    palette: {
      paper: "#0b0508",
      ink: "#fbe4ec",
      edge: "rgba(255,143,184,0.22)",
      edgeHot: "rgba(255,214,231,0.9)",
      layers: {
        evidence: "#fde7f0",
        commerce: "#ff8fb8",
        product: "#ff5f9e",
        identity: "#c2477f",
        financial: "#ffc2d8",
        intelligence: "#7a2b4c",
      },
      chroma: ["#fde7f0", "#ffc2d8", "#ff8fb8", "#ff5f9e", "#c2477f", "#7a2b4c"],
    },
  },

  {
    id: "cobalt",
    name: "Cobalt",
    hint: "Deep sea navy · ice blue signal",
    vars: {
      "--background": "#03060d",
      "--surface": "#0a1120",
      "--foreground": "#dfeaff",
      "--muted-foreground": "#7f92b5",
      "--border": "#15203a",
      "--primary": "#6fa8ff",
      "--primary-foreground": "#03060d",
      "--accent": "#3c76d8",
    },
    palette: {
      paper: "#03060d",
      ink: "#dfeaff",
      edge: "rgba(111,168,255,0.2)",
      edgeHot: "rgba(212,232,255,0.92)",
      layers: {
        evidence: "#eaf3ff",
        commerce: "#6fa8ff",
        product: "#3c76d8",
        identity: "#2a4f9e",
        financial: "#a9cbff",
        intelligence: "#17305e",
      },
      chroma: ["#eaf3ff", "#a9cbff", "#6fa8ff", "#3c76d8", "#2a4f9e", "#17305e"],
    },
  },

  {
    id: "neon",
    name: "Neon",
    hint: "Void black · electric cyan and lime",
    vars: {
      "--background": "#020403",
      "--surface": "#07100d",
      "--foreground": "#e6fff6",
      "--muted-foreground": "#6f9c8f",
      "--border": "#0f2a24",
      "--primary": "#3bffd0",
      "--primary-foreground": "#020403",
      "--accent": "#c6ff4f",
    },
    palette: {
      paper: "#020403",
      ink: "#e6fff6",
      edge: "rgba(59,255,208,0.2)",
      edgeHot: "rgba(198,255,79,0.95)",
      layers: {
        evidence: "#e6fff6",
        commerce: "#3bffd0",
        product: "#c6ff4f",
        identity: "#22c1e8",
        financial: "#7dffb2",
        intelligence: "#0f6f68",
      },
      chroma: ["#e6fff6", "#3bffd0", "#7dffb2", "#c6ff4f", "#22c1e8", "#0f6f68"],
    },
  },

  {
    id: "fusion",
    name: "Fusion",
    hint: "Multi-hue spectrum · balanced ink",
    vars: {
      "--background": "#06050a",
      "--surface": "#100e18",
      "--foreground": "#f0ecf7",
      "--muted-foreground": "#8f8aa3",
      "--border": "#211d2e",
      "--primary": "#f5b83d",
      "--primary-foreground": "#06050a",
      "--accent": "#6be2c2",
    },
    palette: {
      paper: "#06050a",
      ink: "#f0ecf7",
      edge: "rgba(180,170,220,0.16)",
      edgeHot: "rgba(255,236,190,0.9)",
      layers: {
        evidence: "#f6f2ff",
        commerce: "#f5b83d",
        product: "#6be2c2",
        identity: "#7f8bff",
        financial: "#ff7a91",
        intelligence: "#b366f0",
      },
      chroma: ["#ff7a91", "#f5b83d", "#6be2c2", "#7f8bff", "#b366f0", "#f6f2ff"],
    },
  },

  {
    id: "verdant",
    name: "Verdant",
    hint: "Forest ground · chlorophyll signal",
    vars: {
      "--background": "#050805",
      "--surface": "#0c130d",
      "--foreground": "#e4f2e2",
      "--muted-foreground": "#829a83",
      "--border": "#182418",
      "--primary": "#8ede8f",
      "--primary-foreground": "#050805",
      "--accent": "#4fa96b",
    },
    palette: {
      paper: "#050805",
      ink: "#e4f2e2",
      edge: "rgba(142,222,143,0.18)",
      edgeHot: "rgba(220,248,214,0.9)",
      layers: {
        evidence: "#eef8ea",
        commerce: "#8ede8f",
        product: "#4fa96b",
        identity: "#2f7a55",
        financial: "#c8ee9b",
        intelligence: "#17452f",
      },
      chroma: ["#eef8ea", "#c8ee9b", "#8ede8f", "#4fa96b", "#2f7a55", "#17452f"],
    },
  },

  {
    id: "amethyst",
    name: "Amethyst",
    hint: "Violet dusk · orchid filaments",
    vars: {
      "--background": "#07050c",
      "--surface": "#120c1c",
      "--foreground": "#ece2fb",
      "--muted-foreground": "#9485b3",
      "--border": "#231a33",
      "--primary": "#b58cff",
      "--primary-foreground": "#07050c",
      "--accent": "#8452e0",
    },
    palette: {
      paper: "#07050c",
      ink: "#ece2fb",
      edge: "rgba(181,140,255,0.2)",
      edgeHot: "rgba(233,216,255,0.92)",
      layers: {
        evidence: "#f3ecff",
        commerce: "#b58cff",
        product: "#8452e0",
        identity: "#5c33ad",
        financial: "#d6bcff",
        intelligence: "#2d1a52",
      },
      chroma: ["#f3ecff", "#d6bcff", "#b58cff", "#8452e0", "#5c33ad", "#2d1a52"],
    },
  },

  {
    id: "gilt",
    name: "Gilt",
    hint: "Lacquer black · leaf gold",
    vars: {
      "--background": "#070604",
      "--surface": "#120f09",
      "--foreground": "#f5ead2",
      "--muted-foreground": "#a29170",
      "--border": "#241d12",
      "--primary": "#e6bf6a",
      "--primary-foreground": "#070604",
      "--accent": "#b8873a",
    },
    palette: {
      paper: "#070604",
      ink: "#f5ead2",
      edge: "rgba(230,191,106,0.18)",
      edgeHot: "rgba(255,238,199,0.92)",
      layers: {
        evidence: "#faf1dd",
        commerce: "#e6bf6a",
        product: "#b8873a",
        identity: "#8a6224",
        financial: "#f3d9a1",
        intelligence: "#4a3517",
      },
      chroma: ["#faf1dd", "#f3d9a1", "#e6bf6a", "#b8873a", "#8a6224", "#4a3517"],
    },
  },
];





/* ------------------------------------------------------------------ *
 * Graph profiles — which slice of the graph is projected
 * ------------------------------------------------------------------ */

export interface GraphProfile {
  id: string;
  name: string;
  scope: string;
  layers: LayerId[];
  relationships: string[];
  density: number;
}

/** Relationship vocabulary emitted by the live Neo4j public projection. */
export const LIVE_RELATIONSHIPS = [
  "PLACED_ON",
  "ORDERED_FROM",
  "OUTLET_OF",
  "LISTING_OF",
  "HAS_ITEM_OBSERVATION",
  "HAS_COMPONENT",
  "RECONCILED_BY",
  "EVALUATED_BY",
  "DOCUMENTED_BY",
  "RESOLVES_TO",
  "HAS_DELIVERY_MENTION",
  "USED",
  "EVIDENCED_BY",
] as const;

export const GRAPH_PROFILES: GraphProfile[] = [
  {
    id: "full",
    name: "Full Lineage",
    scope: "All six layers · traversal depth 4",
    layers: ["evidence", "commerce", "product", "identity", "financial", "intelligence"],
    relationships: [
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
      "DERIVED_FROM",
      "RECONCILES_TO",
      "CONFLICTS_WITH",
      "POSSIBLY_SAME_AS",
      "PRECEDES",
      "COMPARED_WITH",
      "SUPPORTS",
      ...LIVE_RELATIONSHIPS,
    ],
    density: 1,
  },
  {
    id: "money",
    name: "Money Trace",
    scope: "Financial components reconciled to orders",
    layers: ["commerce", "financial", "evidence"],
    relationships: [
      "HAS_LINE",
      "HAS_MONEY_COMPONENT",
      "HAS_FEE",
      "HAS_TAX",
      "HAS_PROMOTION",
      "RECONCILES_TO",
      "EVIDENCED_BY",
      "ORDERED_FROM",
      "PLACED_ON",
      "OUTLET_OF",
      "HAS_COMPONENT",
      "RECONCILED_BY",
      "EVALUATED_BY",
      "DOCUMENTED_BY",
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
      "HAS_DELIVERY_MENTION",
    ],
    density: 0.75,
  },
  {
    id: "evidence",
    name: "Evidence Spine",
    scope: "Document → page → chunk → assertion provenance",
    layers: ["evidence", "intelligence"],
    relationships: [
      "CONTAINS",
      "ASSERTS",
      "EVIDENCED_BY",
      "DERIVED_FROM",
      "SUPPORTS",
      "DOCUMENTED_BY",
      "EVALUATED_BY",
      "USED",
    ],
    density: 0.8,
  },
  {
    id: "conflict",
    name: "Conflict Surface",
    scope: "Residuals, conflicts and abstention triggers",
    layers: ["financial", "identity", "intelligence", "evidence"],
    relationships: [
      "CONFLICTS_WITH",
      "RECONCILES_TO",
      "POSSIBLY_SAME_AS",
      "EXPLAINS",
      "DERIVED_FROM",
      "RECONCILED_BY",
      "EVALUATED_BY",
    ],
    density: 0.6,
  },
  {
    id: "product",
    name: "Comparable Items",
    scope: "Item observations grouped across merchants",
    layers: ["product", "commerce", "financial"],
    relationships: [
      "HAS_ITEM",
      "COMPARED_WITH",
      "ORDERED_FROM",
      "HAS_MONEY_COMPONENT",
      "PRECEDES",
      "OUTLET_OF",
      "LISTING_OF",
      "HAS_ITEM_OBSERVATION",
    ],
    density: 0.85,
  },
];

/* ------------------------------------------------------------------ *
 * Visualization profiles — how the projection is drawn
 * ------------------------------------------------------------------ */

export type NodeMark =
  | "soma"
  | "orb"
  | "vertex"
  | "moon"
  | "burst"
  | "planet"
  | "ganglion"
  | "astro"
  | "arbor";
export type EdgeMark =
  | "dendrite"
  | "spectral"
  | "mesh"
  | "hair"
  | "filament"
  | "axon"
  | "varicose"
  | "tendril";
/** global formation the layout is pulled into */
export type Formation = "free" | "brain" | "moon" | "orbit" | "culture";


export interface VizProfile {
  id: string;
  name: string;
  hint: string;
  nodeMark: NodeMark;
  edgeMark: EdgeMark;
  /** layer = 6 semantic hues · chroma = per-node spectral index */
  colorMode: "layer" | "chroma";
  labels: "hover" | "hubs" | "all";
  particles: boolean;
  charge: number;
  linkDistance: number;
  scale: number;
  formation: Formation;
  /** how hard nodes are pulled onto the formation (0 = free) */
  formStrength: number;
  /** theme auto-selected when this style is picked (user can still override) */
  preferredTheme: string;
}

export const VIZ_PROFILES: VizProfile[] = [
  {
    id: "neuron",
    name: "Neuron",
    hint: "Somas · dendrite arbors",
    nodeMark: "soma",
    edgeMark: "dendrite",
    colorMode: "layer",
    labels: "hover",
    particles: false,
    charge: -340,
    linkDistance: 128,
    scale: 1.1,
    formation: "free",
    formStrength: 0,
    preferredTheme: "monochrome-grain",
  },
  {
    id: "chromatic",
    name: "Chromatic Web",
    hint: "Hue-indexed orbs · blended strands",
    nodeMark: "orb",
    edgeMark: "spectral",
    colorMode: "chroma",
    labels: "hubs",
    particles: false,
    charge: -330,
    linkDistance: 118,
    scale: 1.25,
    formation: "free",
    formStrength: 0,
    preferredTheme: "fusion",
  },
  {
    id: "fabric",
    name: "Space Fabric",
    hint: "Wireframe vertices · taut mesh",
    nodeMark: "vertex",
    edgeMark: "mesh",
    colorMode: "layer",
    labels: "hubs",
    particles: false,
    charge: -210,
    linkDistance: 86,
    scale: 0.92,
    formation: "free",
    formStrength: 0,
    preferredTheme: "cobalt",
  },
  {
    id: "lunar",
    name: "Lunar Phase",
    hint: "Phase-lit moons · hairline sky",
    nodeMark: "moon",
    edgeMark: "hair",
    colorMode: "layer",
    labels: "hover",
    particles: true,
    charge: -430,
    linkDistance: 190,
    scale: 1.3,
    formation: "free",
    formStrength: 0,
    preferredTheme: "eclipse",
  },
  {
    id: "nova",
    name: "Nova",
    hint: "Radial spokes · tapered filaments",
    nodeMark: "burst",
    edgeMark: "filament",
    colorMode: "chroma",
    labels: "hubs",
    particles: true,
    charge: -520,
    linkDistance: 168,
    scale: 1.12,
    formation: "free",
    formStrength: 0,
    preferredTheme: "gilt",
  },

  /* ---- formation studies ---- */
  {
    id: "cortex",
    name: "Cortex",
    hint: "Brain silhouette · dendrite arbors",
    nodeMark: "soma",
    edgeMark: "dendrite",
    colorMode: "chroma",
    labels: "hover",
    particles: false,
    charge: -80,
    linkDistance: 60,
    scale: 0.62,
    formation: "brain",
    formStrength: 0.9,
    preferredTheme: "cerise",
  },
  {
    id: "selene",
    name: "Selene",
    hint: "Crescent formation · phase-lit bodies",
    nodeMark: "moon",
    edgeMark: "hair",
    colorMode: "layer",
    labels: "hover",
    particles: true,
    charge: -70,
    linkDistance: 58,
    scale: 1.05,
    formation: "moon",
    formStrength: 0.72,
    preferredTheme: "nocturne",
  },
  {
    id: "orrery",
    name: "Orrery",
    hint: "Planets, rings and stars on orbits",
    nodeMark: "planet",
    edgeMark: "hair",
    colorMode: "chroma",
    labels: "hubs",
    particles: true,
    charge: -120,
    linkDistance: 90,
    scale: 1.45,
    formation: "orbit",
    formStrength: 0.72,
    preferredTheme: "amethyst",
  },
  {
    id: "purkinje",
    name: "Purkinje",
    hint: "Stencil somas · lacquer arbor field",
    nodeMark: "ganglion",
    edgeMark: "axon",
    colorMode: "layer",
    labels: "hover",
    particles: false,
    charge: -70,
    linkDistance: 56,
    scale: 1.12,
    formation: "culture",
    formStrength: 0.5,
    preferredTheme: "rose",
  },
  {
    id: "golgi",
    name: "Golgi Stain",
    hint: "Ramified arbors · stained tissue",
    nodeMark: "arbor",
    edgeMark: "tendril",
    colorMode: "layer",
    labels: "hover",
    particles: false,
    charge: -260,
    linkDistance: 150,
    scale: 1.0,
    formation: "free",
    formStrength: 0,
    preferredTheme: "golgi",
  },
  {
    id: "synapse",
    name: "Synapse",
    hint: "Cultured tissue · myelin beads",
    nodeMark: "astro",
    edgeMark: "varicose",
    colorMode: "chroma",
    labels: "hover",
    particles: false,
    charge: -300,
    linkDistance: 132,
    scale: 1.2,
    formation: "free",
    formStrength: 0,
    preferredTheme: "corium",
  },
];


/* ------------------------------------------------------------------ *
 * Formations — deterministic target points sampled from a silhouette
 * ------------------------------------------------------------------ */

const R = 340;

/** van der Corput radical inverse — even, deterministic point spread */
function halton(i: number, base: number) {
  let f = 1;
  let r = 0;
  let k = i + 1;
  while (k > 0) {
    f /= base;
    r += f * (k % base);
    k = Math.floor(k / base);
  }
  return r;
}

function seeded(id: string, salt: number) {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < id.length; i++) h = (h ^ id.charCodeAt(i)) * 16777619;
  h >>>= 0;
  return () => {
    h = (h * 1664525 + 1013904223) >>> 0;
    return h / 4294967296;
  };
}

/* ---------------- brain silhouette (sagittal, facing left) ----------------
 * A hand-drawn anatomical contour: frontal pole, parietal crown, occipital
 * curve, preoccipital notch, cerebellum, brain stem and temporal lobe.
 * Nodes ride the contour and a concentric inner ribbon, so the silhouette
 * reads as cortex — outline plus cortical band, never a filled blob.        */

const BRAIN: [number, number][] = [
  [-1.0, 0.02],
  [-0.97, -0.28],
  [-0.83, -0.5],
  [-0.56, -0.66],
  [-0.2, -0.74],
  [0.2, -0.68],
  [0.54, -0.5],
  [0.79, -0.22],
  [0.86, 0.06],
  [0.72, 0.19],
  [0.87, 0.33],
  [0.8, 0.55],
  [0.6, 0.66],
  [0.41, 0.57],
  [0.31, 0.73],
  [0.17, 0.88],
  [0.03, 0.84],
  [0.11, 0.6],
  [0.06, 0.43],
  [-0.16, 0.52],
  [-0.47, 0.5],
  [-0.72, 0.35],
  [-0.93, 0.16],
];

const BRAIN_CX = 0.0;
const BRAIN_CY = -0.02;

const BRAIN_SEG = (() => {
  const seg: number[] = [];
  let total = 0;
  for (let i = 0; i < BRAIN.length; i++) {
    const a = BRAIN[i]!;
    const b = BRAIN[(i + 1) % BRAIN.length]!;
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    seg.push(d);
    total += d;
  }
  return { seg, total };
})();

/** evenly spaced point along the contour, optionally shrunk toward the centroid */
function brainContour(k: number, total: number, shrink = 1) {
  const u = (k % Math.max(1, total)) / Math.max(1, total);
  let d = u * BRAIN_SEG.total;
  let i = 0;
  while (i < BRAIN_SEG.seg.length - 1 && d > BRAIN_SEG.seg[i]!) {
    d -= BRAIN_SEG.seg[i]!;
    i++;
  }
  const a = BRAIN[i]!;
  const b = BRAIN[(i + 1) % BRAIN.length]!;
  const t = d / Math.max(1e-6, BRAIN_SEG.seg[i]!);
  const px = a[0] + (b[0] - a[0]) * t;
  const py = a[1] + (b[1] - a[1]) * t;
  return {
    x: BRAIN_CX + (px - BRAIN_CX) * shrink,
    y: BRAIN_CY + (py - BRAIN_CY) * shrink,
  };
}

export function formationTargets(
  formation: Formation,
  nodes: { id: string }[],
): Map<string, { x: number; y: number }> {
  const out = new Map<string, { x: number; y: number }>();
  const n = Math.max(1, nodes.length);
  nodes.forEach((node, i) => {
    const r = seeded(node.id, formation.length * 7 + 11);
    let x = 0;
    let y = 0;
    if (formation === "brain") {
      /* three concentric bands: silhouette, cortical ribbon, deep tissue */
      const band = i % 5;
      const shrink = band < 3 ? 1 : band === 3 ? 0.72 : 0.45;
      const per = band < 3 ? Math.ceil((n * 3) / 5) : Math.ceil(n / 5);
      const k = band < 3 ? Math.floor(i / 5) * 3 + band : Math.floor(i / 5);
      const off = band === 3 ? 0.5 : band === 4 ? 1.4 : 0;
      const p = brainContour(k + off, Math.max(8, per), shrink);
      x = p.x * 1.4;
      y = p.y * 1.4;
    } else if (formation === "moon") {

      if (i % 3 === 0) {
        // outer limb
        const t = (Math.floor(i / 3) / Math.ceil(n / 3)) * Math.PI * 2;
        x = Math.cos(t) * 1.25;
        y = Math.sin(t) * 1.25;
      } else {
        for (let t = 0; t < 96; t++) {
          const px = halton(i * 47 + t, 2) * 2 - 1;
          const py = halton(i * 47 + t, 3) * 2 - 1;
          const inOuter = px * px + py * py <= 1;
          const inCut = (px - 0.42) ** 2 + (py + 0.06) ** 2 <= 0.72 ** 2;
          if (inOuter && !inCut) {
            x = px * 1.25;
            y = py * 1.25;
            break;
          }
        }
      }
    } else if (formation === "orbit") {
      const rings = 5;
      const ring = i % rings;
      const per = Math.ceil(n / rings);
      const a = ((Math.floor(i / rings) % per) / per) * Math.PI * 2 + ring * 0.7;
      const rad = 0.32 + ring * 0.2 + (r() - 0.5) * 0.045;
      x = Math.cos(a) * rad * 1.5;
      y = Math.sin(a) * rad * 0.92;
    } else if (formation === "culture") {
      /* cultured tissue field: jittered hex lattice, evenly seeded */
      const cols = Math.max(3, Math.round(Math.sqrt(n * 2.1)));
      const rows = Math.ceil(n / cols);
      const cx = i % cols;
      const cy = Math.floor(i / cols);
      const stagger = cy % 2 ? 0.5 : 0;
      x = ((cx + 0.5 + stagger) / cols - 0.5) * 2.9 + (r() - 0.5) * 0.16;
      y = ((cy + 0.5) / Math.max(1, rows) - 0.5) * 1.85 + (r() - 0.5) * 0.16;
    } else {
      return;
    }
    out.set(node.id, { x: x * R, y: y * R });
  });
  return out;
}




export const SORTS = [
  { id: "weight", name: "Centrality" },
  { id: "confidence", name: "Confidence" },
  { id: "sources", name: "Source count" },
  { id: "label", name: "Label A–Z" },
] as const;

export type SortId = (typeof SORTS)[number]["id"];

/* ------------------------------------------------------------------ *
 * Deterministic projection
 * ------------------------------------------------------------------ */

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const LAYER_TYPES: Record<LayerId, string[]> = {
  evidence: ["Document", "Page", "EvidenceChunk", "EvidenceCell", "SourceAssertion"],
  commerce: ["Order", "OrderLine", "Merchant", "Outlet", "Platform"],
  product: ["ItemObservation", "MerchantItem", "ComparableItemGroup"],
  identity: ["Alias", "LegalEntity", "DeliveryMention", "IdentityDecision"],
  financial: ["MoneyComponent", "Fee", "Tax", "Promotion", "Payment", "Reconciliation"],
  intelligence: ["Finding", "Metric", "QueryTrace", "Hypothesis", "Conclusion"],
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
      weight: hub ? 7 + r() * 5 : 1 + r() * 3,
      source_count: 1 + Math.floor(r() * 9),
      confidence: Number((0.62 + r() * 0.37).toFixed(2)),
      privacy_state: r() > 0.9 ? "redacted" : "public",
      scope: SCOPES[Math.floor(r() * SCOPES.length)]!,
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
      edges.push({
        id: `e-${i}-${k}`,
        source: node.id,
        target: target.id,
        relationship_type: profile.relationships[Math.floor(r() * profile.relationships.length)]!,
        confidence: Number((0.55 + r() * 0.44).toFixed(2)),
        provenance_label: `chunk#${1000 + Math.floor(r() * 8999)}`,
      });
    }
  });

  const metrics: Metric[] = [
    { label: "Nodes projected", value: String(nodes.length), unit: "nodes", scope: "live" },
    { label: "Edges projected", value: String(edges.length), unit: "rels", scope: "live" },
    {
      label: "Citation coverage",
      value: String(88 + Math.floor(r() * 10)),
      unit: "%",
      scope: "trailing-30d",
    },
    {
      label: "Abstention rate",
      value: String(3 + Math.floor(r() * 5)),
      unit: "%",
      scope: "trailing-30d",
    },
    { label: "Fusion channels", value: "4", unit: "exact·lex·dense·graph", scope: "live" },
  ];

  const statuses: Finding["status"][] = ["verified", "residual", "conflict", "abstained"];
  const findings: Finding[] = Array.from({ length: 5 }).map((_, i) => ({
    id: `finding-${i}`,
    title: [
      "Delivery fee drifts above merchant-declared scope",
      "Alias cluster resolves to a single legal entity",
      "Promotion applied twice on one order line",
      "Tax component missing source assertion",
      "Comparable item priced apart across platforms",
    ][i]!,
    confidence: Number((0.6 + r() * 0.39).toFixed(2)),
    status: statuses[i % statuses.length]!,
    graph_path: Array.from({ length: 3 }).map(
      () => nodes[Math.floor(r() * nodes.length)]!.label,
    ),
  }));

  return {
    metrics,
    graph_nodes: nodes,
    graph_edges: edges,
    findings,
    disclosure:
      "Public projection only. Values pass privacy validation before render; no raw documents or identifiers are exposed.",
  };
}
