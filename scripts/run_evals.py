from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.chunk import evaluate_chunk_archive  # noqa: E402


def parse_args() -> tuple[str, Path]:
    parser = ArgumentParser(description="Run Lunarbit's deterministic regression suites.")
    parser.add_argument("--suite", choices=("chunking",), required=True)
    parser.add_argument("--input", type=Path, required=True, help="Private processed archive root")
    arguments = parser.parse_args()
    return str(arguments.suite), Path(arguments.input)


def main() -> int:
    suite, input_root = parse_args()
    if suite != "chunking":
        raise ValueError("unsupported evaluation suite")
    summary = evaluate_chunk_archive(input_root)
    print(json.dumps(summary.model_dump(mode="json"), indent=2))
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
