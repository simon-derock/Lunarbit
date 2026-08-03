from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from subprocess import run

from lunarbit.models import OrderCategory, Platform, SourceMessage

PRIVATE_SUFFIXES = {".eml", ".mbox", ".pdf", ".zip"}


def test_repository_tracks_no_private_source_formats() -> None:
    result = run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [Path(value) for value in result.stdout.splitlines()]

    assert not [path for path in tracked if path.suffix.lower() in PRIVATE_SUFFIXES]


def test_private_source_patterns_are_ignored_by_default() -> None:
    ignore_file = Path(".gitignore").read_text(encoding="utf-8")

    assert "/data/**" in ignore_file
    assert "*.pdf" in ignore_file
    assert "*.mbox" in ignore_file
    assert "*.eml" in ignore_file
    assert "*.zip" in ignore_file


def test_source_message_repr_hides_private_values() -> None:
    message = SourceMessage(
        message_id="msg_0123456789abcdef",
        raw_sha256="0" * 64,
        platform=Platform.ZOMATO,
        category=OrderCategory.FOOD,
        occurred_at=datetime(2026, 8, 3, tzinfo=UTC),
        subject_private="Private restaurant and order subject",
        sender_private="customer@example.com",
        source_locator_private="data/private/message.eml",
        attachment_document_ids=("doc_0123456789abcdef",),
    )

    rendered = repr(message)

    assert "Private restaurant" not in rendered
    assert "customer@example.com" not in rendered
    assert "data/private" not in rendered
