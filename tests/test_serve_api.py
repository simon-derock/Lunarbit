from __future__ import annotations

import pytest

from scripts.serve_api import _neo4j_auth, _session_database_path


def test_neo4j_auth_requires_a_complete_credential_pair() -> None:
    assert _neo4j_auth(None, None) is None
    assert _neo4j_auth("neo4j", "secret") == ("neo4j", "secret")


@pytest.mark.parametrize(
    ("username", "password"),
    (("neo4j", None), (None, "secret")),
)
def test_neo4j_auth_rejects_partial_credentials(
    username: str | None,
    password: str | None,
) -> None:
    with pytest.raises(ValueError, match="supplied together"):
        _neo4j_auth(username, password)


def test_local_launcher_falls_back_from_container_session_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUNARBIT_SESSION_DB", "/var/lib/lunarbit/conversations.sqlite3")

    path = _session_database_path(None)

    assert path is not None
    assert path.resolve() == tmp_path / ".lunarbit/conversations.sqlite3"
    assert path.parent.is_dir()
