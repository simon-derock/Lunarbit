from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.agentic import (  # noqa: E402
    CLOUDFLARE_MODEL,
    AgenticBatchPlan,
    AgenticBatchPolicy,
    CloudflareWorkersAIClient,
    execute_agentic_plan,
    load_agentic_evidence_bundles,
    plan_agentic_batches,
    render_agentic_user_prompt,
)


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description=(
            "Plan or sequentially execute medium, order-relevant agentic chunking batches."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Private Phase 1/2 processed archive root",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send private evidence to Cloudflare Workers AI; dry-run is the default",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=0,
        help="Maximum sequential API calls; required with --execute",
    )
    parser.add_argument("--target-characters", type=int, default=18_000)
    parser.add_argument("--max-characters", type=int, default=32_000)
    parser.add_argument("--max-chunks", type=int, default=32)
    parser.add_argument("--max-bundles", type=int, default=6)
    args = parser.parse_args()
    if args.execute and args.max_calls < 1:
        parser.error("--execute requires --max-calls of at least 1")
    if not args.execute and args.max_calls:
        parser.error("--max-calls is only valid with --execute")
    return args


def _plan_summary(plan: AgenticBatchPlan) -> dict[str, object]:
    chunk_counts = tuple(len(batch.chunks) for batch in plan.batches)
    prompt_sizes = tuple(len(render_agentic_user_prompt(batch)) for batch in plan.batches)
    planned_chunks = sum(chunk_counts)
    return {
        "model": CLOUDFLARE_MODEL,
        "execution": "dry-run",
        "bundles": plan.bundles,
        "input_chunks": plan.input_chunks,
        "planned_batches": len(plan.batches),
        "planned_chunks": planned_chunks,
        "quarantined_chunks": len(plan.quarantined_chunk_ids),
        "chunks_per_batch": {
            "minimum": min(chunk_counts, default=0),
            "average": round(planned_chunks / len(chunk_counts), 2) if chunk_counts else 0,
            "maximum": max(chunk_counts, default=0),
        },
        "prompt_characters": {
            "minimum": min(prompt_sizes, default=0),
            "average": round(sum(prompt_sizes) / len(prompt_sizes), 2) if prompt_sizes else 0,
            "maximum": max(prompt_sizes, default=0),
        },
        "concurrency": 1,
    }


def main() -> int:
    args = parse_args()
    bundles = load_agentic_evidence_bundles(args.input)
    policy = AgenticBatchPolicy(
        target_prompt_characters=args.target_characters,
        max_prompt_characters=args.max_characters,
        max_chunks=args.max_chunks,
        max_bundles=args.max_bundles,
        minimum_chunks=2,
    )
    plan = plan_agentic_batches(bundles, policy=policy)
    if not args.execute:
        print(json.dumps(_plan_summary(plan), indent=2))
        return 0

    client = CloudflareWorkersAIClient.from_environment()
    summary = execute_agentic_plan(
        plan,
        client=client,
        output_root=args.input / "_agentic",
        max_calls=args.max_calls,
    )
    output = summary.model_dump(mode="json")
    output.update({"model": CLOUDFLARE_MODEL, "concurrency": 1})
    print(json.dumps(output, indent=2))
    return 0 if summary.quarantined_batches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
