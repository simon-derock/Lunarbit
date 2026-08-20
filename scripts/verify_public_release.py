#!/usr/bin/env python3
"""Audit a deployed Lunarbit public API without reading or printing its data."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lunarbit.public_release import PublicReleaseAuditError, assert_public_release


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True, help="deployed public FastAPI origin")
    parser.add_argument("--origin", required=True, help="deployed Nexus Insight browser origin")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: Mapping[str, object] | None = None,
    origin: str | None = None,
    timeout: float,
) -> tuple[int, Mapping[str, object] | None, str | None]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if origin is not None:
        headers["Origin"] = origin
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            decoded: object = json.loads(raw) if raw else None
            if decoded is not None and not isinstance(decoded, Mapping):
                raise PublicReleaseAuditError("public API returned a non-object JSON payload")
            return (
                response.status,
                decoded,
                response.headers.get("Access-Control-Allow-Origin"),
            )
    except HTTPError as error:
        return error.code, None, error.headers.get("Access-Control-Allow-Origin")


def _required_json(
    response: tuple[int, Mapping[str, object] | None, str | None],
) -> Mapping[str, object]:
    status, payload, _ = response
    if status != 200 or payload is None:
        raise PublicReleaseAuditError("public API did not return a required 200 JSON response")
    return payload


def main() -> int:
    args = _args()
    if not 1 <= args.timeout <= 60:
        raise ValueError("timeout must be between 1 and 60 seconds")
    api_url = args.api_url.rstrip("/")
    if not api_url.startswith(("https://", "http://")):
        raise ValueError("api-url must include an http or https scheme")

    openapi = _required_json(_request(f"{api_url}/openapi.json", timeout=args.timeout))
    health = _required_json(_request(f"{api_url}/health", timeout=args.timeout))
    snapshot_status, snapshot, snapshot_cors_origin = _request(
        f"{api_url}/v1/public/snapshot",
        origin=args.origin,
        timeout=args.timeout,
    )
    if snapshot_status != 200 or snapshot is None:
        raise PublicReleaseAuditError("public API did not return a public snapshot")
    showcase = _required_json(
        _request(
            f"{api_url}/v1/public/showcase-answer",
            method="POST",
            payload={"question": "Did discounts offset platform and delivery fees?"},
            timeout=args.timeout,
        )
    )
    private_status, _, _ = _request(
        f"{api_url}/v1/private/retrieval",
        method="POST",
        payload={"question": "historic meal price"},
        timeout=args.timeout,
    )
    assert_public_release(
        openapi=openapi,
        health=health,
        snapshot=snapshot,
        snapshot_cors_origin=snapshot_cors_origin,
        showcase=showcase,
        private_route_status=private_status,
        expected_origin=args.origin,
    )
    print("public release audit passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, PublicReleaseAuditError) as error:
        print(f"public release audit failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
