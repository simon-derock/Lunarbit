import { describe, expect, it, vi } from "vitest";
import {
  mapPublicSnapshot,
  parseSseFrame,
  streamPrivateChat,
  type PublicSnapshotPayload,
} from "./api";

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

describe("SSE protocol parser", () => {
  it("parses typed JSON events and ignores incomplete frames", () => {
    expect(parseSseFrame("event: citation\ndata: {\"citation_id\":\"runtime:citation:1\"}"))?.toEqual({
      event: "citation",
      data: { citation_id: "runtime:citation:1" },
    });
    expect(parseSseFrame("data: {}"))?.toBeNull();
    expect(parseSseFrame("event: done\ndata: {}"))?.toEqual({ event: "done", data: {} });
  });

  it("does not retry an aborted chat POST", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValue(new DOMException("cancelled", "AbortError"));
    const controller = new AbortController();

    await expect(
      streamPrivateChat("How much did I spend?", vi.fn(), vi.fn(), vi.fn(), undefined, controller.signal),
    ).rejects.toThrow("cancelled");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ signal: controller.signal });
    fetchMock.mockRestore();
  });
});
