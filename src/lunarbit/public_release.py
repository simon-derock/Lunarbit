"""Assertions for auditing a browser-facing Lunarbit deployment.

The audit deliberately validates only the public contract. It never queries a
private route successfully, accepts source material, or records API responses.
"""

from __future__ import annotations

from collections.abc import Mapping

from lunarbit.public import assert_public_payload

_REQUIRED_PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/ready",
        "/v1/public/snapshot",
        "/v1/query/plan",
        "/v1/public/showcase-answer",
        "/v1/demo/answers/{answer_key}",
    }
)

_REQUIRED_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "cross-origin-resource-policy": "same-origin",
    "referrer-policy": "no-referrer",
    "content-security-policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    "x-permitted-cross-domain-policies": "none",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


class PublicReleaseAuditError(ValueError):
    """A deployed public API does not meet Lunarbit's release boundary."""


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PublicReleaseAuditError(f"{name} must be a JSON object")
    return value


def assert_public_release(
    *,
    openapi: object,
    health: object,
    ready: object,
    snapshot: object,
    snapshot_cors_origin: str | None,
    snapshot_headers: Mapping[str, str],
    showcase: object,
    private_route_status: int,
    expected_origin: str,
) -> None:
    """Validate safe public routes, responses, and browser-origin handling."""
    openapi_payload = _mapping(openapi, name="openapi")
    paths = _mapping(openapi_payload.get("paths"), name="openapi paths")
    path_names = frozenset(str(path) for path in paths)
    if any(path.startswith("/v1/private/") for path in path_names):
        raise PublicReleaseAuditError("public release exposes a private route")
    missing = sorted(_REQUIRED_PUBLIC_PATHS - path_names)
    if missing:
        raise PublicReleaseAuditError("public release is missing required routes")

    health_payload = _mapping(health, name="health")
    if health_payload.get("status") != "ok" or health_payload.get("service") != "lunarbit-api":
        raise PublicReleaseAuditError("public health contract is not ready")
    ready_payload = _mapping(ready, name="ready")
    if ready_payload.get("status") != "ready":
        raise PublicReleaseAuditError("public readiness contract is not ready")
    if snapshot_cors_origin != expected_origin:
        raise PublicReleaseAuditError("public snapshot CORS origin is not explicitly allowed")
    headers = {key.casefold(): value for key, value in snapshot_headers.items()}
    missing_headers = sorted(
        name
        for name, expected in _REQUIRED_SECURITY_HEADERS.items()
        if headers.get(name) != expected
    )
    if missing_headers:
        raise PublicReleaseAuditError(
            "public snapshot is missing required security headers: " + ", ".join(missing_headers)
        )
    if not headers.get("x-request-id", "").startswith("trace:"):
        raise PublicReleaseAuditError("public snapshot is missing a trace request ID")
    if private_route_status != 404:
        raise PublicReleaseAuditError("public release must not mount private retrieval routes")

    snapshot_payload = _mapping(snapshot, name="snapshot")
    showcase_payload = _mapping(showcase, name="showcase")
    if showcase_payload.get("status") != "verified":
        raise PublicReleaseAuditError("reviewed showcase question did not return a verified trace")
    if not isinstance(showcase_payload.get("answer"), Mapping):
        raise PublicReleaseAuditError("verified showcase trace has no public answer")

    assert_public_payload(health_payload)
    assert_public_payload(snapshot_payload)
    assert_public_payload(showcase_payload)
