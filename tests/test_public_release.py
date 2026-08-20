from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarbit.api import create_app
from lunarbit.public_release import PublicReleaseAuditError, assert_public_release


def test_public_release_audit_accepts_the_deployed_public_contract() -> None:
    client = TestClient(create_app(include_private_routes=False))
    origin = "http://127.0.0.1:5173"

    assert_public_release(
        openapi=client.get("/openapi.json").json(),
        health=client.get("/health").json(),
        snapshot=client.get("/v1/public/snapshot", headers={"Origin": origin}).json(),
        snapshot_cors_origin=client.get(
            "/v1/public/snapshot", headers={"Origin": origin}
        ).headers.get("access-control-allow-origin"),
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
            snapshot={"mode": "synthetic_mirror"},
            snapshot_cors_origin="https://demo.example",
            showcase={"status": "verified"},
            private_route_status=404,
            expected_origin="https://demo.example",
        )

    with pytest.raises(ValueError, match="public payload"):
        assert_public_release(
            openapi={
                "paths": {
                    "/health": {},
                    "/v1/public/snapshot": {},
                    "/v1/query/plan": {},
                    "/v1/public/showcase-answer": {},
                    "/v1/demo/answers/{answer_key}": {},
                }
            },
            health={"status": "ok", "service": "lunarbit-api", "version": "1.0.0"},
            snapshot={"source_hash": "a" * 64},
            snapshot_cors_origin="https://demo.example",
            showcase={"status": "verified"},
            private_route_status=404,
            expected_origin="https://demo.example",
        )
