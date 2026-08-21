"""Repository-level guardrails for Lunarbit's public source boundary."""

from __future__ import annotations

from collections.abc import Iterable

_APPROVED_DATA_PATHS = frozenset({"data/public/README.md", "data/evals/README.md"})
_PRIVATE_SUFFIXES = (".eml", ".key", ".mbox", ".pdf", ".pem", ".zip")


class RepositoryHygieneError(ValueError):
    """A path prohibited by the public repository boundary is tracked."""


def _normalized(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def prohibited_tracked_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Return prohibited tracked paths without revealing their contents."""
    prohibited: set[str] = set()
    for path in paths:
        normalized = _normalized(path)
        filename = normalized.rsplit("/", maxsplit=1)[-1]
        if normalized.startswith("data/") and normalized not in _APPROVED_DATA_PATHS:
            prohibited.add(normalized)
            continue
        if normalized.casefold().endswith(tuple(_PRIVATE_SUFFIXES)):
            prohibited.add(normalized)
            continue
        if filename != ".env.example" and (filename == ".env" or filename.startswith(".env.")):
            prohibited.add(normalized)
    return tuple(sorted(prohibited))


def assert_repository_hygiene(paths: Iterable[str]) -> None:
    """Raise a content-safe error when prohibited files are tracked."""
    prohibited = prohibited_tracked_paths(paths)
    if prohibited:
        raise RepositoryHygieneError(
            f"repository contains {len(prohibited)} prohibited tracked artifact(s)"
        )
