from __future__ import annotations

from lunarbit.evaluation import retrieval_metrics


def test_retrieval_metrics_report_rank_quality_and_tail_latency() -> None:
    metrics = retrieval_metrics(
        (1, 2, 7, None),
        (10.0, 20.0, 30.0, 100.0),
    )

    assert metrics.queries == 4
    assert metrics.hit_at_1 == 0.25
    assert metrics.hit_at_5 == 0.5
    assert metrics.hit_at_10 == 0.75
    assert round(metrics.mrr, 6) == round((1.0 + 0.5 + (1 / 7)) / 4, 6)
    assert metrics.p50_latency_ms == 25.0
    assert metrics.p95_latency_ms == 100.0


def test_retrieval_metrics_require_aligned_nonempty_measurements() -> None:
    for ranks, latencies in (((), ()), ((1,), ()), ((0,), (1.0,))):
        try:
            retrieval_metrics(ranks, latencies)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid benchmark measurements must be rejected")
