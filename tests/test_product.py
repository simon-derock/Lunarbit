from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from lunarbit.product import (
    ItemEvidenceObservation,
    item_name_from_table_row,
    resolve_item_observations,
)


def test_item_name_extraction_uses_table_semantics_and_rejects_financial_labels() -> None:
    assert (
        item_name_from_table_row(
            "1 | Chicken Biryani | 299.00",
            ("Sr.No", "Particulars", "Total"),
        )
        == "Chicken Biryani"
    )
    assert item_name_from_table_row("Paneer Roll | 149.00", ("", "")) == "Paneer Roll"
    assert item_name_from_table_row(
        "Platform fee | 6.00",
        ("Particulars", "Total"),
    ) is None
    assert item_name_from_table_row("2 | 299.00", ("Qty", "Total")) is None


def test_item_resolution_is_merchant_scoped_and_keeps_comparability_separate() -> None:
    first_merchant = UUID("10000000-0000-0000-0000-000000000001")
    second_merchant = UUID("10000000-0000-0000-0000-000000000002")
    observations = (
        ItemEvidenceObservation(
            observation_id=UUID("20000000-0000-0000-0000-000000000001"),
            order_id=UUID("30000000-0000-0000-0000-000000000001"),
            merchant_id=first_merchant,
            source_chunk_id=UUID("40000000-0000-0000-0000-000000000001"),
            source_component_id=UUID("50000000-0000-0000-0000-000000000001"),
            raw_name_private="Chicken Biryani",
            normalized_name_private="chicken biryani",
            observed_amount=Decimal("299.00"),
            currency="INR",
            source_precision=2,
        ),
        ItemEvidenceObservation(
            observation_id=UUID("20000000-0000-0000-0000-000000000002"),
            order_id=UUID("30000000-0000-0000-0000-000000000002"),
            merchant_id=first_merchant,
            source_chunk_id=UUID("40000000-0000-0000-0000-000000000002"),
            source_component_id=UUID("50000000-0000-0000-0000-000000000002"),
            raw_name_private="CHICKEN BIRYANI",
            normalized_name_private="chicken biryani",
            observed_amount=Decimal("319.00"),
            currency="INR",
            source_precision=2,
        ),
        ItemEvidenceObservation(
            observation_id=UUID("20000000-0000-0000-0000-000000000003"),
            order_id=UUID("30000000-0000-0000-0000-000000000003"),
            merchant_id=second_merchant,
            source_chunk_id=UUID("40000000-0000-0000-0000-000000000003"),
            source_component_id=UUID("50000000-0000-0000-0000-000000000003"),
            raw_name_private="Chicken Biryani",
            normalized_name_private="chicken biryani",
            observed_amount=Decimal("279.00"),
            currency="INR",
            source_precision=2,
        ),
    )

    archive = resolve_item_observations(observations)
    replay = resolve_item_observations(tuple(reversed(observations)))

    assert archive == replay
    assert archive.summary.item_observations == 3
    assert archive.summary.merchant_items == 2
    assert archive.summary.canonical_items == 0
    assert archive.summary.comparable_item_groups == 0
    first = next(item for item in archive.merchant_items if item.merchant_id == first_merchant)
    assert len(first.observation_ids) == 2
    assert archive.canonical_items == ()
    assert archive.comparable_item_groups == ()
