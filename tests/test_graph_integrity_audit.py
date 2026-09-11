from __future__ import annotations

from scripts.audit_graph_integrity import AUDITS, run_audits


class _Record:
    def __init__(self, count: int) -> None:
        self._count = count

    def __getitem__(self, key: str) -> int:
        assert key == "count"
        return self._count


class _Result:
    def __init__(self, count: int) -> None:
        self._count = count

    def single(self, *, strict: bool) -> _Record:
        assert strict
        return _Record(self._count)


class _Session:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def run(self, query: str) -> _Result:
        self.queries.append(query)
        return _Result(3)


def test_integrity_audits_are_read_only_and_return_all_checks() -> None:
    session = _Session()
    result = run_audits(session)

    assert result == {name: 3 for name in AUDITS}
    assert len(session.queries) == len(AUDITS)
    assert all(
        not any(keyword in query.upper() for keyword in ("CREATE", "MERGE", "DELETE", "SET"))
        for query in session.queries
    )
