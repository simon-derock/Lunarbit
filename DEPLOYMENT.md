# Lunarbit production deployment contract

This runbook describes the minimum safe deployment for the Aura-backed API and
the static frontend. It is an operational contract, not a substitute for a
provider's secret manager or network policy.

## Services

- `Dockerfile.api` runs FastAPI on port `8000` as the unprivileged `lunarbit`
  user.
- The frontend is built with `npm run build` and served by a static host or
  reverse proxy.
- The reverse proxy terminates HTTPS and forwards `/api/*` to FastAPI. The
  browser must never connect directly to Neo4j, Cohere, Gemini, or Mistral.

## Required runtime secrets

Provide these through the platform secret manager, never through Git, image
layers, frontend build variables, or chat messages:

```text
NEO4J_URI=neo4j+s://...
NEO4J_USERNAME=<least-privilege-read-user>
NEO4J_PASSWORD=<rotated-secret>
NEO4J_DATABASE=<database>
COHERE_API_KEY=<rotated-secret>
GEMINI_API_KEY=<rotated-secret>
MISTRAL_API_KEY=<rotated-secret>
LUNARBIT_PRIVATE_API_TOKEN=<high-entropy-token>
LUNARBIT_SESSION_DB=/var/lib/lunarbit/conversations.sqlite3
LUNARBIT_PUBLIC_ALLOWED_ORIGINS=https://app.example
```

Mount the session database on encrypted persistent storage. For multiple API
replicas, replace SQLite with an authenticated shared store before scaling out.

## Release gates

1. Run Python tests, Ruff, strict MyPy, repository hygiene, frontend Vitest,
   TypeScript, and production build.
2. Build `Dockerfile.api`; inspect the image as non-root and confirm no private
   corpus or credential marker is present.
3. Start a release candidate with deployment secrets and require `/health`
   plus `/ready` before routing traffic.
4. Verify the public snapshot contains only the reviewed projection and that
   authenticated SSE chat returns typed events without raw evidence.
5. Record image digest, schema/index versions, migration status, and rollback
   image before promotion.

## Security controls

- HTTPS-only ingress with HSTS; explicit CORS origins, never `*`.
- Rotate API tokens and provider credentials; revoke the previous value after
  a successful rollout.
- Use a Neo4j read-only account for query traffic and separate ingestion
  credentials; enforce encrypted Aura connections.
- Keep request, traversal, row, action, session, and rate limits enabled.
- Redact questions, answers, evidence, tokens, Cypher, and provider payloads
  from logs and traces.
- Enable dependency/image scanning, alerting on readiness failures, and
  encrypted backups with a tested restore procedure.
- Roll back by image digest, not by rebuilding from an unpinned dependency
  range.
