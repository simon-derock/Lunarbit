import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Vercel static security policy", () => {
  it("declares browser hardening headers without routing overrides", () => {
    const config = JSON.parse(readFileSync(new URL("./vercel.json", import.meta.url), "utf8")) as {
      headers?: Array<{ headers?: Array<{ key?: string }> }>;
      rewrites?: unknown;
    };
    const keys = config.headers?.flatMap((entry) => entry.headers?.map((header) => header.key) ?? []) ?? [];

    expect(keys).toEqual(
      expect.arrayContaining([
        "Content-Security-Policy",
        "Permissions-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
      ]),
    );
    expect(config.rewrites).toBeUndefined();
  });

  it("ships same-origin public, query, and private proxy handlers", () => {
    const routes = [
      ["./api/private/[...path].ts", "Authorization"],
      ["./api/public/[...path].ts", "createPublicProxy"],
      ["./api/query/[...path].ts", "createPublicProxy"],
    ] as const;
    for (const [route, marker] of routes) {
      expect(readFileSync(new URL(route, import.meta.url), "utf8")).toContain(marker);
    }
  });
});
