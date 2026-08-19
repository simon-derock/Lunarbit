from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, cast

from pydantic import Field

from lunarbit.models import ContractModel

EMBED_URL = "https://api.cohere.com/v2/embed"
RERANK_URL = "https://api.cohere.com/v2/rerank"
EMBED_MODEL = "embed-v4.0"
DEFAULT_RERANK_MODEL = "rerank-v4.0-pro"
EMBEDDING_DIMENSIONS = frozenset({256, 512, 1024, 1536})
MAX_EMBED_INPUTS = 96
MAX_RERANK_DOCUMENTS = 1_000


class EmbedInputType(StrEnum):
    SEARCH_DOCUMENT = "search_document"
    SEARCH_QUERY = "search_query"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"


class RerankModel(StrEnum):
    PRO = "rerank-v4.0-pro"
    FAST = "rerank-v4.0-fast"


class RerankResult(ContractModel):
    index: int = Field(ge=0)
    document: str
    score: float = Field(ge=0.0, le=1.0)


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lunarbit/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"cohere_http_{error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError("cohere_transport_error") from error
    if not isinstance(body, dict):
        raise ValueError("Cohere response must be a JSON object")
    return cast(dict[str, Any], body)


class CohereClient:
    """Small typed client for Lunarbit's bounded Embed v4 and Rerank v4 calls."""

    def __init__(
        self,
        api_key: str,
        *,
        embedding_dimension: int = 1536,
        rerank_model: RerankModel | str = RerankModel.PRO,
        timeout: float = 120.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Cohere API key cannot be empty")
        if embedding_dimension not in EMBEDDING_DIMENSIONS:
            raise ValueError(f"embedding dimension must be one of {sorted(EMBEDDING_DIMENSIONS)}")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key
        self.embedding_dimension = embedding_dimension
        self.rerank_model = str(rerank_model)
        self.timeout = timeout

    def embed(
        self,
        texts: Sequence[str],
        *,
        input_type: EmbedInputType = EmbedInputType.SEARCH_QUERY,
    ) -> tuple[tuple[float, ...], ...]:
        values = tuple(texts)
        if not values:
            raise ValueError("embedding input cannot be empty")
        if len(values) > MAX_EMBED_INPUTS:
            raise ValueError(f"Cohere Embed v4 accepts at most {MAX_EMBED_INPUTS} inputs per call")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("embedding inputs must be non-empty strings")
        body = _post_json(
            EMBED_URL,
            {
                "model": EMBED_MODEL,
                "texts": list(values),
                "input_type": input_type.value,
                "embedding_types": ["float"],
                "output_dimension": self.embedding_dimension,
            },
            api_key=self._api_key,
            timeout=self.timeout,
        )
        embeddings = body.get("embeddings")
        vectors = embeddings.get("float") if isinstance(embeddings, Mapping) else None
        if not isinstance(vectors, list) or len(vectors) != len(values):
            raise ValueError("Cohere embedding response shape does not match the request")
        parsed: list[tuple[float, ...]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self.embedding_dimension:
                raise ValueError("Cohere embedding response shape does not match the request")
            if any(not isinstance(value, (int, float)) for value in vector):
                raise ValueError("Cohere embedding response contains a non-numeric value")
            parsed.append(tuple(float(value) for value in vector))
        return tuple(parsed)

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        values = tuple(documents)
        if not query.strip():
            raise ValueError("rerank query cannot be empty")
        if not values:
            raise ValueError("rerank documents cannot be empty")
        if len(values) > MAX_RERANK_DOCUMENTS:
            raise ValueError(f"rerank accepts at most {MAX_RERANK_DOCUMENTS} documents")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("rerank documents must be non-empty strings")
        selected = len(values) if top_n is None else top_n
        if not 1 <= selected <= len(values):
            raise ValueError("top_n must be between one and the document count")
        body = _post_json(
            RERANK_URL,
            {
                "model": self.rerank_model,
                "query": query,
                "documents": list(values),
                "top_n": selected,
            },
            api_key=self._api_key,
            timeout=self.timeout,
        )
        rows = body.get("results")
        if not isinstance(rows, list):
            raise ValueError("Cohere rerank response shape does not match the request")
        results: list[RerankResult] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("Cohere rerank result must be an object")
            index = row.get("index")
            score = row.get("relevance_score")
            if not isinstance(index, int) or not 0 <= index < len(values):
                raise ValueError("Cohere rerank response contains an invalid document index")
            if not isinstance(score, (int, float)):
                raise ValueError("Cohere rerank response contains an invalid score")
            results.append(RerankResult(index=index, document=values[index], score=float(score)))
        return tuple(results)
