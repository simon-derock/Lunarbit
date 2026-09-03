import { beforeEach, describe, expect, it, vi } from "vitest";
import handler from "./api/private/[...path]";

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
});
