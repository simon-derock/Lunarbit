export type DataProfileId = "atlas" | "meridian" | "nova" | "solstice";

export type VisualProfileId =
  | "dark-chromatic"
  | "mono-wireframe"
  | "spectral-bloom"
  | "signal-noir"
  | "economic-terrain";

export type GraphNodeKind =
  | "profile"
  | "platform"
  | "merchant"
  | "order"
  | "item"
  | "money"
  | "event"
  | "evidence";

export interface GraphNode {
  id: string;
  profileId: DataProfileId;
  kind: GraphNodeKind;
  label: string;
  detail: string;
  x: number;
  y: number;
  weight: number;
}

export interface GraphEdge {
  id: string;
  profileId: DataProfileId;
  source: string;
  target: string;
  relation: string;
}

export interface TimelinePoint {
  period: string;
  spend: number;
  fees: number;
  discount: number;
  index: number;
}

export interface CommerceDataProfile {
  id: DataProfileId;
  handle: string;
  title: string;
  archetype: string;
  disclosure: string;
  years: string;
  metrics: readonly {
    label: string;
    value: string;
    delta: string;
  }[];
  timeline: readonly TimelinePoint[];
  nodes: readonly GraphNode[];
  edges: readonly GraphEdge[];
  findings: readonly {
    tag: string;
    title: string;
    detail: string;
    confidence: string;
  }[];
  questions: readonly string[];
}

export interface VisualProfile {
  id: VisualProfileId;
  name: string;
  shortName: string;
  description: string;
  rendering: "constellation" | "wireframe" | "bloom" | "signal" | "terrain";
  palette: readonly [string, string, string, string, string];
  tokens: Readonly<Record<string, string>>;
}

export interface ProfileSelection {
  dataProfileId: DataProfileId;
  visualProfileId: VisualProfileId;
}
