import { describe, expect, it, vi } from "vitest";
import {
  fetchPublicSnapshot,
  mapPublicSnapshot,
  parseSseFrame,
  streamPrivateChat,
  type PublicSnapshotPayload,
  type StreamAnswer,
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

  it("retries a transient public projection failure before succeeding", async () => {
    vi.stubGlobal("window", { setTimeout });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("temporarily unavailable", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );

    try {
      const result = await fetchPublicSnapshot();
      expect(result.mode).toBe("neo4j_aggregate_projection");
      expect(fetchMock).toHaveBeenCalledTimes(2);
    } finally {
      fetchMock.mockRestore();
      vi.unstubAllGlobals();
    }
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

  it("reassembles split SSE frames and delivers the complete answer contract", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('event: thinking\ndata: {"stage":"retrieval"}\n\n'));
        const answer = JSON.stringify({
          session_id: "session:test",
          turn_index: 1,
          context_reused: false,
          answer: {
            status: "verified",
            direct_answer: "You placed 4 orders.",
            calculation: null,
            fact_count: 4,
            citation_ids: ["runtime:citation:1"],
            citations: [],
            verification_status: "verified",
            limitations: [],
            abstention_reason: null,
            review_required: true,
            review_reason: "identity_ambiguity",
          },
        });
        const frame = `event: answer\ndata: ${answer}\n\nevent: done\ndata: {}\n\n`;
        const bytes = encoder.encode(frame);
        controller.enqueue(bytes.slice(0, 17));
        controller.enqueue(bytes.slice(17));
        controller.close();
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );
    const stages: string[] = [];
    const result = await streamPrivateChat(
      "How many orders did I place?",
      (stage) => stages.push(stage),
      vi.fn(),
      vi.fn(),
    );

    expect(result.answer.direct_answer).toBe("You placed 4 orders.");
    expect(result.answer.review_required).toBe(true);
    expect(result.answer.review_reason).toBe("identity_ambiguity");
    expect(stages).toEqual(["retrieval"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
    fetchMock.mockRestore();
  });

  it("delivers streamed citations and graph focus before the final answer", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(
          encoder.encode(
            'event: citation\ndata: {"citation_id":"runtime:citation:1","chunk_node_id":"chunk:1","source_node_id":"source:1","authority_score":0.98,"supports_claim_ids":["claim:1"],"quality_flags":[]}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode('event: graph_focus\ndata: {"node_ids":["pub:order:alpha","pub:merchant:ember"]}\n\n'),
        );
        controller.enqueue(
          encoder.encode(
            'event: answer\ndata: {"session_id":"session:test","turn_index":2,"context_reused":true,"answer":{"status":"verified","direct_answer":"Four orders.","calculation":null,"fact_count":4,"citation_ids":["runtime:citation:1"],"citations":[],"verification_status":"verified","limitations":[],"abstention_reason":null,"review_required":false,"review_reason":null}}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );
    const citations: StreamAnswer["citations"] = [];
    const focus: string[][] = [];
    const lifecycle: string[] = [];

    const result = await streamPrivateChat(
      "How many orders did I place?",
      vi.fn(),
      (citation) => {
        lifecycle.push("citation");
        citations.push(citation);
      },
      (nodeIds) => {
        lifecycle.push("graph_focus");
        focus.push(nodeIds);
      },
    );

    expect(citations).toHaveLength(1);
    expect(citations[0]?.citation_id).toBe("runtime:citation:1");
    expect(focus).toEqual([["pub:order:alpha", "pub:merchant:ember"]]);
    expect(result.context_reused).toBe(true);
    expect(lifecycle).toEqual(["citation", "graph_focus"]);
    fetchMock.mockRestore();
  });

  it("fails closed when a stream ends before an answer event", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: thinking\ndata: {"stage":"retrieval"}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    await expect(streamPrivateChat("Show my orders", vi.fn(), vi.fn(), vi.fn())).rejects.toThrow(
      "chat stream ended without an answer",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock.mockRestore();
  });

  it("fails closed when the server emits a typed error event", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode('event: error\ndata: {"code":"answer_unavailable"}\n\n'),
        );
        controller.close();
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    await expect(streamPrivateChat("Show my orders", vi.fn(), vi.fn(), vi.fn())).rejects.toThrow(
      "answer_unavailable",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock.mockRestore();
  });
});
