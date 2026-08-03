from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.chunk import build_chunk_archive  # noqa: E402


def parse_args() -> Path:
    parser = ArgumentParser(
        description="Build deterministic rich evidence chunks from Phase 1 artifacts."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Private Phase 1 processed archive root",
    )
    return Path(parser.parse_args().input)


def main() -> int:
    summary = build_chunk_archive(parse_args())
    print(json.dumps(summary.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
