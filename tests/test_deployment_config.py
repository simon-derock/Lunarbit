from __future__ import annotations

from pathlib import Path

import pytest

from lunarbit.deployment_config import DeploymentConfigError, validate_deployment_environment

ROOT = Path(__file__).resolve().parents[1]


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
        "NEO4J_USERNAME": "reader",
        "NEO4J_PASSWORD": "password",
        "NEO4J_DATABASE": "neo4j",
        "LUNARBIT_PRIVATE_API_TOKEN": "x" * 32,
        "LUNARBIT_PUBLIC_ALLOWED_ORIGINS": "https://app.example",
        "LUNARBIT_SESSION_DB": "/var/lib/lunarbit/conversations.sqlite3",
    }
    values.update(overrides)
    return values


def test_production_environment_returns_safe_typed_config() -> None:
    config = validate_deployment_environment(_environment())
    assert config.neo4j_uri.startswith("neo4j+s://")
    assert config.allowed_origins == ("https://app.example",)
    assert config.session_db.is_absolute()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("NEO4J_URI", "bolt://example", "encrypted"),
        ("LUNARBIT_PRIVATE_API_TOKEN", "short", "32 characters"),
        ("LUNARBIT_PUBLIC_ALLOWED_ORIGINS", "*", "HTTPS origins"),
        ("LUNARBIT_PUBLIC_ALLOWED_ORIGINS", "https://app.example/?next=home", "HTTPS origins"),
        ("LUNARBIT_SESSION_DB", "relative.sqlite3", "absolute"),
    ),
)
def test_production_environment_fails_closed(name: str, value: str, message: str) -> None:
    with pytest.raises(DeploymentConfigError, match=message):
        validate_deployment_environment(_environment(**{name: value}))


@pytest.mark.parametrize("dockerfile", ("Dockerfile.api", "Dockerfile.public"))
def test_api_images_declare_a_local_health_contract(dockerfile: str) -> None:
    contents = (ROOT / dockerfile).read_text(encoding="utf-8")

    assert "HEALTHCHECK" in contents
    assert "http://127.0.0.1:8000/health" in contents
    assert "timeout=3" in contents


def test_api_image_provisions_the_non_root_session_directory() -> None:
    contents = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert "mkdir -p /var/lib/lunarbit" in contents
    assert "chown lunarbit:lunarbit /var/lib/lunarbit" in contents
    assert 'VOLUME ["/var/lib/lunarbit"]' in contents


def test_public_container_ci_supplies_the_live_graph_boundary() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "image: neo4j:5.26-community" in workflow
    assert "--env NEO4J_URI=bolt://127.0.0.1:7687" in workflow
    assert "--api-url http://127.0.0.1:8000" in workflow


def test_ci_explicitly_loads_timeout_plugin_when_autoload_is_disabled() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"' in workflow
    assert "pytest -p pytest_timeout" in workflow
