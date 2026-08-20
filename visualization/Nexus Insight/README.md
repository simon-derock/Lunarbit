# Lunarbit Nexus Insight

Nexus Insight is the interactive, privacy-safe topology view for Lunarbit. It
does not connect to Neo4j or private data from the browser. Its only data
boundary is the public FastAPI contract.

## Runtime boundary

```text
Nexus Insight (React) → FastAPI public projection → Neo4j aggregate reader
                                              └→ private GraphRAG runtime (authenticated only)
```

`GET /v1/public/snapshot` contains reviewed/synthetic data or a live aggregate
topology. A live topology exposes only graph classes, relationship types, and
counts—never canonical IDs, node properties, source text, emails, order IDs,
or credentials. `POST /v1/public/showcase-answer` returns only a reviewed,
synthetic calculation + graph path + evidence trace or an explicit abstention;
it never runs private retrieval. `POST /v1/query/plan` remains available for
inspection of the governed traversal plan only.

## Local development

From the repository root, start the public-only API:

```sh
uv run python scripts/serve_public_api.py
```

This launcher deliberately omits the private GraphRAG endpoints. Set
`NEO4J_URI` (plus read-only Neo4j credentials) for the live aggregate projection;
without it, the API serves the reviewed synthetic mirror. For a deployed browser
origin, set the explicit comma-separated `LUNARBIT_PUBLIC_ALLOWED_ORIGINS` value.

Then start this application:

```sh
npm install
npm run dev
```

In development, Nexus calls `http://127.0.0.1:8000` directly; FastAPI allows
the local Vite origin. For deployment, set `VITE_API_BASE_URL` to the public
FastAPI origin, or route `/api` to that service at the deployment edge.

## Verification

```sh
npm run build
npm run lint
```

The graph uses semantic glyphs by class and relationship-aware arrows. Aggregate
relationship counts influence edge weight without exposing individual records.
