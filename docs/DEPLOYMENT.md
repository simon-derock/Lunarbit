# Lunarbit deployment runbook

This runbook deploys the browser projection and the authenticated GraphRAG API
without placing private documents, provider credentials, or Neo4j credentials in
the repository.

## Services

- **Neo4j AuraDB** is the canonical graph store. Use an encrypted `neo4j+s://`
  URI and the `neo4j` database (or the database selected during ingestion).
- **API service** runs `Dockerfile.api` as the unprivileged `lunarbit` user.
  Mount durable storage at `/var/lib/lunarbit`; the service writes the bounded
  conversation database and its `*.langgraph.sqlite3` checkpoint database there.
  Use encrypted persistent storage. SQLite supports a single API replica; move
  sessions to an authenticated shared store before scaling out.
- **Frontend** is the Vite application under `/frontend`. Build it with
  `npm ci && npm run build` and publish `frontend/dist` as a static site.

## API environment

Set these in the hosting provider's secret manager, never in Git:

```text
NEO4J_URI=neo4j+s://<aura-host>
NEO4J_USERNAME=<aura-user>
NEO4J_PASSWORD=<aura-password>
NEO4J_DATABASE=neo4j
COHERE_API_KEY=<server-only-key>
GEMINI_API_KEY=<server-only-key>
MISTRAL_API_KEY=<server-only-key>
LUNARBIT_PRIVATE_API_TOKEN=<random-32-plus-character-token>
LUNARBIT_PUBLIC_ALLOWED_ORIGINS=https://<frontend-host>
LUNARBIT_SESSION_DB=/var/lib/lunarbit/conversations.sqlite3
```

Start the API in production mode:

```bash
python scripts/serve_api.py --host 0.0.0.0 --port 8000 --production
```

The release probe is `GET /health`; `GET /ready` additionally verifies the
configured graph projection. The public API must return only the reviewed
projection at `GET /v1/public/snapshot`. Private chat requires the bearer token
and must not be exposed through a browser bundle.

## Frontend routing

The repository includes Vercel serverless proxies for `/api/private/*`,
`/api/public/*`, and `/api/query/*`. Configure their server environment with
`LUNARBIT_API_URL`; the private proxy additionally requires
`LUNARBIT_PRIVATE_API_TOKEN` and keeps that bearer token server-side while
streaming chat responses through to FastAPI. The public/query proxies never
forward credentials. A different host must provide equivalent same-origin
routes. Never put `LUNARBIT_PRIVATE_API_TOKEN` or provider keys in a
`VITE_*` variable: Vite embeds those values into JavaScript sent to every
visitor. Set `VITE_LUNARBIT_API_URL` only for the browser-safe public API origin.
`frontend/vercel.json` applies a restrictive CSP and standard browser security
headers; keep those headers enabled in any equivalent static-host configuration.

## Release checks

1. Run the repository CI workflow and container smoke jobs.
2. Run `scripts/verify_deployment_config.py` against the production secret set.
3. Run `scripts/verify_public_release.py --api-url <api-origin> --origin <frontend-origin>`.
4. Confirm `/health`, `/ready`, `/v1/public/snapshot`, and a browser-origin CORS
   request before enabling traffic.
5. Verify the mounted volume survives replacement and that private routes reject
   missing or invalid bearer tokens.
6. Inspect the API image as non-root and confirm it contains no private corpus
   or credential marker.
7. Record the image digest, schema/index versions, migration status, and the
   rollback image digest before promotion.

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

The narrower public-only service is documented in
[`deploy-public-api.md`](deploy-public-api.md).

## GitHub security prerequisites

Keep the repository **Dependency graph** enabled under *Settings → Security &
analysis*. The pull-request dependency-review workflow depends on that GitHub
feature; if it is disabled, the workflow reports a configuration failure even
when the dependency diff is safe. Dependabot security updates and the review
check should remain enabled for the default branch.

Do not publish `data/`, PDFs, mailboxes, processed private JSONL, `.env` files,
or generated private graph archives.
