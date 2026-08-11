from __future__ import annotations

import pytest

from lunarbit.public import PublicMetric, assert_public_payload, build_demo_snapshot


def test_public_snapshot_is_synthetic_navigable_and_metric_backed() -> None:
    snapshot = build_demo_snapshot(
        metrics=(
            PublicMetric(label="Orders reconstructed", value="454"),
            PublicMetric(label="Evidence chunks", value="24,675"),
        )
    )
    payload = snapshot.model_dump(mode="json")

    assert snapshot.mode == "synthetic_mirror"
    assert len(snapshot.sample_questions) >= 10
    assert len(snapshot.nodes) >= 12
    assert len(snapshot.edges) >= 12
    assert any(node.label.value == "Evidence" for node in snapshot.nodes)
    assert any(edge.relationship == "EVIDENCED_BY" for edge in snapshot.edges)
    assert_public_payload(payload)


@pytest.mark.parametrize(
    "payload",
    (
        {"merchant_name_private": "Sensitive Kitchen"},
        {"source_hash": "a" * 64},
        {"safe": {"email": "customer@example.com"}},
        {"safe": "Contact customer@example.com"},
        {"safe": "9876543210"},
    ),
)
def test_public_payload_validator_rejects_private_keys_and_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="public payload"):
        assert_public_payload(payload)
