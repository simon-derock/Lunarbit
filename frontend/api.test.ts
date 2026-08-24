import { describe, expect, it } from "vitest";
import { mapPublicSnapshot, type PublicSnapshotPayload } from "./api";

const payload: PublicSnapshotPayload = {
  mode: "neo4j_aggregate_projection",
  disclosure: "Aggregate-only public projection.",
  metrics: [{ label: "Orders reconstructed", value: "454", detail: null }],
  sample_questions: Array.from({ length: 10 }, (_, index) => `Question ${index + 1}`),
  nodes: [
    {
      id: "pub:merchant:ember",
      label: "Merchant",
      title: "Ember Kitchen",
      subtitle: "Public alias",
      properties: { confidence: 0.99 },
    },
    {
      id: "pub:order:alpha",
      label: "Order",
      title: "Order Alpha",
      subtitle: "Aggregate order",
      properties: {},
    },
  ],
  edges: [
    {
      id: "pub:edge:1",
      source: "pub:order:alpha",
      target: "pub:merchant:ember",
      relationship: "ORDERED_FROM",
      properties: {},
    },
  ],
};

describe("public snapshot adapter", () => {
  it("maps the privacy-safe API DTO into the graph data frame", () => {
    const snapshot = mapPublicSnapshot(payload);
    expect(snapshot.graph_nodes).toHaveLength(2);
    expect(snapshot.graph_nodes[0]?.layer).toBe("commerce");
    expect(snapshot.graph_edges[0]?.relationship_type).toBe("ORDERED_FROM");
    expect(snapshot.metrics[0]?.scope).toBe("neo4j_aggregate_projection");
    expect(snapshot.findings).toHaveLength(6);
  });
});
