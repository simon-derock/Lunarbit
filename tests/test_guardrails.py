from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarbit.api import create_app
from lunarbit.guardrails import InMemoryRateLimiter


def test_api_rejects_wildcard_or_empty_cors_configuration() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        create_app(allowed_origins=("*",))
    with pytest.raises(ValueError, match="at least one"):
        create_app(allowed_origins=())


def test_api_sets_security_headers_and_disables_response_caching() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


def test_public_rate_limit_returns_retry_after_without_leaking_payload() -> None:
    client = TestClient(
        create_app(
            public_rate_limiter=InMemoryRateLimiter(limit=1, window_seconds=60),
        )
    )

    first = client.get("/v1/public/snapshot")
    limited = client.get("/v1/public/snapshot")

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert limited.json() == {"detail": "request rate limit exceeded"}
