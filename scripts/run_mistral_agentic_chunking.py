#!/usr/bin/env python3
"""Run Lunarbit agentic batches sequentially through Mistral JSON mode."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import lunarbit.agentic as agentic


_KEY_NAMES = tuple(f"KEY_{name}" for name in ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN"))

def _keys(root: Path) -> tuple[str, ...]:
    values: dict[str, str] = {}
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        value = raw_value.strip().strip(chr(34)).strip(chr(39))
        if value:
            values[name.strip()] = value
    keys = tuple(values[name] for name in _KEY_NAMES if name in values)
    if not keys and values.get("MISTRAL_API_KEY"):
        keys = (values["MISTRAL_API_KEY"],)
    if not keys:
        raise RuntimeError("No Mistral API keys are configured in .env")
    if len(set(keys)) != len(keys):
        raise RuntimeError("Mistral API keys must be unique")
    return keys

def _key(root: Path) -> str:
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("MISTRAL_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("MISTRAL_API_KEY is not configured in .env")


def _propose(
    batch: agentic.AgenticBatch, *, key: str, model: str, timeout: float, max_tokens: int
) -> agentic.AgenticBatchResult:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": agentic._SYSTEM_PROMPT},
            {"role": "user", "content": agentic.render_agentic_user_prompt(batch)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = json.loads(error.read())
        message = str(detail.get("message", "unknown")).replace("\n", " ")[:240]
        raise RuntimeError(f"mistral_http_{error.code}:{message}") from error
    content = body["choices"][0]["message"]["content"]
    return agentic.validate_agentic_response(batch, content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", default="mistral-small-latest")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=24_000)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    key = _key(root)
    bundles = agentic.load_agentic_evidence_bundles(args.input)
    policy = agentic.AgenticBatchPolicy(
        target_input_tokens=12_000,
        max_input_tokens=16_000,
        max_completion_tokens=args.max_tokens,
        max_estimated_output_tokens=18_000,
        minimum_chunks=2,
    )
    counter = agentic.GemmaTokenizerCounter.from_cache(args.input / "_agentic" / "_tokenizer")
    plan = agentic.plan_agentic_batches(bundles, policy=policy, token_counter=counter)
    output_root = args.input / "_agentic"
    candidates = tuple(
        batch
        for batch in plan.batches
        if not args.resume or not (output_root / f"{batch.batch_id}.json").exists()
    )
    limit = args.max_calls or len(candidates)
    accepted = 0
    attempted = 0
    for batch in candidates[:limit]:
        attempted += 1
        try:
            result = _propose(
                batch,
                key=key,
                model=args.model,
                timeout=args.timeout_seconds,
                max_tokens=args.max_tokens,
            )
        except (RuntimeError, TimeoutError, urllib.error.URLError) as error:
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
        agentic.write_agentic_result(result, output_root)
        accepted += result.validation_status.value == "accepted"
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
