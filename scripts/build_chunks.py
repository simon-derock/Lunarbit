from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.chunk import build_chunk_archive  # noqa: E402


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Build deterministic rich evidence chunks from Phase 1 artifacts."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Private Phase 1 processed archive root",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Bounded concurrent chunk builders; preserve deterministic write ordering",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_chunk_archive(args.input, workers=args.workers)
    print(json.dumps(summary.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
