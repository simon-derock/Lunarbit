from __future__ import annotations

import json
import re
from hashlib import sha256
from math import fsum, sqrt
from pathlib import Path
from typing import Any

from pydantic import Field

from lunarbit.agentic import _atomic_private_write
from lunarbit.models import ContractModel

_SAFE_IDENTIFIER_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class EmbeddingInput(ContractModel):
    node_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class VectorIdentifiers(ContractModel):
    property_name: str
    index_name: str
    model_property: str
    dimension_property: str


def normalized_matryoshka_prefix(
    vector: tuple[float, ...],
    *,
    dimension: int,
) -> tuple[float, ...]:
    if not 1 <= dimension <= len(vector):
        raise ValueError("Matryoshka dimension must fit inside the source vector")
    prefix = vector[:dimension]
    norm = sqrt(fsum(value * value for value in prefix))
    if norm == 0:
        raise ValueError("cannot normalize a zero Matryoshka prefix")
    return tuple(value / norm for value in prefix)


def batch_embedding_inputs(
    values: tuple[EmbeddingInput, ...],
    *,
    max_inputs: int,
) -> tuple[tuple[EmbeddingInput, ...], ...]:
    if max_inputs <= 0:
        raise ValueError("max_inputs must be positive")
    node_ids = tuple(value.node_id for value in values)
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("embedding inputs contain duplicate node IDs")
    return tuple(
        values[offset : offset + max_inputs] for offset in range(0, len(values), max_inputs)
    )


def archive_batch_path(
    output: Path,
    batch: tuple[EmbeddingInput, ...],
    *,
    model: str,
    dimension: int,
) -> Path:
    identity = json.dumps(
        {
            "model": model,
            "dimension": dimension,
            "node_ids": [value.node_id for value in batch],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return output / "batches" / f"{sha256(identity.encode()).hexdigest()}.json"


def write_embedding_batch(
    path: Path,
    batch: tuple[EmbeddingInput, ...],
    vectors: tuple[tuple[float, ...], ...],
    *,
    model: str,
    dimension: int,
    input_type: str,
) -> None:
    if len(batch) != len(vectors) or any(len(vector) != dimension for vector in vectors):
        raise ValueError("embedding vectors do not match the deterministic batch contract")
    rows = [
        {"node_id": value.node_id, "embedding": list(vector)}
        for value, vector in zip(batch, vectors, strict=True)
    ]
    content = {
        "model": model,
        "dimension": dimension,
        "input_type": input_type,
        "rows": rows,
    }
    _atomic_private_write(
        path,
        f"{json.dumps(content, separators=(',', ':'))}\n".encode(),
    )


def load_embedding_batch(
    path: Path,
    *,
    expected: tuple[EmbeddingInput, ...],
    model: str,
    dimension: int,
    input_type: str,
) -> tuple[dict[str, Any], ...]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict) or (
        body.get("model") != model
        or body.get("dimension") != dimension
        or body.get("input_type") != input_type
    ):
        raise ValueError("stored embedding batch contract changed")
    rows = body.get("rows")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("stored embedding batch coverage changed")
    parsed: list[dict[str, Any]] = []
    for row, expected_input in zip(rows, expected, strict=True):
        if not isinstance(row, dict) or row.get("node_id") != expected_input.node_id:
            raise ValueError("stored embedding batch coverage changed")
        vector = row.get("embedding")
        if not isinstance(vector, list) or len(vector) != dimension:
            raise ValueError("stored embedding dimension changed")
        if any(not isinstance(value, (int, float)) for value in vector):
            raise ValueError("stored embedding contains a non-numeric value")
        parsed.append(
            {
                "node_id": expected_input.node_id,
                "embedding": [float(value) for value in vector],
            }
        )
    return tuple(parsed)


def vector_identifiers(provider: str, model: str, dimension: int) -> VectorIdentifiers:
    if not _SAFE_IDENTIFIER_PART.fullmatch(provider) or not _SAFE_IDENTIFIER_PART.fullmatch(model):
        raise ValueError("vector identifier components contain unsupported characters")
    if dimension <= 0:
        raise ValueError("vector dimension must be positive")
    stem = re.sub(r"[^a-z0-9]+", "_", f"{provider}_{model}".lower()).strip("_")
    property_name = f"embedding_{stem}_{dimension}"
    return VectorIdentifiers(
        property_name=property_name,
        index_name=f"evidence_vector_{stem}_{dimension}",
        model_property=f"{property_name}_model",
        dimension_property=f"{property_name}_dimension",
    )
