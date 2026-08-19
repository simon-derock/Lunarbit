import type {
  CommerceDataProfile,
  DataProfileId,
  GraphEdge,
  GraphNode,
  ProfileSelection,
  VisualProfile,
  VisualProfileId,
} from "@/lib/types";

const DEFAULT_SELECTION: ProfileSelection = {
  dataProfileId: "atlas",
  visualProfileId: "dark-chromatic",
};

const node = (
  profileId: DataProfileId,
  id: string,
  kind: GraphNode["kind"],
  label: string,
  detail: string,
  x: number,
  y: number,
  weight = 1,
): GraphNode => ({
  id: `${profileId}:${id}`,
  profileId,
  kind,
  label,
  detail,
  x,
  y,
  weight,
});

const edge = (
  profileId: DataProfileId,
  id: string,
  source: string,
  target: string,
  relation: string,
): GraphEdge => ({
  id: `${profileId}:edge:${id}`,
  profileId,
  source: `${profileId}:${source}`,
  target: `${profileId}:${target}`,
  relation,
});

const graph = (profileId: DataProfileId, merchant: string, item: string) => ({
  nodes: [
    node(profileId, "self", "profile", "Commerce self", "Synthetic profile root", 50, 49, 1.6),
    node(profileId, "platform-z", "platform", "Platform Z", "Food delivery", 17, 19, 1.1),
    node(profileId, "platform-s", "platform", "Platform S", "Food + grocery", 81, 18, 1.1),
    node(profileId, "merchant", "merchant", merchant, "Reviewed public alias", 28, 48, 1.35),
    node(profileId, "order-a", "order", "Order A.24", "Reconstructed bundle", 16, 72),
    node(profileId, "order-b", "order", "Order B.91", "Mail + invoice", 76, 69),
    node(profileId, "item", "item", item, "Comparable within merchant", 49, 82, 1.25),
    node(profileId, "money", "money", "INR 468", "Scoped customer total", 66, 46, 1.2),
    node(profileId, "event", "event", "Price event", "Observed · normalized", 90, 47),
    node(profileId, "evidence-a", "evidence", "Evidence 01", "Redacted synthetic proof", 7, 46, 0.8),
    node(profileId, "evidence-b", "evidence", "Evidence 02", "Redacted synthetic proof", 93, 81, 0.8),
  ],
  edges: [
    edge(profileId, "1", "self", "platform-z", "USES"),
    edge(profileId, "2", "self", "platform-s", "USES"),
    edge(profileId, "3", "self", "merchant", "ORDERS_FROM"),
    edge(profileId, "4", "merchant", "order-a", "FULFILLED"),
    edge(profileId, "5", "merchant", "order-b", "FULFILLED"),
    edge(profileId, "6", "order-a", "item", "CONTAINS"),
    edge(profileId, "7", "order-b", "item", "CONTAINS"),
    edge(profileId, "8", "order-b", "money", "HAS_COMPONENT"),
    edge(profileId, "9", "money", "event", "ASSERTS_EVENT"),
    edge(profileId, "10", "order-a", "evidence-a", "EVIDENCED_BY"),
    edge(profileId, "11", "event", "evidence-b", "EVIDENCED_BY"),
  ],
});

const atlasGraph = graph("atlas", "Ember Kitchen", "Spiced rice bowl");
const meridianGraph = graph("meridian", "Common Table", "Family meal set");
const novaGraph = graph("nova", "Citrus Counter", "Protein grain bowl");
const solsticeGraph = graph("solstice", "Nightjar Foods", "Midnight biryani");

export const DATA_PROFILES = {
  atlas: {
    id: "atlas",
    handle: "ATLAS / 01",
    title: "Urban Omnivore",
    archetype: "Six-year cross-platform history",
    disclosure: "Synthetic mirror calibrated to Lunarbit's reviewed aggregate corpus.",
    years: "2020—2026",
    metrics: [
      { label: "Orders reconstructed", value: "454", delta: "100% evidence linked" },
      { label: "Observed spend", value: "₹186.4K", delta: "+8.2% annualized" },
      { label: "Price index", value: "128.6", delta: "+4.7 this year" },
      { label: "Fee burden", value: "6.8%", delta: "−0.9 pp vs peak" },
    ],
    timeline: [
      { period: "20", spend: 38, fees: 10, discount: 22, index: 62 },
      { period: "21", spend: 47, fees: 15, discount: 30, index: 68 },
      { period: "22", spend: 55, fees: 22, discount: 28, index: 74 },
      { period: "23", spend: 71, fees: 28, discount: 42, index: 81 },
      { period: "24", spend: 79, fees: 36, discount: 48, index: 88 },
      { period: "25", spend: 84, fees: 43, discount: 53, index: 94 },
      { period: "26", spend: 91, fees: 39, discount: 46, index: 99 },
    ],
    nodes: atlasGraph.nodes,
    edges: atlasGraph.edges,
    findings: [
      { tag: "PRICE", title: "Comparable meals rose 28.6%", detail: "Matched within reviewed merchant-item groups across 31 observations.", confidence: "0.94" },
      { tag: "FEES", title: "Fee pressure changed regime", detail: "A robust change point appears in late 2023; causal attribution is withheld.", confidence: "0.88" },
      { tag: "MIX", title: "Merchant mix offset inflation", detail: "Substitution toward lower-cost kitchens reduced the simulated total by 7.4%.", confidence: "0.82" },
    ],
    questions: [
      "What did the same biryani cost three years ago?",
      "When did fees begin rising faster than item prices?",
      "Which discounts actually offset delivery charges?",
      "Show every source behind my highest reconstructed total.",
    ],
    answers: [
      { directAnswer: "In the synthetic mirror, the reviewed Ember Kitchen rice-bowl group cost ₹320 in 2023 and ₹412 in 2026.", calculation: "₹412 − ₹320 = ₹92; matched-item increase = 28.75%.", confidenceScope: "Same reviewed merchant-item group · 31 observations", findingIndex: 0 },
      { directAnswer: "Fee pressure changes regime in late 2023, after which fees rise faster than the matched item-price signal.", calculation: "Median fee burden: 4.9% before the change point → 6.8% after; +1.9 percentage points.", confidenceScope: "Robust descriptive change point · no causal claim", findingIndex: 1 },
      { directAnswer: "Reviewed synthetic discounts total ₹14.6K against ₹9.1K of delivery and platform charges.", calculation: "₹14.6K benefits − ₹9.1K charges = ₹5.5K net scoped offset.", confidenceScope: "Promotion and membership scopes kept separate", findingIndex: 2 },
      { directAnswer: "The highest reconstructed synthetic total is ₹1,248 and resolves to both mail confirmation and invoice evidence.", calculation: "Item subtotal ₹1,156 + fees/tax ₹132 − discount ₹40 = customer total ₹1,248.", confidenceScope: "Two-source bundle · exact component reconciliation", findingIndex: 0 },
    ],
  },
  meridian: {
    id: "meridian",
    handle: "MERIDIAN / 02",
    title: "Family Planner",
    archetype: "High-basket, low-frequency household",
    disclosure: "Synthetic household profile; no private family or address data.",
    years: "2021—2026",
    metrics: [
      { label: "Orders reconstructed", value: "188", delta: "98.9% reconciled" },
      { label: "Observed spend", value: "₹142.7K", delta: "+3.1% annualized" },
      { label: "Basket median", value: "₹812", delta: "+₹94 since 2023" },
      { label: "Membership ROI", value: "1.42×", delta: "+0.18 this year" },
    ],
    timeline: [
      { period: "21", spend: 31, fees: 18, discount: 12, index: 64 },
      { period: "22", spend: 46, fees: 19, discount: 20, index: 70 },
      { period: "23", spend: 62, fees: 24, discount: 33, index: 79 },
      { period: "24", spend: 76, fees: 31, discount: 45, index: 86 },
      { period: "25", spend: 84, fees: 29, discount: 51, index: 92 },
      { period: "26", spend: 89, fees: 26, discount: 58, index: 97 },
    ],
    nodes: meridianGraph.nodes,
    edges: meridianGraph.edges,
    findings: [
      { tag: "BASKET", title: "Basket size explains 61% of change", detail: "Exact decomposition separates quantity, price, fee, tax, and residual effects.", confidence: "0.91" },
      { tag: "MEMBER", title: "Membership crossed break-even", detail: "Observed delivery benefits exceeded synthetic membership cost after order 14.", confidence: "0.96" },
      { tag: "RISK", title: "Two totals remain conflicted", detail: "Invoice and customer scopes disagree; neither is silently selected as bank truth.", confidence: "1.00" },
    ],
    questions: [
      "Did membership save more than it cost this year?",
      "How much of spending growth came from larger baskets?",
      "Which family meals remained stable after inflation?",
      "Why do two documents disagree on this order total?",
    ],
    answers: [
      { directAnswer: "Yes. Synthetic membership benefits return ₹1.42 for every ₹1.00 of membership cost this year.", calculation: "₹7,100 observed benefits ÷ ₹5,000 synthetic cost = 1.42×; net benefit ₹2,100.", confidenceScope: "Observed benefit components versus explicit synthetic cost", findingIndex: 1 },
      { directAnswer: "Larger baskets explain 61% of the reviewed spending increase.", calculation: "₹18.0K total change × 61% basket contribution = ₹10.98K.", confidenceScope: "Exact price/quantity/fee/discount decomposition", findingIndex: 0 },
      { directAnswer: "The Common Table family meal remained the most stable matched bundle, moving only 2.6% after discounts.", calculation: "Effective bundle price ₹642 → ₹659; change ₹17 / ₹642 = 2.65%.", confidenceScope: "Same merchant and reviewed bundle composition", findingIndex: 0 },
      { directAnswer: "The invoice asserts ₹812 while the customer summary asserts ₹839 because their commercial scopes differ by ₹27 of customer-facing fees.", calculation: "Customer scope ₹839 − merchant-invoice scope ₹812 = ₹27 preserved difference.", confidenceScope: "Both source assertions retained · neither treated as bank truth", findingIndex: 2 },
    ],
  },
  nova: {
    id: "nova",
    handle: "NOVA / 03",
    title: "Deal Optimizer",
    archetype: "Promotion-sensitive, high substitution",
    disclosure: "Synthetic behavioral profile; signals are descriptive, never diagnostic.",
    years: "2022—2026",
    metrics: [
      { label: "Orders reconstructed", value: "306", delta: "1,942 components" },
      { label: "Observed spend", value: "₹97.2K", delta: "−2.4% this year" },
      { label: "Discount capture", value: "17.9%", delta: "+3.2 pp vs 2024" },
      { label: "Substitution signal", value: "0.76", delta: "descriptive only" },
    ],
    timeline: [
      { period: "22", spend: 42, fees: 17, discount: 48, index: 68 },
      { period: "23", spend: 58, fees: 22, discount: 61, index: 77 },
      { period: "24", spend: 69, fees: 29, discount: 73, index: 85 },
      { period: "25", spend: 64, fees: 32, discount: 86, index: 92 },
      { period: "26", spend: 59, fees: 28, discount: 94, index: 96 },
    ],
    nodes: novaGraph.nodes,
    edges: novaGraph.edges,
    findings: [
      { tag: "PROMO", title: "Discount capture reached 17.9%", detail: "Promotion components are separated from membership benefits and refunds.", confidence: "0.98" },
      { tag: "SUB", title: "Directional substitution is visible", detail: "Higher focal prices coincide with lower focal quantity in 76% of qualifying transitions.", confidence: "0.79" },
      { tag: "SIM", title: "No-promotion scenario adds ₹11.8K", detail: "Counterfactual output is explicitly simulated and cannot overwrite observed truth.", confidence: "0.90" },
    ],
    questions: [
      "Which promotions changed what I ordered next?",
      "What would I have spent without coupons?",
      "Where did I substitute after a price rise?",
      "Which deal looked large but failed to offset fees?",
    ],
    answers: [
      { directAnswer: "In 76% of qualifying synthetic transitions, a higher focal-item price is followed by a lower-cost substitute on the next comparable order.", calculation: "19 qualifying substitution transitions ÷ 25 reviewed transitions = 0.76 directional signal.", confidenceScope: "Temporal association only · not causal elasticity", findingIndex: 1 },
      { directAnswer: "Without reviewed coupons, synthetic observed spend would rise from ₹97.2K to ₹109.0K.", calculation: "₹97.2K observed + ₹11.8K removed promotion benefit = ₹109.0K counterfactual.", confidenceScope: "Immutable bounded simulation · cannot overwrite observed truth", findingIndex: 2 },
      { directAnswer: "After the reviewed Citrus Counter bowl rose from ₹289 to ₹338, the next comparable purchase shifted to a lower-cost grain bowl.", calculation: "Focal price change ₹49 / ₹289 = 16.96%; next-basket substitution observed once.", confidenceScope: "One evidence-linked transition · descriptive only", findingIndex: 1 },
      { directAnswer: "A ₹40 headline discount failed to offset ₹56 of delivery, platform, and tax charges on the reviewed bundle.", calculation: "₹40 discount − ₹56 scoped charges = −₹16 net benefit.", confidenceScope: "Face-value promotion separated from total landed cost", findingIndex: 0 },
    ],
  },
  solstice: {
    id: "solstice",
    handle: "SOLSTICE / 04",
    title: "Night Explorer",
    archetype: "Late-hour discovery and fee exposure",
    disclosure: "Synthetic temporal profile with generalized hours and public aliases.",
    years: "2023—2026",
    metrics: [
      { label: "Orders reconstructed", value: "221", delta: "74 late-hour clusters" },
      { label: "Observed spend", value: "₹88.9K", delta: "+12.6% annualized" },
      { label: "Late-hour premium", value: "9.4%", delta: "+1.7 pp this year" },
      { label: "Anomaly events", value: "12", delta: "8 evidence resolved" },
    ],
    timeline: [
      { period: "23", spend: 36, fees: 26, discount: 19, index: 71 },
      { period: "24", spend: 55, fees: 39, discount: 28, index: 82 },
      { period: "25", spend: 74, fees: 52, discount: 35, index: 91 },
      { period: "26", spend: 88, fees: 63, discount: 31, index: 98 },
    ],
    nodes: solsticeGraph.nodes,
    edges: solsticeGraph.edges,
    findings: [
      { tag: "TIME", title: "Late-hour premium widened", detail: "Same-merchant comparisons show a 9.4% descriptive premium after 22:00.", confidence: "0.86" },
      { tag: "ANOM", title: "Twelve robust anomalies detected", detail: "Eight map to explicit fee or basket changes; four remain unexplained.", confidence: "0.93" },
      { tag: "COVER", title: "Mail-only evidence closes gaps", detail: "Attachmentless confirmations preserve four otherwise missing order events.", confidence: "1.00" },
    ],
    questions: [
      "How much extra did late-night ordering cost?",
      "Which anomalies have direct documentary explanations?",
      "Show orders reconstructed from email alone.",
      "Did the same restaurant charge differently after 10 PM?",
    ],
    answers: [
      { directAnswer: "The reviewed late-hour basket costs ₹37.79 more than its same-merchant daytime baseline in the synthetic mirror.", calculation: "₹402.00 baseline × 9.4% late-hour premium = ₹37.79; comparable total ₹439.79.", confidenceScope: "Same-merchant descriptive comparison after 22:00", findingIndex: 0 },
      { directAnswer: "Eight of twelve robust anomalies map to explicit fee or basket changes; four remain unexplained and visible.", calculation: "8 evidence-resolved / 12 detected = 66.7%; unresolved = 4.", confidenceScope: "Robust statistical flags · not fraud claims", findingIndex: 1 },
      { directAnswer: "Four representative order events are reconstructed from attachmentless confirmation mail alone.", calculation: "4 mail-only proofs → 4 provisional order bundles; zero synthetic PDFs invented.", confidenceScope: "Email evidence scope · attachment absence preserved", findingIndex: 2 },
      { directAnswer: "Yes. The reviewed Nightjar Foods basket averages ₹418 before 22:00 and ₹457 after 22:00.", calculation: "₹457 − ₹418 = ₹39; relative difference = 9.33%.", confidenceScope: "Same merchant and comparable basket · descriptive only", findingIndex: 0 },
    ],
  },
} as const satisfies Record<DataProfileId, CommerceDataProfile>;

export const VISUAL_PROFILES = {
  "dark-chromatic": {
    id: "dark-chromatic",
    name: "Dark Chromatic",
    shortName: "Chromatic",
    description: "Chrome type, spectral semantics, controlled bloom.",
    rendering: "constellation",
    palette: ["#7CF7D4", "#FF6B77", "#F5CE67", "#9C8CFF", "#68A7FF"],
    tokens: {
      "--void": "#050607",
      "--surface": "#0A0C0E",
      "--surface-high": "#111418",
      "--ink": "#F2F5F3",
      "--muted": "#858B8E",
      "--line": "rgba(229, 239, 235, 0.14)",
      "--accent": "#7CF7D4",
      "--accent-2": "#FF6B77",
      "--glow": "rgba(124, 247, 212, 0.24)",
      "--radius": "2px",
    },
  },
  "mono-wireframe": {
    id: "mono-wireframe",
    name: "Monochrome Wireframe",
    shortName: "Wireframe",
    description: "Technical-poster precision in pure black and silver.",
    rendering: "wireframe",
    palette: ["#FFFFFF", "#C6C9CA", "#939899", "#656A6C", "#34383A"],
    tokens: {
      "--void": "#020202",
      "--surface": "#070707",
      "--surface-high": "#0D0D0D",
      "--ink": "#F8F8F5",
      "--muted": "#8C8C88",
      "--line": "rgba(255, 255, 255, 0.22)",
      "--accent": "#F4F4EF",
      "--accent-2": "#969A9B",
      "--glow": "rgba(255, 255, 255, 0.16)",
      "--radius": "0px",
    },
  },
  "spectral-bloom": {
    id: "spectral-bloom",
    name: "Spectral Bloom",
    shortName: "Bloom",
    description: "Luminous clusters with fluid gradients and depth.",
    rendering: "bloom",
    palette: ["#46FFE2", "#FF4FA3", "#8E62FF", "#4F8CFF", "#FFD85A"],
    tokens: {
      "--void": "#05030A",
      "--surface": "#0C0812",
      "--surface-high": "#150E20",
      "--ink": "#FAF5FF",
      "--muted": "#988DA5",
      "--line": "rgba(215, 187, 255, 0.16)",
      "--accent": "#46FFE2",
      "--accent-2": "#FF4FA3",
      "--glow": "rgba(142, 98, 255, 0.32)",
      "--radius": "18px",
    },
  },
  "signal-noir": {
    id: "signal-noir",
    name: "Signal Noir",
    shortName: "Noir",
    description: "Hard black, forensic white, verification red.",
    rendering: "signal",
    palette: ["#FFFFFF", "#FF344D", "#BFC4C6", "#74797B", "#2F3335"],
    tokens: {
      "--void": "#000000",
      "--surface": "#080808",
      "--surface-high": "#101010",
      "--ink": "#FFFFFF",
      "--muted": "#888888",
      "--line": "rgba(255, 255, 255, 0.18)",
      "--accent": "#FF344D",
      "--accent-2": "#FFFFFF",
      "--glow": "rgba(255, 52, 77, 0.22)",
      "--radius": "0px",
    },
  },
  "economic-terrain": {
    id: "economic-terrain",
    name: "Economic Terrain",
    shortName: "Terrain",
    description: "Cartographic surfaces, cyan signals, amber findings.",
    rendering: "terrain",
    palette: ["#79E6FF", "#E9B44C", "#A9F0D1", "#B9A7FF", "#E8EDF0"],
    tokens: {
      "--void": "#030709",
      "--surface": "#071014",
      "--surface-high": "#0C181D",
      "--ink": "#EAF7F9",
      "--muted": "#789199",
      "--line": "rgba(121, 230, 255, 0.16)",
      "--accent": "#79E6FF",
      "--accent-2": "#E9B44C",
      "--glow": "rgba(121, 230, 255, 0.22)",
      "--radius": "6px",
    },
  },
} as const satisfies Record<VisualProfileId, VisualProfile>;

export const DATA_PROFILE_IDS = Object.keys(DATA_PROFILES) as DataProfileId[];
export const VISUAL_PROFILE_IDS = Object.keys(VISUAL_PROFILES) as VisualProfileId[];
export { DEFAULT_SELECTION };

export function isDataProfileId(value: string | null): value is DataProfileId {
  return value !== null && DATA_PROFILE_IDS.includes(value as DataProfileId);
}

export function isVisualProfileId(value: string | null): value is VisualProfileId {
  return value !== null && VISUAL_PROFILE_IDS.includes(value as VisualProfileId);
}

export function selectionFromSearch(search: string): ProfileSelection {
  const params = new URLSearchParams(search);
  const data = params.get("profile");
  const visual = params.get("visual");
  return {
    dataProfileId: isDataProfileId(data) ? data : DEFAULT_SELECTION.dataProfileId,
    visualProfileId: isVisualProfileId(visual) ? visual : DEFAULT_SELECTION.visualProfileId,
  };
}

export function selectionSearch(selection: ProfileSelection): string {
  const params = new URLSearchParams();
  params.set("profile", selection.dataProfileId);
  params.set("visual", selection.visualProfileId);
  return `?${params.toString()}`;
}

export function validateProfileIsolation(profile: CommerceDataProfile): void {
  const nodeIds = new Set(profile.nodes.map((value) => value.id));
  if (nodeIds.size !== profile.nodes.length) {
    throw new Error("data profile node IDs must be unique");
  }
  for (const value of profile.nodes) {
    if (value.profileId !== profile.id || !value.id.startsWith(`${profile.id}:`)) {
      throw new Error("data profile contains a foreign node");
    }
  }
  for (const value of profile.edges) {
    if (
      value.profileId !== profile.id ||
      !nodeIds.has(value.source) ||
      !nodeIds.has(value.target)
    ) {
      throw new Error("data profile contains a foreign or open edge");
    }
  }
  if (profile.answers.length !== profile.questions.length) {
    throw new Error("every reviewed question must have exactly one reviewed answer");
  }
  for (const answer of profile.answers) {
    if (!profile.findings[answer.findingIndex]) {
      throw new Error("reviewed answer references an unknown finding");
    }
  }
}

for (const profile of Object.values(DATA_PROFILES)) {
  validateProfileIsolation(profile);
}
