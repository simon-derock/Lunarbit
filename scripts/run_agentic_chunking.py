from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from lunarbit.agentic import (  # noqa: E402
    CLOUDFLARE_MODEL,
    CLOUDFLARE_STREAM_TIMEOUT_SECONDS,
    AgenticBatchPlan,
    AgenticBatchPolicy,
    CloudflareWorkersAIClient,
    GemmaTokenizerCounter,
    execute_agentic_plan,
    load_agentic_evidence_bundles,
    plan_agentic_batches,
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
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--target-input-tokens", type=int, default=64_000)
    parser.add_argument("--max-input-tokens", type=int, default=80_000)
    parser.add_argument("--max-completion-tokens", type=int, default=24_000)
    parser.add_argument("--max-estimated-output-tokens", type=int, default=18_000)
    parser.add_argument("--max-chunks", type=int, default=512)
    parser.add_argument("--max-bundles", type=int, default=6)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=CLOUDFLARE_STREAM_TIMEOUT_SECONDS,
        help="Socket timeout for connecting to and reading the SSE stream",
    )
    args = parser.parse_args()
    if args.execute and args.max_calls < 1:
        parser.error("--execute requires --max-calls of at least 1")
    if not args.execute and args.max_calls:
        parser.error("--max-calls is only valid with --execute")
    return args


def _plan_summary(plan: AgenticBatchPlan) -> dict[str, object]:
    chunk_counts = tuple(len(batch.chunks) for batch in plan.batches)
    input_token_counts = tuple(batch.estimated_input_tokens for batch in plan.batches)
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
        "estimated_input_tokens": {
            "counter": plan.batches[0].token_counter_id if plan.batches else None,
            "minimum": min(input_token_counts, default=0),
            "average": (
                round(sum(input_token_counts) / len(input_token_counts), 2)
                if input_token_counts
                else 0
            ),
            "maximum": max(input_token_counts, default=0),
        },
        "concurrency": 1,
    }


def main() -> int:
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
    args = parse_args()
    bundles = load_agentic_evidence_bundles(args.input)
    policy = AgenticBatchPolicy(
        target_input_tokens=args.target_input_tokens,
        max_input_tokens=args.max_input_tokens,
        max_completion_tokens=args.max_completion_tokens,
        max_estimated_output_tokens=args.max_estimated_output_tokens,
        max_chunks=args.max_chunks,
        max_bundles=args.max_bundles,
        minimum_chunks=2,
    )
    token_counter = GemmaTokenizerCounter.from_cache(args.input / "_agentic" / "_tokenizer")
    plan = plan_agentic_batches(
        bundles,
        policy=policy,
        token_counter=token_counter,
    )
    if not args.execute:
        print(json.dumps(_plan_summary(plan), indent=2))
        return 0

    client = CloudflareWorkersAIClient.from_environment(
        max_completion_tokens=policy.max_completion_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    summary = execute_agentic_plan(
        plan,
        client=client,
        output_root=args.input / "_agentic",
        max_calls=args.max_calls,
        resume=args.resume,
    )
    output = summary.model_dump(mode="json")
    output.update({"model": CLOUDFLARE_MODEL, "concurrency": 1})
    print(json.dumps(output, indent=2))
    return 0 if summary.quarantined_batches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
