"""Deterministic cross-provider identity projections.

Provider listings remain immutable source identities. This module adds a
canonical layer above them so a restaurant can be queried once without
discarding Swiggy/Zomato provenance.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from lunarbit.models import ContractModel, Platform
from lunarbit.resolve import CanonicalMerchant


class CanonicalMerchantIdentity(ContractModel):
    """One user-facing restaurant identity backed by provider listings."""

    identity_id: UUID
    canonical_name_private: str = Field(min_length=1)
    normalized_name_private: str = Field(min_length=1)
    aliases_private: tuple[str, ...] = Field(min_length=1)
    listing_ids: tuple[UUID, ...] = Field(min_length=1)
    platforms: tuple[Platform, ...] = Field(min_length=1)


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _identity_uuid(key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lunarbit-merchant-identity-v1:{key}")


def build_canonical_merchants(
    listings: Sequence[CanonicalMerchant],
    *,
    reviewed_aliases: Mapping[str, str] | None = None,
) -> tuple[CanonicalMerchantIdentity, ...]:
    """Group provider listings without changing their source IDs.

    reviewed_aliases maps any normalized source name to one reviewed
    canonical name. Without a review entry, only exact normalized names are
    grouped across providers; fuzzy matching is deliberately excluded.
    """

    aliases = {
        _key(source): canonical.strip() for source, canonical in (reviewed_aliases or {}).items()
    }
    groups: dict[str, list[CanonicalMerchant]] = defaultdict(list)
    for listing in listings:
        source_key = _key(listing.normalized_name_private)
        canonical = aliases.get(source_key, listing.normalized_name_private)
        groups[_key(canonical)].append(listing)

    identities: list[CanonicalMerchantIdentity] = []
    for group_key, group in sorted(groups.items()):
        names = tuple(
            sorted(
                {item.display_name_private for item in group},
                key=lambda value: (_key(value), value),
            )
        )
        canonical_name = aliases.get(group_key) or min(
            names,
            key=lambda value: (len(value), _key(value)),
        )
        identities.append(
            CanonicalMerchantIdentity(
                identity_id=_identity_uuid(group_key),
                canonical_name_private=canonical_name,
                normalized_name_private=group_key,
                aliases_private=names,
                listing_ids=tuple(sorted((item.merchant_id for item in group), key=str)),
                platforms=tuple(
                    sorted(
                        {item.platform for item in group},
                        key=lambda value: value.value,
                    )
                ),
            )
        )
    return tuple(identities)


def identity_manifest_checksum(
    identities: Sequence[CanonicalMerchantIdentity],
) -> str:
    """Return a stable checksum for migration idempotency and audit logs."""

    payload = "\n".join(identity.model_dump_json() for identity in identities)
    return sha256(payload.encode("utf-8")).hexdigest()
