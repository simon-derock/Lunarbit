from __future__ import annotations

from scripts.build_resolutions import _merchant_candidate_from_message


def test_email_merchant_fallback_uses_explicit_fields_only() -> None:
    assert (
        _merchant_candidate_from_message(
            "Your Zomato order from Hotel Kannappa Grand Gardenia",
            "Issued on behalf of\nHotel Kannappa Grand Gardenia\n"
            "Please order from a different restaurant.",
        )
        == "Hotel Kannappa Grand Gardenia"
    )
    assert (
        _merchant_candidate_from_message("Order update", "Please order from another restaurant")
        is None
    )
