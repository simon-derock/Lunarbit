from __future__ import annotations

from lunarbit.product import item_name_from_table_row


def test_numeric_table_cells_are_not_promoted_to_item_names() -> None:
    assert item_name_from_table_row("14.90 | 1 | 14.90", ("Item", "Qty", "Amount")) is None
    assert (
        item_name_from_table_row("Chicken biryani | 1 | 14.90", ("Item", "Qty", "Amount"))
        == "Chicken biryani"
    )
