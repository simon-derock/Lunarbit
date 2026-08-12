#!/usr/bin/env python3
"""Evaluate governed Neo4j answers against private canonical-oracle goldens."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from lunarbit.agentic import _atomic_private_write
from lunarbit.answer_evaluation import AnswerGolden, evaluate_grounded_answers
from lunarbit.runtime import Neo4jGraphReader
from lunarbit.service import GovernedAnswerBackend


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldens", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--database", default="neo4j")
    return parser.parse_args()


def main() -> int:
    args = _args()
    goldens = tuple(
        AnswerGolden.model_validate_json(line)
        for line in args.goldens.read_text(encoding="utf-8").splitlines()
        if line
    )
    reader = Neo4jGraphReader.connect(args.uri, database=args.database)
    try:
        backend = GovernedAnswerBackend(reader)
        report = evaluate_grounded_answers(goldens, backend.answer)
    finally:
        reader.close()
    content = (report.model_dump_json() + "\n").encode()
    _atomic_private_write(args.output, content)
    summary = report.summary.model_dump(mode="json")
    print(
        json.dumps(
            {
                "evaluation_version": report.evaluation_version,
                "report_sha256": sha256(content).hexdigest(),
                "summary": summary,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
