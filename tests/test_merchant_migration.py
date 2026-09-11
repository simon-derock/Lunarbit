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
