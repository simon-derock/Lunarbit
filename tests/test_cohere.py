from __future__ import annotations

from typing import Any

import pytest

from lunarbit.cohere import CohereClient, EmbedInputType


def test_embed_v4_uses_explicit_search_mode_and_mrl_dimension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        observed.update(url=url, payload=payload, kwargs=kwargs)
        return {"embeddings": {"float": [[0.1, 0.2], [0.3, 0.4]]}}

    monkeypatch.setattr("lunarbit.cohere._post_json", fake_post)
    client = CohereClient("private-token", embedding_dimension=2)

    vectors = client.embed(("first", "second"), input_type=EmbedInputType.SEARCH_DOCUMENT)

    assert vectors == ((0.1, 0.2), (0.3, 0.4))
    assert observed["url"] == "https://api.cohere.com/v2/embed"
    assert observed["payload"] == {
        "model": "embed-v4.0",
        "texts": ["first", "second"],
        "input_type": "search_document",
        "embedding_types": ["float"],
        "output_dimension": 2,
    }
    assert observed["kwargs"]["api_key"] == "private-token"


def test_embed_rejects_oversized_batches_before_network_access() -> None:
    client = CohereClient("private-token")

    with pytest.raises(ValueError, match="96"):
        client.embed(tuple(str(index) for index in range(97)))


def test_embed_rejects_response_shape_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lunarbit.cohere._post_json",
        lambda *args, **kwargs: {"embeddings": {"float": [[0.1]]}},
    )
    client = CohereClient("private-token", embedding_dimension=2)

    with pytest.raises(ValueError, match="shape"):
        client.embed(("first",))


def test_rerank_v4_maps_scores_to_original_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        observed.update(url=url, payload=payload, kwargs=kwargs)
        return {
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.42},
            ]
        }

    monkeypatch.setattr("lunarbit.cohere._post_json", fake_post)
    client = CohereClient("private-token")

    results = client.rerank("historic biryani price", ("new", "old"), top_n=2)

    assert [(item.index, item.document, item.score) for item in results] == [
        (1, "old", 0.91),
        (0, "new", 0.42),
    ]
    assert observed["url"] == "https://api.cohere.com/v2/rerank"
    assert observed["payload"] == {
        "model": "rerank-v4.0-pro",
        "query": "historic biryani price",
        "documents": ["new", "old"],
        "top_n": 2,
    }


def test_rerank_rejects_unknown_response_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lunarbit.cohere._post_json",
        lambda *args, **kwargs: {"results": [{"index": 5, "relevance_score": 0.5}]},
    )
    client = CohereClient("private-token")

    with pytest.raises(ValueError, match="index"):
        client.rerank("query", ("only candidate",))
