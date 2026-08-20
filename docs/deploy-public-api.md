# Deploying the public Lunarbit API

This service is deliberately narrower than the authenticated private runtime.
It serves the public graph projection, reviewed synthetic answer traces, and
governed query plans. It never mounts `/v1/private/*` routes.

## Build and run

The build context is denylisted by [`.dockerignore`](../.dockerignore): only
the public serving code, lockfile, and package metadata enter the image.

```sh
docker build --file Dockerfile.public --tag lunarbit-public-api .
docker run --rm --publish 8000:8000 \
  --env LUNARBIT_PUBLIC_ALLOWED_ORIGINS=https://demo.example \
  lunarbit-public-api
```

Without Neo4j configuration, the service serves the reviewed synthetic mirror.
To expose the aggregate topology, provide only a read-only Neo4j account:

```sh
docker run --rm --publish 8000:8000 \
  --env NEO4J_URI=neo4j+s://your-aura-host \
  --env NEO4J_DATABASE=neo4j \
  --env NEO4J_USERNAME=lunarbit_public_reader \
  --env NEO4J_PASSWORD=... \
  --env LUNARBIT_PUBLIC_ALLOWED_ORIGINS=https://demo.example \
  lunarbit-public-api
```

`PORT` is honoured when a service platform assigns it. The API process runs as
an unprivileged container user.

## Required safeguards

- Set `LUNARBIT_PUBLIC_ALLOWED_ORIGINS` to explicit HTTPS origins. Wildcards are
  rejected at startup.
- Do not set `COHERE_API_KEY` or `LUNARBIT_PRIVATE_API_TOKEN` on this service.
  The public launcher neither needs nor mounts the private runtime.
- Grant the Aura account read access only. The aggregate reader itself uses
  Neo4j read sessions and returns classes, relationship types, and counts only.
- Configure the Nexus Insight build with
  `VITE_API_BASE_URL=https://your-public-api.example`.

## Release checks

Before directing public traffic, verify all of the following against the
deployed origin:

```sh
curl --fail https://your-public-api.example/health
curl --fail https://your-public-api.example/v1/public/snapshot
curl --fail --request POST https://your-public-api.example/v1/public/showcase-answer \
  --header 'content-type: application/json' \
  --data '{"question":"Did discounts offset platform and delivery fees?"}'
curl --output /dev/null --write-out '%{http_code}\n' \
  --request POST https://your-public-api.example/v1/private/retrieval
```

The last command must return `404`. Review the snapshot and answer response
with the public-payload leakage tests before each new public fixture or schema
class is released.

Use the repeatable audit in the release pipeline or immediately after deployment:

```sh
uv run python scripts/verify_public_release.py \
  --api-url https://your-public-api.example \
  --origin https://your-nexus-insight.example
```

It checks the documented route surface, exact CORS origin, public-payload
validator, reviewed showcase trace, and absence of private retrieval routes. It
does not print API response bodies.
