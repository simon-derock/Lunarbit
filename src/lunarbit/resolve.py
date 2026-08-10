from __future__ import annotations

import hmac
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.models import (
    ContractModel,
    OrderCategory,
    OrderEvidence,
    OrderEvidenceKind,
    Platform,
    SourceDocument,
    SourceMessage,
)

ORDER_RESOLUTION_POLICY_VERSION = "order-resolution-v1.0.0"


class OrderIdentityStatus(StrEnum):
    RESOLVED = "resolved"
    PROVISIONAL = "provisional"
    SUPERSEDED = "superseded"


class ResolutionType(StrEnum):
    ORDER = "order"
    MERCHANT = "merchant"
    OUTLET = "outlet"
    LEGAL_ENTITY = "legal_entity"
    MERCHANT_ITEM = "merchant_item"
    DELIVERY_PERSON = "delivery_person"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    PROVISIONAL = "provisional"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class ResolutionSignal(StrEnum):
    EXACT_PLATFORM_ORDER_ID = "exact_platform_order_id"
    DUPLICATE_HISTORY_EVIDENCE = "duplicate_history_evidence"
    MULTIPLE_CORROBORATING_SOURCES = "multiple_corroborating_sources"
    SINGLE_MESSAGE_EVIDENCE = "single_message_evidence"
    NORMALIZED_TRADE_NAME = "normalized_trade_name"
    EXACT_LEGAL_IDENTIFIER = "exact_legal_identifier"
    EXACT_PLATFORM_MERCHANT_ID = "exact_platform_merchant_id"
    ADDRESS_MATCH = "address_match"
    ADDRESS_CONFLICT = "address_conflict"
    LEGAL_OWNER_CONFLICT = "legal_owner_conflict"
    SAME_NAME_ONLY = "same_name_only"


class OrderIdentityCandidate(ContractModel):
    candidate_id: UUID
    evidence_id: str = Field(min_length=1)
    message_id: str = Field(pattern=r"^msg_[0-9a-f]{16}$")
    document_ids: tuple[str, ...]
    agentic_region_ids: tuple[UUID, ...]
    platform: Platform
    category: OrderCategory
    evidence_kind: OrderEvidenceKind
    platform_order_id_private: str | None = Field(default=None, repr=False, pattern=r"^\d+$")
    provisional_fingerprint_private: str | None = Field(default=None, repr=False, min_length=1)

    @model_validator(mode="after")
    def identity_source_is_exclusive(self) -> OrderIdentityCandidate:
        if (self.platform_order_id_private is None) == (
            self.provisional_fingerprint_private is None
        ):
            raise ValueError("candidate requires exactly one resolved or provisional identity")
        return self


class AgenticOrderRegionReference(ContractModel):
    region_id: UUID
    source_ids: tuple[str, ...] = Field(min_length=1)
    order_ids_private: tuple[str, ...] = Field(default=(), repr=False)

    @model_validator(mode="after")
    def source_and_order_ids_are_well_formed(self) -> AgenticOrderRegionReference:
        if any(
            not source_id.startswith(("doc_", "msg_")) or len(source_id) != 20
            for source_id in self.source_ids
        ):
            raise ValueError("region source IDs must be document or message IDs")
        if any(not value.isdigit() for value in self.order_ids_private):
            raise ValueError("region order IDs must contain digits only")
        return self


class ResolutionDecision(ContractModel):
    resolution_id: UUID
    resolution_type: ResolutionType
    candidate_ids: tuple[UUID, ...] = Field(min_length=1)
    selected_candidate_id: UUID | None = None
    selected_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    second_candidate_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    decision_margin: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))
    positive_signals: tuple[ResolutionSignal, ...]
    negative_signals: tuple[ResolutionSignal, ...]
    policy_version: str = Field(min_length=1)
    status: ResolutionStatus
    decided_at: datetime

    @model_validator(mode="after")
    def decision_is_consistent(self) -> ResolutionDecision:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        if self.selected_candidate_id is not None and (
            self.selected_candidate_id not in self.candidate_ids
        ):
            raise ValueError("selected candidate must occur in candidate_ids")
        if self.decision_margin != self.selected_score - self.second_candidate_score:
            raise ValueError("decision_margin must equal selected minus second score")
        if set(self.positive_signals) & set(self.negative_signals):
            raise ValueError("a signal cannot be both positive and negative")
        return self


class OrderDocumentBundle(ContractModel):
    bundle_id: UUID
    order_id: UUID
    candidate_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    message_ids: tuple[str, ...] = Field(min_length=1)
    document_ids: tuple[str, ...]
    agentic_region_ids: tuple[UUID, ...]


class CanonicalOrder(ContractModel):
    order_id: UUID
    platform: Platform
    category: OrderCategory
    identity_status: OrderIdentityStatus
    platform_order_id_private: str | None = Field(default=None, repr=False, pattern=r"^\d+$")
    provisional_fingerprint_private: str | None = Field(default=None, repr=False, min_length=1)
    candidate_ids: tuple[UUID, ...] = Field(min_length=1)
    bundle_id: UUID
    resolution_id: UUID
    supersedes_order_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def identity_status_matches_source(self) -> CanonicalOrder:
        if self.identity_status is OrderIdentityStatus.RESOLVED:
            if self.platform_order_id_private is None or (
                self.provisional_fingerprint_private is not None
            ):
                raise ValueError("resolved order requires only a platform order ID")
        elif self.identity_status is OrderIdentityStatus.PROVISIONAL and (
            self.platform_order_id_private is not None
            or self.provisional_fingerprint_private is None
        ):
            raise ValueError("provisional order requires only a provisional fingerprint")
        return self


class OrderResolutionSummary(ContractModel):
    evidence_records: int = Field(ge=0)
    resolved_orders: int = Field(ge=0)
    provisional_orders: int = Field(ge=0)
    duplicate_evidence_records: int = Field(ge=0)
    total_orders: int = Field(ge=0)

    @model_validator(mode="after")
    def totals_are_consistent(self) -> OrderResolutionSummary:
        if self.total_orders != self.resolved_orders + self.provisional_orders:
            raise ValueError("total_orders must equal resolved plus provisional orders")
        if self.evidence_records != self.total_orders + self.duplicate_evidence_records:
            raise ValueError("evidence records must equal orders plus duplicate records")
        return self


class OrderResolutionArchive(ContractModel):
    policy_version: str = Field(min_length=1)
    candidates: tuple[OrderIdentityCandidate, ...]
    bundles: tuple[OrderDocumentBundle, ...]
    orders: tuple[CanonicalOrder, ...]
    decisions: tuple[ResolutionDecision, ...]
    summary: OrderResolutionSummary

    @model_validator(mode="after")
    def references_are_complete_and_reversible(self) -> OrderResolutionArchive:
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        if len(candidate_ids) != len(self.candidates):
            raise ValueError("candidate IDs must be unique")
        order_ids = {order.order_id for order in self.orders}
        bundle_by_id = {bundle.bundle_id: bundle for bundle in self.bundles}
        decision_by_id = {decision.resolution_id: decision for decision in self.decisions}
        if len(order_ids) != len(self.orders):
            raise ValueError("order IDs must be unique")
        if len(bundle_by_id) != len(self.bundles) or len(self.bundles) != len(self.orders):
            raise ValueError("every order requires one unique document bundle")
        if len(decision_by_id) != len(self.decisions) or len(self.decisions) != len(self.orders):
            raise ValueError("every order requires one unique resolution decision")

        referenced_candidates: list[UUID] = []
        for order in self.orders:
            bundle = bundle_by_id.get(order.bundle_id)
            decision = decision_by_id.get(order.resolution_id)
            if bundle is None or bundle.order_id != order.order_id:
                raise ValueError("order bundle reference is invalid")
            if decision is None or decision.resolution_type is not ResolutionType.ORDER:
                raise ValueError("order resolution reference is invalid")
            if order.candidate_ids != bundle.candidate_ids or (
                order.candidate_ids != decision.candidate_ids
            ):
                raise ValueError("order, bundle, and decision candidates must match")
            if not set(order.candidate_ids) <= candidate_ids:
                raise ValueError("order references an unknown candidate")
            referenced_candidates.extend(order.candidate_ids)
        if sorted(referenced_candidates) != sorted(candidate_ids):
            raise ValueError("every candidate must resolve into exactly one order")
        return self


def _candidate_id(evidence_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lunarbit-order-candidate-v1:{evidence_id}")


def _resolved_order_id(platform: Platform, private_order_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lunarbit-order-v1:{platform.value}:{private_order_id}")


def _provisional_order_id(platform: Platform, fingerprint: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lunarbit-provisional-order-v1:{platform.value}:{fingerprint}")


def _derived_id(namespace: str, values: Iterable[UUID]) -> UUID:
    identity = ",".join(sorted(str(value) for value in values))
    return uuid5(NAMESPACE_URL, f"{namespace}:{identity}")


def link_agentic_regions_to_order_evidence(
    messages: Iterable[SourceMessage],
    evidence_records: Iterable[OrderEvidence],
    regions: Iterable[AgenticOrderRegionReference],
) -> dict[str, tuple[UUID, ...]]:
    message_values = tuple(messages)
    evidence_values = tuple(evidence_records)
    region_values = tuple(regions)
    message_by_id = {message.message_id: message for message in message_values}
    if len(message_by_id) != len(message_values):
        raise ValueError("source message IDs must be unique")
    if len({region.region_id for region in region_values}) != len(region_values):
        raise ValueError("agentic region IDs must be unique")

    links: dict[str, tuple[UUID, ...]] = {}
    for evidence in sorted(evidence_values, key=lambda item: item.evidence_id):
        message = message_by_id.get(evidence.message_id)
        if message is None:
            raise ValueError("order evidence references an unknown source message")
        source_scope = {message.message_id, *message.attachment_document_ids}
        linked: list[UUID] = []
        for region in region_values:
            if not source_scope.intersection(region.source_ids):
                continue
            if evidence.kind is OrderEvidenceKind.HISTORY_ROW and (
                evidence.order_id_private not in region.order_ids_private
            ):
                continue
            linked.append(region.region_id)
        if not linked:
            raise ValueError(
                f"order evidence {evidence.evidence_id} has no agentic region provenance"
            )
        links[evidence.evidence_id] = tuple(sorted(linked, key=str))
    return links


def resolve_order_evidence(
    messages: Iterable[SourceMessage],
    documents: Iterable[SourceDocument],
    evidence_records: Iterable[OrderEvidence],
    *,
    decided_at: datetime,
    region_links_by_evidence_id: Mapping[str, Iterable[UUID]] | None = None,
) -> OrderResolutionArchive:
    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        raise ValueError("decided_at must be timezone-aware")
    message_values = tuple(messages)
    document_values = tuple(documents)
    evidence_values = tuple(evidence_records)
    message_by_id = {message.message_id: message for message in message_values}
    document_by_id = {document.document_id: document for document in document_values}
    if len(message_by_id) != len(message_values):
        raise ValueError("source message IDs must be unique")
    if len(document_by_id) != len(document_values):
        raise ValueError("source document IDs must be unique")
    if len({evidence.evidence_id for evidence in evidence_values}) != len(evidence_values):
        raise ValueError("order evidence IDs must be unique")

    for source_message in message_values:
        for document_id in source_message.attachment_document_ids:
            document = document_by_id.get(document_id)
            if document is None or document.message_id != source_message.message_id:
                raise ValueError("message references an unknown or foreign source document")
            if (
                document.platform is not source_message.platform
                or document.category is not source_message.category
            ):
                raise ValueError("document must match its message platform and category")

    supplied_region_links = region_links_by_evidence_id or {}
    unknown_region_evidence = set(supplied_region_links) - {
        evidence.evidence_id for evidence in evidence_values
    }
    if unknown_region_evidence:
        raise ValueError("agentic region links reference unknown order evidence")

    candidates: list[OrderIdentityCandidate] = []
    candidates_by_key: dict[tuple[str, str, str], list[OrderIdentityCandidate]] = defaultdict(list)
    evidence_by_candidate_id: dict[UUID, OrderEvidence] = {}
    for evidence in sorted(evidence_values, key=lambda item: item.evidence_id):
        message = message_by_id.get(evidence.message_id)
        if message is None:
            raise ValueError("order evidence references an unknown source message")
        if evidence.platform is not message.platform:
            raise ValueError("order evidence must match its message platform and category")
        provisional_fingerprint = message.message_id if evidence.order_id_private is None else None
        candidate = OrderIdentityCandidate(
            candidate_id=_candidate_id(evidence.evidence_id),
            evidence_id=evidence.evidence_id,
            message_id=message.message_id,
            document_ids=tuple(sorted(message.attachment_document_ids)),
            agentic_region_ids=tuple(
                sorted(set(supplied_region_links.get(evidence.evidence_id, ())), key=str)
            ),
            platform=evidence.platform,
            category=message.category,
            evidence_kind=evidence.kind,
            platform_order_id_private=evidence.order_id_private,
            provisional_fingerprint_private=provisional_fingerprint,
        )
        if evidence.order_id_private is not None:
            key = (evidence.platform.value, "resolved", evidence.order_id_private)
        else:
            key = (evidence.platform.value, "provisional", message.message_id)
        candidates.append(candidate)
        candidates_by_key[key].append(candidate)
        evidence_by_candidate_id[candidate.candidate_id] = evidence

    bundles: list[OrderDocumentBundle] = []
    orders: list[CanonicalOrder] = []
    decisions: list[ResolutionDecision] = []
    for key in sorted(candidates_by_key):
        group = tuple(sorted(candidates_by_key[key], key=lambda item: str(item.candidate_id)))
        platforms = {candidate.platform for candidate in group}
        categories = {candidate.category for candidate in group}
        if len(platforms) != 1 or len(categories) != 1:
            raise ValueError("resolved order candidates conflict on platform and category")
        platform = next(iter(platforms))
        category = next(iter(categories))
        candidate_ids = tuple(candidate.candidate_id for candidate in group)
        resolved = key[1] == "resolved"
        if resolved:
            private_order_id = key[2]
            provisional_fingerprint = None
            order_id = _resolved_order_id(platform, private_order_id)
            identity_status = OrderIdentityStatus.RESOLVED
            resolution_status = ResolutionStatus.RESOLVED
            selected_score = Decimal("1")
            signals = [ResolutionSignal.EXACT_PLATFORM_ORDER_ID]
            if len(group) > 1:
                signals.append(ResolutionSignal.MULTIPLE_CORROBORATING_SOURCES)
            if (
                any(
                    evidence_by_candidate_id[candidate.candidate_id].kind
                    is OrderEvidenceKind.HISTORY_ROW
                    for candidate in group
                )
                and len(group) > 1
            ):
                signals.append(ResolutionSignal.DUPLICATE_HISTORY_EVIDENCE)
        else:
            private_order_id = None
            provisional_fingerprint = key[2]
            order_id = _provisional_order_id(platform, provisional_fingerprint)
            identity_status = OrderIdentityStatus.PROVISIONAL
            resolution_status = ResolutionStatus.PROVISIONAL
            selected_score = Decimal("0.5")
            signals = [ResolutionSignal.SINGLE_MESSAGE_EVIDENCE]

        bundle_id = _derived_id("lunarbit-order-document-bundle-v1", (order_id, *candidate_ids))
        resolution_id = _derived_id("lunarbit-order-resolution-v1", candidate_ids)
        bundle = OrderDocumentBundle(
            bundle_id=bundle_id,
            order_id=order_id,
            candidate_ids=candidate_ids,
            evidence_ids=tuple(sorted(candidate.evidence_id for candidate in group)),
            message_ids=tuple(sorted({candidate.message_id for candidate in group})),
            document_ids=tuple(
                sorted({value for candidate in group for value in candidate.document_ids})
            ),
            agentic_region_ids=tuple(
                sorted(
                    {value for candidate in group for value in candidate.agentic_region_ids},
                    key=str,
                )
            ),
        )
        decision = ResolutionDecision(
            resolution_id=resolution_id,
            resolution_type=ResolutionType.ORDER,
            candidate_ids=candidate_ids,
            selected_candidate_id=candidate_ids[0],
            selected_score=selected_score,
            second_candidate_score=Decimal("0"),
            decision_margin=selected_score,
            positive_signals=tuple(signals),
            negative_signals=(),
            policy_version=ORDER_RESOLUTION_POLICY_VERSION,
            status=resolution_status,
            decided_at=decided_at,
        )
        order = CanonicalOrder(
            order_id=order_id,
            platform=platform,
            category=category,
            identity_status=identity_status,
            platform_order_id_private=private_order_id,
            provisional_fingerprint_private=provisional_fingerprint,
            candidate_ids=candidate_ids,
            bundle_id=bundle_id,
            resolution_id=resolution_id,
        )
        bundles.append(bundle)
        decisions.append(decision)
        orders.append(order)

    orders.sort(key=lambda order: str(order.order_id))
    bundles.sort(key=lambda bundle: str(bundle.order_id))
    decisions.sort(key=lambda decision: str(decision.resolution_id))
    resolved_orders = sum(order.identity_status is OrderIdentityStatus.RESOLVED for order in orders)
    provisional_orders = sum(
        order.identity_status is OrderIdentityStatus.PROVISIONAL for order in orders
    )
    return OrderResolutionArchive(
        policy_version=ORDER_RESOLUTION_POLICY_VERSION,
        candidates=tuple(sorted(candidates, key=lambda candidate: str(candidate.candidate_id))),
        bundles=tuple(bundles),
        orders=tuple(orders),
        decisions=tuple(decisions),
        summary=OrderResolutionSummary(
            evidence_records=len(candidates),
            resolved_orders=resolved_orders,
            provisional_orders=provisional_orders,
            duplicate_evidence_records=len(candidates) - len(orders),
            total_orders=len(orders),
        ),
    )


def public_order_id(
    *,
    order_id: UUID,
    platform: Platform,
    private_order_id: str,
    key: bytes,
) -> str:
    if len(key) < 32:
        raise ValueError("public identifier key must contain at least 32 bytes")
    payload = f"lunarbit-public-order-v1:{platform.value}:{order_id}:{private_order_id}".encode()
    digest = hmac.new(key, payload, sha256).hexdigest()[:12].upper()
    platform_code = "ZM" if platform is Platform.ZOMATO else "SW"
    return f"ORD-{platform_code}-{digest}"
