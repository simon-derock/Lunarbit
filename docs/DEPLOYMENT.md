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

The repository includes a Vercel serverless proxy at
`frontend/api/private/[...path].ts` for `/api/private/*`. Configure its server
environment with `LUNARBIT_API_URL` and `LUNARBIT_PRIVATE_API_TOKEN`; it keeps
the bearer token server-side and streams chat responses through to FastAPI. A
different host must provide an equivalent same-origin reverse proxy. Never put
`LUNARBIT_PRIVATE_API_TOKEN` or provider keys in a
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

Do not publish `data/`, PDFs, mailboxes, processed private JSONL, `.env` files,
or generated private graph archives.
