from argparse import Namespace

import pytest

from scripts.ingest_graph import _connection_config


def test_connection_config_reads_aura_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_DATABASE", "lunarbit")
    monkeypatch.setenv("NEO4J_USERNAME", "lunarbit")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")

    args = Namespace(uri=None, database=None, username=None, password=None)
    uri, database, auth = _connection_config(args)

    assert (uri, database, auth) == (
        "neo4j+s://example.databases.neo4j.io",
        "lunarbit",
        ("lunarbit", "secret"),
    )


def test_connection_config_rejects_partial_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_USERNAME", "lunarbit")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="supplied together"):
        _connection_config(Namespace(uri=None, database=None, username=None, password=None))
