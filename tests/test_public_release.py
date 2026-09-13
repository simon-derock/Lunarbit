from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarbit.api import create_app
from lunarbit.public_release import PublicReleaseAuditError, assert_public_release

SECURITY_HEADERS = {
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
    "x-request-id": "trace:release-test",
}


def test_public_release_audit_accepts_the_deployed_public_contract() -> None:
    client = TestClient(create_app(include_private_routes=False))
    origin = "http://127.0.0.1:5173"

    assert_public_release(
        openapi=client.get("/openapi.json").json(),
        health=client.get("/health").json(),
        ready=client.get("/ready").json(),
        snapshot=client.get("/v1/public/snapshot", headers={"Origin": origin}).json(),
        snapshot_cors_origin=client.get(
            "/v1/public/snapshot", headers={"Origin": origin}
        ).headers.get("access-control-allow-origin"),
        snapshot_headers=dict(
            client.get("/v1/public/snapshot", headers={"Origin": origin}).headers
        ),
        showcase=client.post(
            "/v1/public/showcase-answer",
            json={"question": "Did discounts offset platform and delivery fees?"},
        ).json(),
        private_route_status=client.post(
            "/v1/private/retrieval", json={"question": "historic meal price"}
        ).status_code,
        expected_origin=origin,
    )


def test_public_release_audit_rejects_private_routes_and_payload_leaks() -> None:
    with pytest.raises(PublicReleaseAuditError, match="private route"):
        assert_public_release(
            openapi={"paths": {"/health": {}, "/v1/private/retrieval": {}}},
            health={"status": "ok", "service": "lunarbit-api", "version": "1.0.0"},
            ready={"status": "ready", "graph": "configured"},
            snapshot={"mode": "synthetic_mirror"},
            snapshot_cors_origin="https://demo.example",
            snapshot_headers=SECURITY_HEADERS,
            showcase={"status": "verified", "answer": {"safe": "value"}},
            private_route_status=404,
            expected_origin="https://demo.example",
        )

    with pytest.raises(ValueError, match="public payload"):
        assert_public_release(
            openapi={
                "paths": {
                    "/health": {},
                    "/ready": {},
                    "/v1/public/snapshot": {},
                    "/v1/query/plan": {},
                    "/v1/public/showcase-answer": {},
                    "/v1/demo/answers/{answer_key}": {},
                }
            },
            health={"status": "ok", "service": "lunarbit-api", "version": "1.0.0"},
            ready={"status": "ready", "graph": "configured"},
            snapshot={"source_hash": "a" * 64},
            snapshot_cors_origin="https://demo.example",
            snapshot_headers=SECURITY_HEADERS,
            showcase={"status": "verified", "answer": {"safe": "value"}},
            private_route_status=404,
            expected_origin="https://demo.example",
        )


def test_public_release_audit_rejects_unready_graph() -> None:
    with pytest.raises(PublicReleaseAuditError, match="readiness"):
        assert_public_release(
            openapi={
                "paths": {
                    "/health": {},
                    "/ready": {},
                    "/v1/public/snapshot": {},
                    "/v1/query/plan": {},
                    "/v1/public/showcase-answer": {},
                    "/v1/demo/answers/{answer_key}": {},
                }
            },
            health={"status": "ok", "service": "lunarbit-api"},
            ready={"status": "degraded", "graph": "unavailable"},
            snapshot={"source_hash": "a" * 64},
            snapshot_cors_origin="https://demo.example",
            snapshot_headers=SECURITY_HEADERS,
            showcase={"status": "verified", "answer": {"safe": "value"}},
            private_route_status=404,
            expected_origin="https://demo.example",
        )


def test_public_release_audit_rejects_missing_browser_security_headers() -> None:
    with pytest.raises(PublicReleaseAuditError, match="security headers"):
        assert_public_release(
            openapi={
                "paths": {
                    "/health": {},
                    "/ready": {},
                    "/v1/public/snapshot": {},
                    "/v1/query/plan": {},
                    "/v1/public/showcase-answer": {},
                    "/v1/demo/answers/{answer_key}": {},
                }
            },
            health={"status": "ok", "service": "lunarbit-api"},
            ready={"status": "ready"},
            snapshot={"mode": "synthetic_mirror"},
            snapshot_cors_origin="https://demo.example",
            snapshot_headers={"x-request-id": "trace:missing-security"},
            showcase={"status": "verified", "answer": {"safe": "value"}},
            private_route_status=404,
            expected_origin="https://demo.example",
        )
