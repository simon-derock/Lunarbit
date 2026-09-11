from __future__ import annotations

from lunarbit.graph import NodeLabel, RelationshipType


def test_canonical_merchant_graph_vocabulary_is_explicit() -> None:
    assert NodeLabel.MERCHANT_IDENTITY.value == "MerchantIdentity"
    assert RelationshipType.CANONICAL_OF.value == "CANONICAL_OF"
