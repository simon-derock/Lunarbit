"""Privacy-safe delivery-person identity projection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from lunarbit.models import ContractModel
from lunarbit.resolve import DeliveryPartnerMention


class DeliveryIdentityProjection(ContractModel):
    """Stable public identity backed by one or more source mentions."""

    person_id: UUID
    public_id: str = Field(pattern=r"^[0-9]{6}$")
    mention_ids: tuple[UUID, ...] = Field(min_length=1)
    order_ids: tuple[UUID, ...] = Field(min_length=1)


def delivery_public_id(normalized_name: str) -> str:
    """Derive a stable six-digit identifier without exposing the source name."""

    digest = sha256(f"lunarbit-delivery-person-v1:{normalized_name}".encode()).digest()
    return f"{100000 + int.from_bytes(digest[:4], 'big') % 900000:06d}"


def build_delivery_identities(
    mentions: Sequence[DeliveryPartnerMention],
) -> tuple[DeliveryIdentityProjection, ...]:
    """Group exact normalized delivery names and retain every order edge.

    Empty names are rejected rather than silently creating an identity for an
    unknown person. Fuzzy matching remains a human-reviewed operation.
    """

    groups: dict[str, list[DeliveryPartnerMention]] = defaultdict(list)
    for mention in mentions:
        normalized = " ".join(mention.normalized_name_private.split()).casefold()
        if not normalized:
            raise ValueError(f"delivery mention {mention.mention_id} has no normalized name")
        groups[normalized].append(mention)

    identities: list[DeliveryIdentityProjection] = []
    public_ids: dict[str, str] = {}
    for normalized, group in sorted(groups.items()):
        public_id = delivery_public_id(normalized)
        previous = public_ids.get(public_id)
        if previous is not None and previous != normalized:
            raise ValueError(f"delivery public-id collision for {public_id}")
        public_ids[public_id] = normalized
        identities.append(
            DeliveryIdentityProjection(
                person_id=uuid5(
                    NAMESPACE_URL,
                    f"lunarbit-delivery-person-v1:{normalized}",
                ),
                public_id=public_id,
                mention_ids=tuple(sorted((item.mention_id for item in group), key=str)),
                order_ids=tuple(
                    sorted(
                        {order_id for item in group for order_id in item.order_ids},
                        key=str,
                    )
                ),
            )
        )
    return tuple(identities)
