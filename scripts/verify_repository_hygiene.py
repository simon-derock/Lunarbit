#!/usr/bin/env python3
"""Verify that Git tracks no private Lunarbit artifacts or local credentials."""

from __future__ import annotations

import subprocess
import sys

from lunarbit.repository_hygiene import RepositoryHygieneError, assert_repository_hygiene


def _tracked_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "ls-files", "-z"),
        capture_output=True,
        check=True,
    )
    return tuple(
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    )


def main() -> int:
    assert_repository_hygiene(_tracked_paths())
    print("repository hygiene passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RepositoryHygieneError, subprocess.CalledProcessError) as error:
        print(f"repository hygiene failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
