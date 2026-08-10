#!/usr/bin/env python3
"""Run the existing agentic plan sequentially through Gemini function calling."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast

from lunarbit.agentic import (
    _SYSTEM_PROMPT,
    AGENTIC_TOOL_NAME,
    AgenticBatch,
    AgenticBatchPlan,
    AgenticBatchPolicy,
    AgenticBatchResult,
    GemmaTokenizerCounter,
    _agentic_tool_definition,
    load_agentic_evidence_bundles,
    plan_agentic_batches,
    render_agentic_user_prompt,
    validate_agentic_response,
    write_agentic_result,
)


def _env_key(root: Path) -> str:
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("GEMINI_API_KEY is not configured in .env")


def _gemini_tool(batch: AgenticBatch) -> dict[str, object]:
    tool = _agentic_tool_definition(
        batch_id=batch.batch_id,
        bundle_ids=batch.bundle_ids,
        chunks=batch.chunks,
    )
    parameters = cast(dict[str, Any], tool["parameters"])
    definitions = parameters.get("$defs", {})

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"].rsplit("/", 1)[-1]
                return normalize(definitions[reference])
            return {
                key: normalize(item)
                for key, item in value.items()
                if key
                not in {
                    "$defs",
                    "$ref",
                    "const",
                    "uniqueItems",
                    "additionalProperties",
                    "exclusiveMinimum",
                    "exclusiveMaximum",
                    "minimum",
                    "maximum",
                    "minLength",
                    "maxLength",
                    "pattern",
                    "minItems",
                    "maxItems",
                    "anyOf",
                }
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    parameters = normalize(parameters)
    return {
        "functionDeclarations": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": parameters,
            }
        ]
    }


def _propose(
    batch: AgenticBatch,
    *,
    key: str,
    model: str,
    timeout: float,
    max_output: int,
) -> AgenticBatchResult:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": render_agentic_user_prompt(batch)}]}],
        "tools": [_gemini_tool(batch)],
        "toolConfig": {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": [AGENTIC_TOOL_NAME],
            }
        },
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_output},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = json.loads(error.read()).get("error", {})
        message = str(detail.get("message", "unknown")).replace("\n", " ")[:240]
        raise RuntimeError(
            f"gemini_http_{error.code}:{detail.get('status', 'unknown')}:{message}"
        ) from error
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    calls = [part["functionCall"]["args"] for part in parts if "functionCall" in part]
    if len(calls) != 1:
        raise RuntimeError("gemini_missing_or_multiple_function_calls")
    result = validate_agentic_response(batch, json.dumps(calls[0], ensure_ascii=False))
    return result.model_copy(update={"model": model})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--bundle-start", type=int, default=0)
    parser.add_argument("--bundle-count", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--max-output-tokens", type=int, default=24_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Provider-specific result directory; defaults to input/_agentic/gemini",
    )
    args = parser.parse_args()
    key = _env_key(Path.cwd())
    bundles = load_agentic_evidence_bundles(args.input)
    if args.bundle_start < 0 or args.bundle_count < 0:
        parser.error("bundle-start and bundle-count must be non-negative")
    if args.bundle_count:
        bundles = bundles[args.bundle_start : args.bundle_start + args.bundle_count]
    elif args.bundle_start:
        bundles = bundles[args.bundle_start :]
    policy = AgenticBatchPolicy(
        target_input_tokens=12_000,
        max_input_tokens=16_000,
        max_completion_tokens=args.max_output_tokens,
        max_estimated_output_tokens=18_000,
        minimum_chunks=2,
    )
    counter = GemmaTokenizerCounter.from_cache(args.input / "_agentic" / "_tokenizer")
    plan: AgenticBatchPlan = plan_agentic_batches(bundles, policy=policy, token_counter=counter)
    output_root = args.output or (args.input / "_agentic" / "gemini")
    output_root.mkdir(parents=True, exist_ok=True)
    limit = args.max_calls or len(plan.batches)
    accepted = 0
    attempted = 0
    processed = 0
    for batch in plan.batches:
        result_path = output_root / f"{batch.batch_id}.json"
        if args.resume and result_path.exists():
            continue
        if processed >= limit:
            break
        processed += 1
        attempted += 1
        try:
            result = _propose(
                batch,
                key=key,
                model=args.model,
                timeout=args.timeout_seconds,
                max_output=args.max_output_tokens,
            )
        except (RuntimeError, urllib.error.URLError) as error:
            print(
                json.dumps(
                    {
                        "planned_batches": len(plan.batches),
                        "attempted_batches": attempted,
                        "accepted_batches": accepted,
                        "stopped_on_error": str(error),
                    }
                )
            )
            return 1
        write_agentic_result(result, output_root)
        if result.validation_status.value == "accepted":
            accepted += 1
    print(
        json.dumps(
            {
                "planned_batches": len(plan.batches),
                "attempted_batches": attempted,
                "accepted_batches": accepted,
                "stopped_on_error": None,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
