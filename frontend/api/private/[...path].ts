interface VercelRequest {
  method?: string;
  query: Record<string, string | string[] | undefined>;
  body?: unknown;
  headers: Record<string, string | undefined>;
  url?: string;
}

interface VercelResponse {
  status(code: number): VercelResponse;
  json(body: unknown): void;
  setHeader(name: string, value: string): void;
  write(chunk: Uint8Array): void;
  end(): void;
}

const ALLOWED_METHODS = new Set(["GET", "POST"]);
const MAX_REQUEST_BYTES = 64 * 1024;

function reject(response: VercelResponse, status: number, message: string): void {
  response.status(status).json({ error: message });
}

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (!ALLOWED_METHODS.has(request.method ?? "")) {
    response.setHeader("Allow", "GET, POST");
    reject(response, 405, "method not allowed");
    return;
  }
  const contentLength = Number(request.headers["content-length"] ?? 0);
  if (Number.isFinite(contentLength) && contentLength > MAX_REQUEST_BYTES) {
    reject(response, 413, "request body exceeds the configured limit");
    return;
  }

  const apiOrigin = process.env.LUNARBIT_API_URL?.replace(/\/$/, "");
  const token = process.env.LUNARBIT_PRIVATE_API_TOKEN;
  if (!apiOrigin || !token) {
    reject(response, 503, "private API proxy is not configured");
    return;
  }

  const rawPath = request.query.path instanceof Array ? request.query.path.join("/") : request.query.path ?? "";
  const pathSegments = rawPath.split("/");
  if (
    pathSegments.some(
      (segment) => !segment || segment === "." || segment === ".." || !/^[A-Za-z0-9._~:%-]+$/.test(segment),
    )
  ) {
    reject(response, 400, "invalid private API path");
    return;
  }

  let target: URL;
  try {
    target = new URL(`/v1/private/${pathSegments.join("/")}`, apiOrigin);
    if (!/[a-z]+:$/i.test(target.protocol) || !["http:", "https:"].includes(target.protocol)) {
      reject(response, 503, "private API proxy is not configured");
      return;
    }
    if (request.url?.includes("?")) target.search = request.url.slice(request.url.indexOf("?"));
  } catch {
    reject(response, 503, "private API proxy is not configured");
    return;
  }

  const body = request.method === "POST" ? JSON.stringify(request.body ?? {}) : undefined;
  let upstream: globalThis.Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: {
        Accept: request.headers.accept ?? "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
      },
      body,
    });
  } catch {
    reject(response, 502, "private API is unavailable");
    return;
  }

  response.status(upstream.status);
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("Content-Type", upstream.headers.get("content-type") ?? "application/json");
  if (!upstream.body) {
    response.end();
    return;
  }
  const reader = upstream.body.getReader();
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      response.write(Buffer.from(chunk.value));
    }
  } finally {
    reader.releaseLock();
    response.end();
  }
}
