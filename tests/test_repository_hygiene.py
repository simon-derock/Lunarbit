from __future__ import annotations

import pytest

from lunarbit.repository_hygiene import (
    RepositoryHygieneError,
    assert_repository_hygiene,
    prohibited_tracked_paths,
)


def test_repository_hygiene_allows_only_reviewed_data_entrypoints() -> None:
    assert prohibited_tracked_paths(
        (
            "README.md",
            "MEMORY.md",
            ".env.example",
            "data/public/README.md",
            "data/evals/README.md",
        )
    ) == ()


def test_repository_hygiene_rejects_private_artifacts_and_configuration() -> None:
    prohibited = prohibited_tracked_paths(
        (
            "data/processed/order-1.json",
            "private/receipt.pdf",
            "mail/order.eml",
            "archive/mailbox.mbox",
            "exports/takeout.zip",
            ".env.production",
        )
    )

    assert prohibited == (
        ".env.production",
        "archive/mailbox.mbox",
        "data/processed/order-1.json",
        "exports/takeout.zip",
        "mail/order.eml",
        "private/receipt.pdf",
    )
    with pytest.raises(RepositoryHygieneError, match="6 prohibited"):
        assert_repository_hygiene(prohibited)
