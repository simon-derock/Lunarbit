from __future__ import annotations

import re
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
        (
            "LUNARBIT_PUBLIC_ALLOWED_ORIGINS",
            "https://app.example,https://app.example",
            "duplicates",
        ),
        ("LUNARBIT_SESSION_DB", "relative.sqlite3", "absolute"),
        ("LUNARBIT_SESSION_DB", "/tmp/conversations.sqlite3", "ephemeral"),
        ("LUNARBIT_SESSION_DB", "/var/lib/lunarbit/conversations.txt", "SQLite database suffix"),
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


_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")
_PINNED_ACTION = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
_PINNED_IMAGE = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-f]{64}$")
_VERSION_COMMENT = re.compile(r"^\s+# v\d+(?:\.\d+){0,2}\s*$")


def _unpinned_action_refs(workflow: str) -> list[str]:
    """Return every external action reference that is not immutably pinned."""
    unpinned: list[str] = []
    for line in workflow.splitlines():
        match = _USES.match(line)
        if match is None:
            continue
        ref, rest = match["ref"], match["rest"]
        if ref.startswith("./"):
            continue
        if _PINNED_IMAGE.match(ref):
            continue
        if not (_PINNED_ACTION.match(ref) and _VERSION_COMMENT.match(rest)):
            unpinned.append(line.strip())
    return unpinned


@pytest.mark.parametrize(
    "line",
    (
        "      - uses: actions/checkout@v4",
        "      - uses: actions/checkout@main",
        "      - uses: actions/checkout@3d3c42e",
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # latest",
        "        uses: github/codeql-action/init@v4.38.2",
        "      - uses: docker://alpine:3.20",
    ),
)
def test_workflow_pin_audit_rejects_floating_action_refs(line: str) -> None:
    assert _unpinned_action_refs(line) == [line.strip()]


@pytest.mark.parametrize(
    "workflow",
    sorted(path.name for path in (ROOT / ".github/workflows").glob("*.y*ml")),
)
def test_workflow_actions_are_pinned_to_immutable_release_shas(workflow: str) -> None:
    text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")

    assert any(_USES.match(line) for line in text.splitlines())
    assert _unpinned_action_refs(text) == []


@pytest.mark.parametrize("dockerfile", ("Dockerfile.api", "Dockerfile.public"))
def test_api_images_pin_bases_and_keep_build_tools_out(dockerfile: str) -> None:
    text = (ROOT / dockerfile).read_text(encoding="utf-8")
    bases = [line.split()[1] for line in text.splitlines() if line.startswith("FROM ")]

    assert bases
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", base) for base in bases)
    assert "COPY --from=uv" not in text
    assert "--mount=type=cache,target=/root/.cache/uv" in text


def test_docker_build_context_excludes_local_environments() -> None:
    ignored = set((ROOT / ".dockerignore").read_text(encoding="utf-8").split())

    assert {".venv", ".claude", ".lunarbit", "**/__pycache__", "**/*.pyc", ".env.*"} <= ignored
