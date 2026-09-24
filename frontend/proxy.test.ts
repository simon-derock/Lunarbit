import { beforeEach, describe, expect, it, vi } from "vitest";
import handler from "./api/private/[...path]";
import { createPublicProxy } from "./api/_public-proxy";

function responseDouble() {
  const response = {
    end: vi.fn(),
    json: vi.fn(),
    setHeader: vi.fn(),
    status: vi.fn().mockReturnThis(),
    write: vi.fn(),
  };
  return response;
}

describe("Vercel private API proxy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    process.env.LUNARBIT_API_URL = "https://api.example.test";
    process.env.LUNARBIT_PRIVATE_API_TOKEN = "server-secret";
  });

  it("injects the server token and streams an allowed request", async () => {
    const response = responseDouble();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("event: done\ndata: {}\n\n", {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
      ),
    );

    await handler(
      {
        method: "POST",
        query: { path: "chat/stream" },
        body: { question: "How many orders?" },
        headers: { accept: "text/event-stream" },
      } as never,
      response as never,
    );

    expect(fetch).toHaveBeenCalledWith(
      new URL("https://api.example.test/v1/private/chat/stream"),
      expect.objectContaining({
        method: "POST",
        body: '{"question":"How many orders?"}',
        headers: expect.objectContaining({ Authorization: "Bearer server-secret" }),
      }),
    );
    expect(response.status).toHaveBeenCalledWith(200);
    expect(response.write).toHaveBeenCalled();
    expect(response.end).toHaveBeenCalled();
  });

  it("rejects traversal before contacting the upstream API", async () => {
    const response = responseDouble();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await handler(
      { method: "GET", query: { path: "../admin" }, headers: {} } as never,
      response as never,
    );

    expect(response.status).toHaveBeenCalledWith(400);
    expect(response.json).toHaveBeenCalledWith({ error: "invalid private API path" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects oversized bodies before contacting the upstream API", async () => {
    const response = responseDouble();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await handler(
      {
        method: "POST",
        query: { path: "chat/stream" },
        headers: { "content-length": String(64 * 1024 + 1) },
        body: {},
      } as never,
      response as never,
    );

    expect(response.status).toHaveBeenCalledWith(413);
    expect(response.json).toHaveBeenCalledWith({
      error: "request body exceeds the configured limit",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards the bounded HITL resume route with the server token", async () => {
    const response = responseDouble();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ turn_index: 2, answer: { status: "verified" } }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await handler(
      {
        method: "POST",
        query: { path: "chat/session%3Atest/review/resume" },
        body: { turn_index: 1, decision: "approved" },
        headers: { accept: "application/json" },
      } as never,
      response as never,
    );

    expect(fetch).toHaveBeenCalledWith(
      new URL("https://api.example.test/v1/private/chat/session%3Atest/review/resume"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer server-secret" }),
      }),
    );
    expect(response.status).toHaveBeenCalledWith(200);
  });
});

describe("Vercel public API proxies", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    process.env.LUNARBIT_API_URL = "https://api.example.test";
  });

  it("forwards the public snapshot without private credentials", async () => {
    const response = responseDouble();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"mode":"neo4j_navigation_projection"}', {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await createPublicProxy("public")(
      { method: "GET", query: { path: "snapshot" }, headers: {} } as never,
      response as never,
    );

    expect(fetch).toHaveBeenCalledWith(
      new URL("https://api.example.test/v1/public/snapshot"),
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
    expect(response.status).toHaveBeenCalledWith(200);
  });

  it("forwards query plans without an authorization header", async () => {
    const response = responseDouble();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"intent":"financial_aggregation"}', {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await createPublicProxy("query")(
      {
        method: "POST",
        query: { path: "plan" },
        body: { question: "How much did I spend?" },
        headers: { accept: "application/json" },
      } as never,
      response as never,
    );

    expect(fetch).toHaveBeenCalledWith(
      new URL("https://api.example.test/v1/query/plan"),
      expect.objectContaining({
        method: "POST",
        body: '{"question":"How much did I spend?"}',
        headers: expect.not.objectContaining({ Authorization: expect.anything() }),
      }),
    );
  });

  it("rejects an unlisted public route before contacting the upstream API", async () => {
    const response = responseDouble();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await createPublicProxy("public")(
      { method: "GET", query: { path: "future-admin" }, headers: {} } as never,
      response as never,
    );

    expect(response.status).toHaveBeenCalledWith(400);
    expect(response.json).toHaveBeenCalledWith({ error: "invalid public API path" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
