from __future__ import annotations

from scripts.repair_order_merchant_paths import (
    _candidate_identities,
    _identity_id,
    _source_merchant_name,
    plan_repair,
)


def test_source_receipt_merchant_extraction_is_deterministic() -> None:
    order = {
        "evidence": ("your zomato receipt: we hope you enjoyed your meal from csk food truck .",)
    }

    assert _source_merchant_name(order) == "CSK Food Truck"
    assert _identity_id("CSK Food Truck").startswith("merchant_identity:")


def test_candidate_resolution_prefers_the_longest_exact_reviewed_name() -> None:
    catalog = (
        {
            "identity_id": "merchant_identity:short",
            "listing_name": "Hotel New",
            "canonical_name": "Hotel New",
            "aliases": "",
        },
        {
            "identity_id": "merchant_identity:long",
            "listing_name": "Hotel New Thevar",
            "canonical_name": "Hotel New Thevar",
            "aliases": "Hotel New Thevar's",
        },
    )
    order = {"evidence": ("thank you for ordering from hotel new thevar we hope",)}

    assert _candidate_identities(order, catalog) == ("merchant_identity:long",)


_CATALOG = (
    {
        "merchant_id": "merchant:kfc",
        "platform": "swiggy",
        "listing_name": "KFC",
        "identity_id": "merchant_identity:kfc",
        "canonical_name": "KFC",
        "aliases": "",
        "outlets": ["outlet:kfc"],
    },
    {
        "merchant_id": "merchant:grand",
        "platform": "swiggy",
        "listing_name": "Grand Chettinadu Non-Veg Restaurant",
        "identity_id": "merchant_identity:grand",
        "canonical_name": "Grand Chettinadu Restaurant",
        "aliases": "Grand Chettinadu Non-Veg Restaurant",
        "outlets": ["outlet:grand"],
    },
)
_HISTORY_REPORT = "swiggy order history kfc 349.00 grand chettinadu non veg restaurant 512.00"


class _RepairSession:
    """Answer the repair planner's three read queries from in-memory rows."""

    def __init__(
        self,
        orders: tuple[dict[str, object], ...],
        identities: dict[str, str] | None = None,
    ) -> None:
        self._orders = orders
        self._identities = identities or {
            str(row["identity_id"]): str(row["canonical_name"]) for row in _CATALOG
        }

    def run(self, query: str) -> list[dict[str, object]]:
        if query.startswith("MATCH (merchant:Merchant)"):
            return [dict(row) for row in _CATALOG]
        if query.startswith("MATCH (order:Order)"):
            return [dict(row) for row in self._orders]
        if query.startswith("MATCH (identity:MerchantIdentity)"):
            return [
                {"identity_id": identity_id, "canonical_name": name}
                for identity_id, name in self._identities.items()
            ]
        raise AssertionError(f"unexpected repair query: {query[:60]}")


def _order(
    *,
    outlet_identity: str | None,
    direct: tuple[str, ...] = (),
    local: tuple[str, ...] = (),
    shared: tuple[str, ...] = (),
) -> dict[str, object]:
    paths = (
        [{"outlet_id": f"outlet:{outlet_identity}", "identity_id": outlet_identity}]
        if outlet_identity
        else []
    )
    evidence_items = [{"text": text, "source_orders": 1} for text in local] + [
        {"text": text, "source_orders": 73} for text in shared
    ]
    return {
        "order_id": "order:1",
        "platform": "swiggy",
        "order_type": "food",
        "identity_status": "resolved",
        "paths": paths,
        "direct_identity_ids": list(direct),
        "evidence_items": evidence_items,
    }


def _actions(plan: dict[str, object]) -> list[tuple[str, str]]:
    actions = plan["actions"]
    assert isinstance(actions, list)
    return [(action["action"], action.get("identity_id", "")) for action in actions]


def test_shared_history_report_text_cannot_reassign_an_order() -> None:
    session = _RepairSession(
        (
            _order(
                outlet_identity="merchant_identity:kfc",
                local=("thank you for ordering from kfc we hope",),
                shared=(_HISTORY_REPORT,),
            ),
        )
    )

    plan = plan_repair(session)

    assert _actions(plan) == [("add_direct", "merchant_identity:kfc")]
    assert plan["conflicting_order_ids"] == []


def test_order_without_outlet_resolves_from_order_local_evidence_only() -> None:
    session = _RepairSession(
        (
            _order(
                outlet_identity=None,
                local=("thank you for ordering from kfc we hope",),
                shared=(_HISTORY_REPORT,),
            ),
        )
    )

    assert _actions(plan_repair(session)) == [("add_direct", "merchant_identity:kfc")]


def test_misassigned_direct_edge_is_replaced_by_the_outlet_identity() -> None:
    session = _RepairSession(
        (
            _order(
                outlet_identity="merchant_identity:kfc",
                direct=("merchant_identity:grand",),
                shared=(_HISTORY_REPORT,),
            ),
        )
    )

    assert _actions(plan_repair(session)) == [
        ("remove_direct", "merchant_identity:grand"),
        ("add_direct", "merchant_identity:kfc"),
    ]


def test_local_evidence_contradicting_the_outlet_is_reported_not_guessed() -> None:
    session = _RepairSession(
        (
            _order(
                outlet_identity="merchant_identity:kfc",
                direct=("merchant_identity:kfc",),
                local=("thank you for ordering from grand chettinadu non veg restaurant",),
            ),
        )
    )

    plan = plan_repair(session)

    assert _actions(plan) == []
    assert plan["conflicting_order_ids"] == ["order:1"]


def test_repair_converges_for_identities_created_from_source_receipts() -> None:
    receipt_identity = _identity_id("CSK Food Truck")
    session = _RepairSession(
        (
            _order(
                outlet_identity=None,
                direct=(receipt_identity,),
                local=("we hope you enjoyed your meal from csk food truck .",),
            ),
        ),
        identities={receipt_identity: "CSK Food Truck"},
    )

    assert _actions(plan_repair(session)) == []


def test_already_quarantined_order_is_not_replanned() -> None:
    order = _order(outlet_identity=None)
    order["identity_status"] = "quarantined_missing_merchant_evidence"
    plan = plan_repair(_RepairSession((order,)))

    assert _actions(plan) == []
    assert plan["unresolved_order_ids"] == ["order:1"]
