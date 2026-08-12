#!/usr/bin/env python3
"""Build private answer goldens from canonical archives, independently of Neo4j."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from lunarbit.agentic import _atomic_private_write
from lunarbit.answer_goldens import (
    ANSWER_GOLDEN_POLICY_VERSION,
    build_canonical_answer_goldens,
)
from lunarbit.finance import MoneyComponent
from lunarbit.graph import CanonicalGraph, GraphNode, GraphRelationship
from lunarbit.models import SourceMessage


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path, required=True)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases-per-entity-family", type=int, default=5)
    return parser.parse_args()


def _read[T: BaseModel](path: Path, model: type[T]) -> tuple[T, ...]:
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def main() -> int:
    args = _args()
    messages = _read(args.inventory_root / "source_messages.jsonl", SourceMessage)
    components = _read(args.finance_root / "money_components.jsonl", MoneyComponent)
    graph = CanonicalGraph(
        nodes=_read(args.graph_root / "nodes.jsonl", GraphNode),
        relationships=_read(
            args.graph_root / "relationships.jsonl",
            GraphRelationship,
        ),
    )
    goldens = build_canonical_answer_goldens(
        messages,
        components,
        graph,
        cases_per_entity_family=args.cases_per_entity_family,
    )
    content = ("\n".join(value.model_dump_json() for value in goldens) + "\n").encode()
    digest = sha256(content).hexdigest()
    family_counts = dict(sorted(Counter(value.family.value for value in goldens).items()))
    manifest = {
        "policy_version": ANSWER_GOLDEN_POLICY_VERSION,
        "cases": len(goldens),
        "family_counts": family_counts,
        "golden_sha256": digest,
        "upstream": {
            "finance_manifest_sha256": sha256(
                (args.finance_root / "manifest.json").read_bytes()
            ).hexdigest(),
            "graph_manifest_sha256": sha256(
                (args.graph_root / "manifest.json").read_bytes()
            ).hexdigest(),
        },
    }
    _atomic_private_write(args.output, content)
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    _atomic_private_write(
        manifest_path,
        (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
