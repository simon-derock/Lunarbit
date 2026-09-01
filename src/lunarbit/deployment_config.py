"""Fail-closed validation for production deployment environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class DeploymentConfigError(ValueError):
    """Raised when a deployment environment is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class DeploymentConfig:
    neo4j_uri: str
    database: str
    allowed_origins: tuple[str, ...]
    session_db: Path


def validate_deployment_environment(
    environment: Mapping[str, str] | None = None,
) -> DeploymentConfig:
    values = environment if environment is not None else os.environ

    def required(name: str) -> str:
        value = values.get(name, "").strip()
        if not value:
            raise DeploymentConfigError(f"{name} is required")
        return value

    uri = required("NEO4J_URI")
    if not uri.startswith("neo4j+s://"):
        raise DeploymentConfigError("NEO4J_URI must use encrypted neo4j+s:// transport")
    if not required("NEO4J_USERNAME") or not required("NEO4J_PASSWORD"):
        raise DeploymentConfigError("Neo4j credentials are required")
    if len(required("LUNARBIT_PRIVATE_API_TOKEN")) < 32:
        raise DeploymentConfigError("LUNARBIT_PRIVATE_API_TOKEN must be at least 32 characters")

    raw_origins = required("LUNARBIT_PUBLIC_ALLOWED_ORIGINS")
    origins = tuple(origin.strip().rstrip("/") for origin in raw_origins.split(","))
    if not origins or any(not origin for origin in origins):
        raise DeploymentConfigError("allowed origins cannot be empty")
    for origin in origins:
        parsed = urlparse(origin)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise DeploymentConfigError("production allowed origins must be HTTPS origins")
        if "*" in origin:
            raise DeploymentConfigError("allowed origins cannot contain wildcards")

    session_db = Path(required("LUNARBIT_SESSION_DB"))
    if not session_db.is_absolute():
        raise DeploymentConfigError("LUNARBIT_SESSION_DB must be an absolute persistent path")
    return DeploymentConfig(
        neo4j_uri=uri,
        database=required("NEO4J_DATABASE"),
        allowed_origins=origins,
        session_db=session_db,
    )
