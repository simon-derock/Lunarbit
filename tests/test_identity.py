from __future__ import annotations

from uuid import uuid4

from lunarbit.identity import build_canonical_merchants
from lunarbit.models import Platform
from lunarbit.resolve import CanonicalMerchant


def _merchant(name: str, platform: Platform) -> CanonicalMerchant:
    return CanonicalMerchant(
        merchant_id=uuid4(),
        platform=platform,
        display_name_private=name,
        normalized_name_private=" ".join(name.split()).casefold(),
        alias_names_private=(name,),
        mention_ids=(uuid4(),),
        resolution_id=uuid4(),
    )


def test_exact_name_across_providers_has_one_identity() -> None:
    identities = build_canonical_merchants(
        (
            _merchant("Hotel Kannappa", Platform.SWIGGY),
            _merchant("Hotel Kannappa", Platform.ZOMATO),
        )
    )

    assert len(identities) == 1
    assert identities[0].canonical_name_private == "Hotel Kannappa"
    assert set(identities[0].platforms) == {Platform.SWIGGY, Platform.ZOMATO}
    assert len(identities[0].listing_ids) == 2


def test_reviewed_aliases_merge_variants_without_fuzzy_merges() -> None:
    identities = build_canonical_merchants(
        (
            _merchant("Hotel New Thevar", Platform.ZOMATO),
            _merchant("Hotel New Thevar's - Veg", Platform.SWIGGY),
            _merchant("Hotel New Thevar's - Non Veg", Platform.SWIGGY),
            _merchant("Unrelated Hotel", Platform.SWIGGY),
        ),
        reviewed_aliases={
            "hotel new thevar": "Hotel New Thevar",
            "hotel new thevar's - veg": "Hotel New Thevar",
            "hotel new thevar's - non veg": "Hotel New Thevar",
        },
    )

    assert len(identities) == 2
    hotel = next(
        identity for identity in identities if identity.canonical_name_private == "Hotel New Thevar"
    )
    assert len(hotel.listing_ids) == 3
    assert set(hotel.platforms) == {Platform.SWIGGY, Platform.ZOMATO}
