#!/usr/bin/env python3
"""Validate production environment configuration without exposing secrets."""

from __future__ import annotations

import sys

from lunarbit.deployment_config import DeploymentConfigError, validate_deployment_environment


def main() -> int:
    validate_deployment_environment()
    print("deployment configuration passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeploymentConfigError as error:
        print(f"deployment configuration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
