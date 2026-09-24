export interface PublicProxyRequest {
  method?: string;
  query: Record<string, string | string[] | undefined>;
  body?: unknown;
  headers: Record<string, string | undefined>;
  url?: string;
}

export interface PublicProxyResponse {
  status(code: number): PublicProxyResponse;
  json(body: unknown): void;
  setHeader(name: string, value: string): void;
  write(chunk: Uint8Array): void;
  end(): void;
}

const ALLOWED_METHODS = new Set(["GET", "POST"]);
const MAX_REQUEST_BYTES = 64 * 1024;

function reject(response: PublicProxyResponse, status: number, message: string): void {
  response.status(status).json({ error: message });
}

function pathSegments(request: PublicProxyRequest): string[] | null {
  const rawPath =
    request.query.path instanceof Array
      ? request.query.path.join("/")
      : request.query.path ?? "";
  const segments = rawPath.split("/");
  if (
    segments.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        !/^[A-Za-z0-9._~:%-]+$/.test(segment),
    )
  ) {
    return null;
  }
  return segments;
}

function allowedPath(namespace: "public" | "query", segments: string[]): boolean {
  if (namespace === "query") return segments.length === 1 && segments[0] === "plan";
  if (segments.length === 1) return segments[0] === "snapshot" || segments[0] === "showcase-answer";
  return (
    segments.length === 3 &&
    segments[0] === "merchant" &&
    /^pub:node:[a-j]{12}$/.test(segments[1]) &&
    segments[2] === "neighborhood"
  );
}

export function createPublicProxy(namespace: "public" | "query") {
  return async function handler(
    request: PublicProxyRequest,
    response: PublicProxyResponse,
  ): Promise<void> {
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
    if (!apiOrigin) {
      reject(response, 503, "public API proxy is not configured");
      return;
    }
    const segments = pathSegments(request);
    if (!segments || !allowedPath(namespace, segments)) {
      reject(response, 400, "invalid public API path");
      return;
    }

    let target: URL;
    try {
      target = new URL(`/v1/${namespace}/${segments.join("/")}`, apiOrigin);
      if (!["http:", "https:"].includes(target.protocol)) {
        reject(response, 503, "public API proxy is not configured");
        return;
      }
      if (request.url?.includes("?")) {
        target.search = request.url.slice(request.url.indexOf("?"));
      }
    } catch {
      reject(response, 503, "public API proxy is not configured");
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
        },
        body,
      });
    } catch {
      reject(response, 502, "public API is unavailable");
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
  };
}
