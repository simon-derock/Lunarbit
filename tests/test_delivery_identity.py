from __future__ import annotations

from uuid import uuid4

from lunarbit.delivery_identity import build_delivery_identities, delivery_public_id
from lunarbit.models import Platform
from lunarbit.resolve import DeliveryIdentityStatus, DeliveryPartnerMention


def _mention(name: str, orders: tuple[str, ...]) -> DeliveryPartnerMention:
    return DeliveryPartnerMention(
        mention_id=uuid4(),
        raw_name_private=name,
        normalized_name_private=name.casefold(),
        source_chunk_id=uuid4(),
        source_id="doc_" + "a" * 16,
        platform=Platform.SWIGGY,
        order_ids=tuple(uuid4() for _ in orders),
        identity_status=DeliveryIdentityStatus.MENTION_ONLY,
    )


def test_delivery_identity_is_stable_and_keeps_all_orders() -> None:
    first = _mention("Courier Alpha", ("one",))
    second = _mention("Courier Alpha", ("two",))

    identities = build_delivery_identities((first, second))

    assert len(identities) == 1
    assert identities[0].public_id == delivery_public_id("courier alpha")
    assert len(identities[0].mention_ids) == 2
    assert len(identities[0].order_ids) == 2


def test_missing_delivery_name_is_rejected() -> None:
    mention = _mention("Courier Alpha", ("one",))
    mention = mention.model_copy(update={"normalized_name_private": ""})

    try:
        build_delivery_identities((mention,))
    except ValueError as error:
        assert "no normalized name" in str(error)
    else:
        raise AssertionError("missing delivery names must not create identities")
