from __future__ import annotations

from math import ceil
from statistics import median

from pydantic import Field

from lunarbit.models import ContractModel


class RetrievalMetrics(ContractModel):
    queries: int = Field(ge=1)
    hit_at_1: float = Field(ge=0.0, le=1.0)
    hit_at_5: float = Field(ge=0.0, le=1.0)
    hit_at_10: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    p50_latency_ms: float = Field(ge=0.0)
    p95_latency_ms: float = Field(ge=0.0)


def retrieval_metrics(
    ranks: tuple[int | None, ...],
    latencies_ms: tuple[float, ...],
) -> RetrievalMetrics:
    if not ranks or len(ranks) != len(latencies_ms):
        raise ValueError("benchmark ranks and latencies must be nonempty and aligned")
    if any(rank is not None and rank < 1 for rank in ranks):
        raise ValueError("retrieval ranks must be positive")
    if any(latency < 0 for latency in latencies_ms):
        raise ValueError("retrieval latency cannot be negative")
    count = len(ranks)
    ordered_latency = sorted(latencies_ms)
    p95_index = max(0, ceil(0.95 * count) - 1)
    return RetrievalMetrics(
        queries=count,
        hit_at_1=sum(rank == 1 for rank in ranks) / count,
        hit_at_5=sum(rank is not None and rank <= 5 for rank in ranks) / count,
        hit_at_10=sum(rank is not None and rank <= 10 for rank in ranks) / count,
        mrr=sum(0.0 if rank is None else 1.0 / rank for rank in ranks) / count,
        p50_latency_ms=float(median(ordered_latency)),
        p95_latency_ms=float(ordered_latency[p95_index]),
    )
