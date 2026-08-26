import json
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from scripts import run_mistral_agentic_chunking as runner


def _write_env(root: Path, contents: str) -> None:
    (root / ".env").write_text(contents, encoding="utf-8")


def test_loads_numbered_mistral_keys_in_stable_order(tmp_path: Path) -> None:
    _write_env(
        tmp_path,
        "KEY_THREE=third\nMISTRAL_API_KEY=fallback\nKEY_ONE=first\nKEY_TWO=second\n",
    )

    assert runner._keys(tmp_path) == ("first", "second", "third")


def test_rejects_duplicate_mistral_keys(tmp_path: Path) -> None:
    _write_env(tmp_path, "KEY_ONE=reused\nKEY_TWO=reused\n")

    with pytest.raises(RuntimeError, match="must be unique"):
        runner._keys(tmp_path)


def test_shards_batches_without_overlap() -> None:
    shards = runner._shard(tuple(range(10)), 3)

    assert shards == ((0, 3, 6, 9), (1, 4, 7), (2, 5, 8))
    assert sorted(item for shard in shards for item in shard) == list(range(10))


def test_extracts_single_agentic_tool_call_arguments() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "submit_agentic_regions",
                                "arguments": '{"batch_id":"example"}',
                            }
                        }
                    ]
                }
            }
        ]
    }

    assert runner._tool_arguments(body) == '{"batch_id":"example"}'


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [{"message": {"tool_calls": []}}]},
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "unexpected_tool",
                                    "arguments": "{}",
                                }
                            }
                        ]
                    }
                }
            ]
        },
    ],
)
def test_rejects_missing_or_unexpected_tool_calls(body: object) -> None:
    with pytest.raises(RuntimeError, match="mistral_invalid_tool_call"):
        runner._tool_arguments(body)


def test_resolves_call_local_references_to_code_owned_uuid_values() -> None:
    chunk_id = uuid5(NAMESPACE_URL, "test-mistral-chunk")
    component_id = uuid5(NAMESPACE_URL, "test-mistral-money")
    batch_id = uuid5(NAMESPACE_URL, "test-mistral-batch")
    batch = SimpleNamespace(
        batch_id=batch_id,
        chunks=(
            SimpleNamespace(
                chunk_id=chunk_id,
                candidate_money_components=(SimpleNamespace(component_id=component_id),),
            ),
        ),
    )
    raw = json.dumps(
        {
            "batch_id": "batch",
            "covered_source_chunk_ids": ["c0001"],
            "covered_money_component_ids": ["m0001"],
            "regions": [
                {
                    "source_chunk_ids": ["c0001"],
                    "candidate_facts": [{"source_chunk_id": "c0001"}],
                    "entity_candidates": [{"source_chunk_id": "c0001"}],
                    "money_interpretations": [
                        {
                            "source_component_id": "m0001",
                            "source_chunk_id": "c0001",
                        }
                    ],
                    "relation_candidates": [{"evidence_chunk_ids": ["c0001"]}],
                }
            ],
        }
    )

    resolved = json.loads(runner._resolve_references(batch, raw))

    assert resolved["batch_id"] == str(batch_id)
    assert resolved["covered_source_chunk_ids"] == [str(chunk_id)]
    assert resolved["covered_money_component_ids"] == [str(component_id)]
    region = resolved["regions"][0]
    assert region["source_chunk_ids"] == [str(chunk_id)]
    assert region["candidate_facts"][0]["source_chunk_id"] == str(chunk_id)
    assert region["entity_candidates"][0]["source_chunk_id"] == str(chunk_id)
    assert region["money_interpretations"][0] == {
        "source_component_id": str(component_id),
        "source_chunk_id": str(chunk_id),
    }
    assert region["relation_candidates"][0]["evidence_chunk_ids"] == [str(chunk_id)]
