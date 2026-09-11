from __future__ import annotations

from uuid import UUID

from lunarbit.graph import NodeLabel, RelationshipType
from lunarbit.models import Platform
from lunarbit.resolve import DeliveryIdentityStatus, DeliveryPartnerMention
from scripts.build_graph import _delivery_identity_records


def test_canonical_merchant_graph_vocabulary_is_explicit() -> None:
    assert NodeLabel.MERCHANT_IDENTITY.value == "MerchantIdentity"
    assert RelationshipType.CANONICAL_OF.value == "CANONICAL_OF"


def test_delivery_identity_graph_links_pseudonym_to_every_order() -> None:
    mention = DeliveryPartnerMention(
        mention_id=UUID("00000000-0000-0000-0000-000000000001"),
        raw_name_private="Courier Beta",
        normalized_name_private="courier beta",
        source_chunk_id=UUID("00000000-0000-0000-0000-000000000002"),
        source_id="doc_0000000000000001",
        platform=Platform.SWIGGY,
        order_ids=(
            UUID("00000000-0000-0000-0000-000000000003"),
            UUID("00000000-0000-0000-0000-000000000004"),
        ),
        identity_status=DeliveryIdentityStatus.MENTION_ONLY,
    )
    nodes, relationships = _delivery_identity_records((mention,))
    assert nodes[0].labels == (NodeLabel.PERSON_IDENTITY,)
    assert nodes[0].properties["public_label"].startswith("Delivery participant ")
    assert sum(r.relationship_type is RelationshipType.DELIVERED_BY for r in relationships) == 2
    assert sum(r.relationship_type is RelationshipType.RESOLVED_TO for r in relationships) == 1
