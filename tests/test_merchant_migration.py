from __future__ import annotations

import json

from scripts.migrate_merchant_identities import _aliases


def test_alias_manifest_is_normalized_and_reviewed(tmp_path) -> None:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"  Hotel New Thevars ": "Hotel New Thevar"}))

    assert _aliases(path) == {"hotel new thevars": "Hotel New Thevar"}
