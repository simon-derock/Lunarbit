from __future__ import annotations

import json
from pathlib import Path

import pytest

from lunarbit.embedding_archive import (
    EmbeddingInput,
    archive_batch_path,
    batch_embedding_inputs,
    load_embedding_batch,
    normalized_matryoshka_prefix,
    vector_identifiers,
    write_embedding_batch,
)


def _inputs(count: int) -> tuple[EmbeddingInput, ...]:
    return tuple(
        EmbeddingInput(node_id=f"node:{index:03d}", text=f"evidence {index}")
        for index in range(count)
    )


def test_embedding_batches_respect_cohere_input_limit() -> None:
    batches = batch_embedding_inputs(_inputs(193), max_inputs=96)

    assert tuple(len(batch) for batch in batches) == (96, 96, 1)
    assert tuple(item.node_id for batch in batches for item in batch) == tuple(
        item.node_id for item in _inputs(193)
    )


def test_archive_identity_includes_model_dimension_and_node_coverage(tmp_path: Path) -> None:
    batch = _inputs(2)

    first = archive_batch_path(tmp_path, batch, model="embed-v4.0", dimension=1536)
    repeated = archive_batch_path(tmp_path, batch, model="embed-v4.0", dimension=1536)
    different_dimension = archive_batch_path(tmp_path, batch, model="embed-v4.0", dimension=256)

    assert first == repeated
    assert first.parent == tmp_path / "batches"
    assert first != different_dimension


def test_private_batch_round_trip_validates_contract(tmp_path: Path) -> None:
    path = tmp_path / "batch.json"
    batch = _inputs(2)
    vectors = ((0.1, 0.2), (0.3, 0.4))

    write_embedding_batch(
        path,
        batch,
        vectors,
        model="embed-v4.0",
        dimension=2,
        input_type="search_document",
    )

    assert path.stat().st_mode & 0o777 == 0o600
    assert load_embedding_batch(
        path,
        expected=batch,
        model="embed-v4.0",
        dimension=2,
        input_type="search_document",
    ) == (
        {"node_id": "node:000", "embedding": [0.1, 0.2]},
        {"node_id": "node:001", "embedding": [0.3, 0.4]},
    )


def test_archive_rejects_model_or_coverage_drift(tmp_path: Path) -> None:
    path = tmp_path / "batch.json"
    path.write_text(
        json.dumps(
            {
                "model": "wrong-model",
                "dimension": 2,
                "input_type": "search_document",
                "rows": [{"node_id": "node:000", "embedding": [0.1, 0.2]}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="contract"):
        load_embedding_batch(
            path,
            expected=_inputs(1),
            model="embed-v4.0",
            dimension=2,
            input_type="search_document",
        )


def test_vector_identifiers_are_versioned_and_cypher_safe() -> None:
    identifiers = vector_identifiers("cohere", "embed-v4.0", 1536)

    assert identifiers.property_name == "embedding_cohere_embed_v4_0_1536"
    assert identifiers.index_name == "evidence_vector_cohere_embed_v4_0_1536"
    assert identifiers.model_property == "embedding_cohere_embed_v4_0_1536_model"

    with pytest.raises(ValueError, match="identifier"):
        vector_identifiers("cohere`) MATCH (n) DETACH DELETE n //", "embed-v4.0", 1536)


def test_matryoshka_prefix_is_normalized_and_bounded() -> None:
    prefix = normalized_matryoshka_prefix((3.0, 4.0, 12.0), dimension=2)

    assert prefix == pytest.approx((0.6, 0.8))
    with pytest.raises(ValueError, match="dimension"):
        normalized_matryoshka_prefix((3.0, 4.0), dimension=3)
    with pytest.raises(ValueError, match="zero"):
        normalized_matryoshka_prefix((0.0, 0.0), dimension=2)
