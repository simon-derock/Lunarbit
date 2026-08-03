from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from functools import partial
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.extract import build_source_inventory, write_source_inventory  # noqa: E402
from lunarbit.models import SourceDocument  # noqa: E402
from lunarbit.pdf import extract_pdf_document, write_document_artifacts  # noqa: E402


def parse_args() -> tuple[Path, Path, bool]:
    parser = ArgumentParser(description="Build Lunarbit's deterministic source inventory.")
    parser.add_argument("--input", type=Path, required=True, help="Private source archive root")
    parser.add_argument("--output", type=Path, required=True, help="Private processed output root")
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Skip page artifacts and rebuild only the source inventory",
    )
    arguments = parser.parse_args()
    return arguments.input, arguments.output, arguments.inventory_only


def _write_processed_document(
    output_root: Path,
    source: SourceDocument,
    payload: bytes,
) -> None:
    processed = extract_pdf_document(source, payload)
    write_document_artifacts(processed, payload, output_root)


def main() -> int:
    input_root, output_root, inventory_only = parse_args()
    document_handler = None if inventory_only else partial(_write_processed_document, output_root)
    inventory = build_source_inventory(input_root, document_handler=document_handler)
    write_source_inventory(inventory, output_root)
    print(json.dumps(inventory.summary.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
