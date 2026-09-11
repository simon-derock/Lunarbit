from __future__ import annotations

import inspect
import json

import scripts.migrate_merchant_identities as migration
from scripts.migrate_merchant_identities import _aliases


def test_alias_manifest_is_normalized_and_reviewed(tmp_path) -> None:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"  Hotel New Thevars ": "Hotel New Thevar"}))

    assert _aliases(path) == {"hotel new thevars": "Hotel New Thevar"}


def test_apply_keeps_canonical_identity_in_public_graph_namespace() -> None:
    source = inspect.getsource(migration._apply)
    assert "MERGE (identity:LunarbitNode:MerchantIdentity" in source
    assert 'canonical_name": str(group["canonical_name"])' in inspect.getsource(migration._plan)
    assert "DETACH DELETE legacy" in source
    assert "DELETE stale" in source
    assert "stale_identities_removed" in source
    assert "relationship_id: listing_row.relationship_id" in source
