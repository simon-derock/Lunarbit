from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.models import CandidateMoneyType, ChunkType, ContractModel, EvidenceChunk

PRODUCT_RESOLUTION_POLICY_VERSION = "product-resolution-v1.0.0"
_NAME_HEADERS = ("particular", "item", "product", "description", "name")
_NON_ITEM_LABEL = re.compile(
    r"\b(?:sub\s*total|grand\s+total|total|fee|charge|tax|cgst|sgst|igst|discount|"
    r"delivery|packing|packaging|handling|platform|invoice|round\s*off)\b",
    re.IGNORECASE,
)
_NUMBER_ONLY = re.compile(r"^(?:₹|INR|Rs\.?)?\s*-?\d[\d,]*(?:\.\d+)?$", re.IGNORECASE)


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def item_name_from_table_row(
    raw_text_private: str,
    column_headers_private: tuple[str, ...],
) -> str | None:
    cells = tuple(value.strip() for value in raw_text_private.split(" | "))
    named_indexes = tuple(
        index
        for index, header in enumerate(column_headers_private)
        if any(token in header.casefold() for token in _NAME_HEADERS)
    )
    if named_indexes:
        candidates = tuple(cells[index] for index in named_indexes if index < len(cells))
    else:
        candidates = tuple(
            value
            for value in cells
            if re.search(r"[A-Za-z]", value) and not _NUMBER_ONLY.fullmatch(value)
        )
    for value in candidates:
        cleaned = " ".join(value.split()).strip(" -:|")
        if len(cleaned) >= 2 and not _NON_ITEM_LABEL.search(cleaned):
            return cleaned
    return None


class ItemEvidenceObservation(ContractModel):
    observation_id: UUID
    order_id: UUID
    merchant_id: UUID | None = None
    source_chunk_id: UUID
    source_component_id: UUID
    raw_name_private: str = Field(repr=False, min_length=1)
    normalized_name_private: str = Field(repr=False, min_length=1)
    observed_amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_precision: int = Field(ge=0)


class MerchantItem(ContractModel):
    merchant_item_id: UUID
    merchant_id: UUID | None = None
    provisional_order_scope_id: UUID | None = None
    display_name_private: str = Field(repr=False, min_length=1)
    normalized_name_private: str = Field(repr=False, min_length=1)
    alias_names_private: tuple[str, ...] = Field(repr=False, min_length=1)
    observation_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identity_scope_is_exclusive(self) -> MerchantItem:
        if (self.merchant_id is None) == (self.provisional_order_scope_id is None):
            raise ValueError("merchant item requires one merchant or provisional order scope")
        return self


class CanonicalItem(ContractModel):
    canonical_item_id: UUID
    canonical_name_private: str = Field(repr=False, min_length=1)
    merchant_item_ids: tuple[UUID, ...] = Field(min_length=1)
    review_status: str = Field(min_length=1)


class ComparableItemGroup(ContractModel):
    group_id: UUID
    merchant_item_ids: tuple[UUID, ...] = Field(min_length=2)
    comparison_method: str = Field(min_length=1)
    outlet_constraint: str = Field(min_length=1)
    package_constraint: str = Field(min_length=1)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    review_status: str = Field(min_length=1)


class ProductResolutionSummary(ContractModel):
    item_observations: int = Field(ge=0)
    merchant_items: int = Field(ge=0)
    canonical_items: int = Field(ge=0)
    comparable_item_groups: int = Field(ge=0)


class ProductResolutionArchive(ContractModel):
    policy_version: str = Field(min_length=1)
    observations: tuple[ItemEvidenceObservation, ...]
    merchant_items: tuple[MerchantItem, ...]
    canonical_items: tuple[CanonicalItem, ...]
    comparable_item_groups: tuple[ComparableItemGroup, ...]
    summary: ProductResolutionSummary

    @model_validator(mode="after")
    def observation_coverage_is_exact(self) -> ProductResolutionArchive:
        observation_ids = {item.observation_id for item in self.observations}
        if len(observation_ids) != len(self.observations):
            raise ValueError("item observation IDs must be unique")
        grouped_ids = [
            observation_id
            for merchant_item in self.merchant_items
            for observation_id in merchant_item.observation_ids
        ]
        if sorted(grouped_ids) != sorted(observation_ids):
            raise ValueError("every observation must belong to exactly one merchant item")
        return self


def item_observation_from_chunk(
    chunk: EvidenceChunk,
    *,
    order_id: UUID,
    merchant_id: UUID | None,
) -> ItemEvidenceObservation | None:
    if chunk.chunk_type is not ChunkType.ITEM_ROW:
        return None
    components = tuple(
        component
        for component in chunk.candidate_money_components
        if component.component_type is CandidateMoneyType.ITEM_AMOUNT
    )
    if len(components) != 1:
        return None
    raw_name = item_name_from_table_row(
        chunk.raw_text_private,
        chunk.column_headers_private,
    )
    if raw_name is None:
        return None
    component = components[0]
    observation_id = uuid5(
        NAMESPACE_URL,
        f"lunarbit-item-observation-v1:{order_id}:{chunk.chunk_id}:{component.component_id}",
    )
    return ItemEvidenceObservation(
        observation_id=observation_id,
        order_id=order_id,
        merchant_id=merchant_id,
        source_chunk_id=chunk.chunk_id,
        source_component_id=component.component_id,
        raw_name_private=raw_name,
        normalized_name_private=_normalize(raw_name),
        observed_amount=component.amount,
        currency=component.currency,
        source_precision=component.source_precision,
    )


def _preferred_name(values: Iterable[str]) -> tuple[str, tuple[str, ...]]:
    aliases = tuple(sorted(set(values), key=lambda value: (value.casefold(), value)))
    counts = Counter(values)
    return min(aliases, key=lambda value: (-counts[value], value.casefold(), value)), aliases


def resolve_item_observations(
    observations: Iterable[ItemEvidenceObservation],
) -> ProductResolutionArchive:
    values = tuple(sorted(observations, key=lambda item: str(item.observation_id)))
    if len({item.observation_id for item in values}) != len(values):
        raise ValueError("item observation IDs must be unique")
    groups: dict[tuple[str, str], list[ItemEvidenceObservation]] = defaultdict(list)
    for observation in values:
        scope = (
            f"merchant:{observation.merchant_id}"
            if observation.merchant_id is not None
            else f"order:{observation.order_id}"
        )
        groups[(scope, observation.normalized_name_private)].append(observation)

    merchant_items: list[MerchantItem] = []
    for key in sorted(groups):
        group = tuple(sorted(groups[key], key=lambda item: str(item.observation_id)))
        first = group[0]
        display_name, aliases = _preferred_name(item.raw_name_private for item in group)
        merchant_item_id = uuid5(
            NAMESPACE_URL,
            f"lunarbit-merchant-item-v1:{key[0]}:{key[1]}",
        )
        merchant_items.append(
            MerchantItem(
                merchant_item_id=merchant_item_id,
                merchant_id=first.merchant_id,
                provisional_order_scope_id=(first.order_id if first.merchant_id is None else None),
                display_name_private=display_name,
                normalized_name_private=first.normalized_name_private,
                alias_names_private=aliases,
                observation_ids=tuple(item.observation_id for item in group),
            )
        )
    merchant_items.sort(key=lambda item: str(item.merchant_item_id))
    return ProductResolutionArchive(
        policy_version=PRODUCT_RESOLUTION_POLICY_VERSION,
        observations=values,
        merchant_items=tuple(merchant_items),
        canonical_items=(),
        comparable_item_groups=(),
        summary=ProductResolutionSummary(
            item_observations=len(values),
            merchant_items=len(merchant_items),
            canonical_items=0,
            comparable_item_groups=0,
        ),
    )
