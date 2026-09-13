from __future__ import annotations

from scripts.repair_order_merchant_paths import (
    _candidate_identities,
    _identity_id,
    _source_merchant_name,
)


def test_source_receipt_merchant_extraction_is_deterministic() -> None:
    order = {
        "evidence": ("your zomato receipt: we hope you enjoyed your meal from csk food truck .",)
    }

    assert _source_merchant_name(order) == "CSK Food Truck"
    assert _identity_id("CSK Food Truck").startswith("merchant_identity:")


def test_candidate_resolution_prefers_the_longest_exact_reviewed_name() -> None:
    catalog = (
        {
            "identity_id": "merchant_identity:short",
            "listing_name": "Hotel New",
            "canonical_name": "Hotel New",
            "aliases": "",
        },
        {
            "identity_id": "merchant_identity:long",
            "listing_name": "Hotel New Thevar",
            "canonical_name": "Hotel New Thevar",
            "aliases": "Hotel New Thevar's",
        },
    )
    order = {"evidence": ("thank you for ordering from hotel new thevar we hope",)}

    assert _candidate_identities(order, catalog) == ("merchant_identity:long",)
