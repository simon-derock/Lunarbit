from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import Field, model_validator

from lunarbit.models import ContractModel

type PublicScalar = str | int | float | bool | None
_FORBIDDEN_KEYS = frozenset(
    {
        "address",
        "document_id",
        "email",
        "fssai",
        "gstin",
        "invoice_id",
        "message_id",
        "order_id",
        "pan",
        "payment_reference",
        "phone",
        "sha256",
        "source_hash",
    }
)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{10,}(?!\d)")
_CONTENT_HASH = re.compile(r"\b[0-9a-fA-F]{64}\b")


def assert_public_payload(value: object, *, path: str = "root") -> None:
    """Reject private identifiers and contact-shaped values at the publish boundary."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold()
            if (
                normalized in _FORBIDDEN_KEYS
                or "private" in normalized
                or normalized.startswith("raw_")
            ):
                raise ValueError(f"public payload contains a forbidden key at {path}.{key}")
            assert_public_payload(child, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            assert_public_payload(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and (
        _EMAIL.search(value) or _LONG_NUMBER.search(value) or _CONTENT_HASH.search(value)
    ):
        raise ValueError(f"public payload contains a forbidden scalar at {path}")


class PublicMetric(ContractModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=40)
    detail: str | None = Field(default=None, max_length=160)


class PublicNodeLabel(StrEnum):
    PLATFORM = "Platform"
    ORDER = "Order"
    MERCHANT = "Merchant"
    ITEM = "Item"
    MONEY_COMPONENT = "MoneyComponent"
    EVIDENCE = "Evidence"
    RECONCILIATION = "Reconciliation"


class PublicNode(ContractModel):
    id: str = Field(pattern=r"^pub:[a-z0-9:-]+$")
    label: PublicNodeLabel
    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(min_length=1, max_length=120)
    properties: dict[str, PublicScalar]


class PublicEdge(ContractModel):
    id: str = Field(pattern=r"^pub:edge:[a-z0-9-]+$")
    source: str = Field(pattern=r"^pub:[a-z0-9:-]+$")
    target: str = Field(pattern=r"^pub:[a-z0-9:-]+$")
    relationship: str = Field(pattern=r"^[A-Z_]+$")


class PublicSnapshot(ContractModel):
    mode: str = "synthetic_mirror"
    disclosure: str
    metrics: tuple[PublicMetric, ...]
    sample_questions: tuple[str, ...] = Field(min_length=10)
    nodes: tuple[PublicNode, ...] = Field(min_length=1)
    edges: tuple[PublicEdge, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def graph_is_closed_and_public(self) -> PublicSnapshot:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("public graph node IDs must be unique")
        if any(edge.source not in node_ids or edge.target not in node_ids for edge in self.edges):
            raise ValueError("public graph edges must reference public nodes")
        assert_public_payload(self.model_dump(mode="json"))
        return self


def _node(
    identifier: str,
    label: PublicNodeLabel,
    title: str,
    subtitle: str,
    **properties: PublicScalar,
) -> PublicNode:
    return PublicNode(
        id=f"pub:{identifier}",
        label=label,
        title=title,
        subtitle=subtitle,
        properties=properties,
    )


def build_demo_snapshot(*, metrics: tuple[PublicMetric, ...]) -> PublicSnapshot:
    """Build a deterministic synthetic mirror; no private graph values enter this function."""
    nodes = (
        _node("platform:z", PublicNodeLabel.PLATFORM, "Platform Z", "Food commerce"),
        _node("platform:s", PublicNodeLabel.PLATFORM, "Platform S", "Food commerce"),
        _node("order:alpha", PublicNodeLabel.ORDER, "Order Alpha", "Synthetic · 2023"),
        _node("order:beta", PublicNodeLabel.ORDER, "Order Beta", "Synthetic · 2026"),
        _node("merchant:ember", PublicNodeLabel.MERCHANT, "Ember Kitchen", "Public alias"),
        _node("merchant:harbor", PublicNodeLabel.MERCHANT, "Harbor Bowl", "Public alias"),
        _node("item:biryani", PublicNodeLabel.ITEM, "Spiced Rice Bowl", "Comparable meal"),
        _node("item:wrap", PublicNodeLabel.ITEM, "Garden Wrap", "Comparable meal"),
        _node(
            "money:item",
            PublicNodeLabel.MONEY_COMPONENT,
            "Item subtotal",
            "Synthetic INR 420.00",
            amount="420.00",
            currency="INR",
        ),
        _node(
            "money:fee",
            PublicNodeLabel.MONEY_COMPONENT,
            "Platform fee",
            "Synthetic INR 12.00",
            amount="12.00",
            currency="INR",
        ),
        _node(
            "money:discount",
            PublicNodeLabel.MONEY_COMPONENT,
            "Promotion",
            "Synthetic INR -80.00",
            amount="-80.00",
            currency="INR",
        ),
        _node("evidence:summary", PublicNodeLabel.EVIDENCE, "Summary evidence", "Redacted demo"),
        _node("evidence:fee", PublicNodeLabel.EVIDENCE, "Fee evidence", "Redacted demo"),
        _node(
            "reconciliation:alpha",
            PublicNodeLabel.RECONCILIATION,
            "Scoped reconciliation",
            "Exact synthetic equation",
            status="exact",
        ),
    )
    edge_values = (
        ("1", "order:alpha", "platform:z", "PLACED_ON"),
        ("2", "order:beta", "platform:s", "PLACED_ON"),
        ("3", "order:alpha", "merchant:ember", "ORDERED_FROM"),
        ("4", "order:beta", "merchant:harbor", "ORDERED_FROM"),
        ("5", "order:alpha", "item:biryani", "HAS_ITEM_OBSERVATION"),
        ("6", "order:beta", "item:wrap", "HAS_ITEM_OBSERVATION"),
        ("7", "order:alpha", "money:item", "HAS_COMPONENT"),
        ("8", "order:alpha", "money:fee", "HAS_COMPONENT"),
        ("9", "order:alpha", "money:discount", "HAS_COMPONENT"),
        ("10", "money:item", "evidence:summary", "EVIDENCED_BY"),
        ("11", "money:fee", "evidence:fee", "EVIDENCED_BY"),
        ("12", "order:alpha", "reconciliation:alpha", "RECONCILED_BY"),
        ("13", "reconciliation:alpha", "money:item", "USED"),
        ("14", "reconciliation:alpha", "money:fee", "USED"),
        ("15", "reconciliation:alpha", "money:discount", "USED"),
    )
    edges = tuple(
        PublicEdge(
            id=f"pub:edge:{identifier}",
            source=f"pub:{source}",
            target=f"pub:{target}",
            relationship=relationship,
        )
        for identifier, source, target, relationship in edge_values
    )
    questions = (
        "How did the same meal's effective price change across three years?",
        "Did discounts offset the rise in platform and delivery fees?",
        "Which evidence proves each component of this reconstructed total?",
        "When did fee burden grow faster than the underlying item subtotal?",
        "Which merchant aliases show repeat-order behaviour across platforms?",
        "How many reconciled orders contain a platform-fee component?",
        "Which historical orders are comparable without guessing item identity?",
        "Where do invoice scope and customer-payable scope disagree?",
        "What graph path connects a promotion to its source evidence?",
        "Which claims must abstain because their source authority is insufficient?",
        "How did tax, fees, and discounts reshape the effective meal price?",
        "Which residual conflicts survive deterministic financial reconciliation?",
    )
    return PublicSnapshot(
        disclosure=(
            "Synthetic longitudinal transactions mirror the private graph schema; "
            "headline corpus counts are reviewed aggregates."
        ),
        metrics=metrics,
        sample_questions=questions,
        nodes=nodes,
        edges=edges,
    )
