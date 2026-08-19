from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.finance import (
    FinancialComponentType,
    MoneyComponent,
    ReconciliationStatus,
)
from lunarbit.models import ContractModel, DocumentRole

BUNDLE_RECONCILIATION_VERSION = "transaction-bundle-reconciliation-v1.0.0"

_DISCOUNTS = {
    FinancialComponentType.ITEM_DISCOUNT,
    FinancialComponentType.COUPON_DISCOUNT,
    FinancialComponentType.MEMBERSHIP_BENEFIT,
}
_TOTALS = {
    FinancialComponentType.CUSTOMER_TOTAL,
    FinancialComponentType.INVOICE_TOTAL,
}
_NON_CALCULATION = _TOTALS | {
    FinancialComponentType.PAYMENT_ASSERTION,
    FinancialComponentType.REFUND,
    FinancialComponentType.SUBTOTAL,
    FinancialComponentType.UNRESOLVED,
    FinancialComponentType.UNEXPLAINED_DISCOUNT_RESIDUAL,
    FinancialComponentType.UNEXPLAINED_FINANCIAL_RESIDUAL,
}
_MERCHANT_ROLES = {
    DocumentRole.ZOMATO_MERCHANT_INVOICE,
    DocumentRole.SWIGGY_RESTAURANT_INVOICE,
    DocumentRole.SWIGGY_INSTAMART_SELLER_INVOICE,
}
_PLATFORM_ROLES = {
    DocumentRole.ZOMATO_PLATFORM_FEE_INVOICE,
    DocumentRole.SWIGGY_PLATFORM_FEE_INVOICE,
}
_DELIVERY_ROLES = {
    DocumentRole.ZOMATO_DELIVERY_SERVICE_INVOICE,
}
_SUMMARY_ROLES = {
    DocumentRole.ZOMATO_ORDER_SUMMARY,
    DocumentRole.SWIGGY_ORDER_HISTORY_REPORT,
}


class AuthorityDecision(ContractModel):
    component_type: FinancialComponentType
    selected_role: DocumentRole
    selected_component_ids: tuple[UUID, ...] = Field(min_length=1)
    rejected_component_ids: tuple[UUID, ...]


class BundleReconciliationRun(ContractModel):
    reconciliation_id: UUID
    order_id: UUID
    selected_component_ids: tuple[UUID, ...] = Field(min_length=1)
    rejected_component_ids: tuple[UUID, ...]
    source_ids: tuple[str, ...] = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    formula: str = Field(min_length=1)
    expected_amount: Decimal | None
    calculated_amount: Decimal | None
    residual: Decimal | None
    tolerance: Decimal = Field(ge=Decimal("0"))
    status: ReconciliationStatus
    authority_decisions: tuple[AuthorityDecision, ...]
    assumptions: tuple[str, ...]
    algorithm_version: str = BUNDLE_RECONCILIATION_VERSION
    executed_at: datetime

    @model_validator(mode="after")
    def arithmetic_and_execution_time_are_valid(self) -> BundleReconciliationRun:
        if self.executed_at.tzinfo is None or self.executed_at.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        if (
            self.expected_amount is not None
            and self.calculated_amount is not None
            and self.residual is not None
        ):
            if self.expected_amount - self.calculated_amount != self.residual:
                raise ValueError("bundle residual must be exact Decimal subtraction")
        elif any(
            value is not None
            for value in (self.expected_amount, self.calculated_amount, self.residual)
        ):
            raise ValueError("partial bundle arithmetic must remain entirely unknown")
        if set(self.selected_component_ids) & set(self.rejected_component_ids):
            raise ValueError("a component cannot be both selected and rejected")
        return self


def _authority(component_type: FinancialComponentType, role: DocumentRole) -> int:
    if component_type in {
        FinancialComponentType.ITEM_GROSS,
        FinancialComponentType.ITEM_NET,
        FinancialComponentType.ITEM_DISCOUNT,
        FinancialComponentType.PACKING_CHARGE,
        FinancialComponentType.TAX,
        FinancialComponentType.CGST,
        FinancialComponentType.SGST,
        FinancialComponentType.IGST,
        FinancialComponentType.CESS,
    }:
        return 100 if role in _MERCHANT_ROLES else 60 if role in _SUMMARY_ROLES else 30
    if component_type in {
        FinancialComponentType.PLATFORM_FEE,
        FinancialComponentType.HANDLING_FEE,
        FinancialComponentType.MEMBERSHIP_BENEFIT,
    }:
        return 100 if role in _PLATFORM_ROLES else 80 if role in _SUMMARY_ROLES else 30
    if component_type is FinancialComponentType.DELIVERY_CHARGE:
        return 100 if role in _DELIVERY_ROLES else 80 if role in _SUMMARY_ROLES else 40
    if component_type in _TOTALS:
        if role is DocumentRole.ZOMATO_ORDER_SUMMARY:
            return 100
        if role is DocumentRole.SWIGGY_ORDER_HISTORY_REPORT:
            return 95
        if role in _MERCHANT_ROLES:
            return 70
        return 40
    if component_type is FinancialComponentType.COUPON_DISCOUNT:
        return 100 if role in _SUMMARY_ROLES else 80 if role in _PLATFORM_ROLES else 40
    return 50


def _status(residual: Decimal, tolerance: Decimal) -> ReconciliationStatus:
    absolute = abs(residual)
    if residual == 0:
        return ReconciliationStatus.EXACT
    if absolute <= tolerance:
        return ReconciliationStatus.WITHIN_SOURCE_PRECISION
    if absolute <= Decimal("0.05"):
        return ReconciliationStatus.WITHIN_ROUNDING
    return ReconciliationStatus.CONFLICTING


def reconcile_transaction_bundle(
    components: Iterable[MoneyComponent],
    *,
    document_roles: Mapping[str, DocumentRole],
    executed_at: datetime,
) -> BundleReconciliationRun:
    values = tuple(components)
    if not values:
        raise ValueError("transaction-bundle reconciliation requires components")
    if executed_at.tzinfo is None or executed_at.utcoffset() is None:
        raise ValueError("executed_at must be timezone-aware")
    currencies = {component.currency for component in values}
    if len(currencies) != 1:
        raise ValueError("transaction-bundle reconciliation cannot mix currency")
    order_sets = {component.order_ids for component in values}
    if len(order_sets) != 1 or len(next(iter(order_sets))) != 1:
        raise ValueError("transaction-bundle reconciliation requires exactly one common order")
    missing_roles = {component.source_id for component in values} - set(document_roles)
    if missing_roles:
        raise ValueError("every source document requires a declared document role")
    by_type: dict[FinancialComponentType, list[MoneyComponent]] = defaultdict(list)
    for component in values:
        by_type[component.component_type].append(component)
    selected_calculation: list[MoneyComponent] = []
    rejected: set[UUID] = set()
    decisions: list[AuthorityDecision] = []
    for component_type, candidates in sorted(by_type.items(), key=lambda item: item[0].value):
        if component_type in _NON_CALCULATION:
            continue
        maximum = max(
            _authority(component_type, document_roles[item.source_id]) for item in candidates
        )
        chosen = tuple(
            item
            for item in candidates
            if _authority(component_type, document_roles[item.source_id]) == maximum
        )
        rejected_values = tuple(item for item in candidates if item not in chosen)
        selected_calculation.extend(chosen)
        rejected.update(item.component_id for item in rejected_values)
        decisions.append(
            AuthorityDecision(
                component_type=component_type,
                selected_role=document_roles[chosen[0].source_id],
                selected_component_ids=tuple(item.component_id for item in chosen),
                rejected_component_ids=tuple(item.component_id for item in rejected_values),
            )
        )
    total_candidates = tuple(
        component for component in values if component.component_type in _TOTALS
    )
    selected_total: MoneyComponent | None = None
    if total_candidates:
        maximum = max(
            _authority(component.component_type, document_roles[component.source_id])
            for component in total_candidates
        )
        authoritative = tuple(
            component
            for component in total_candidates
            if _authority(component.component_type, document_roles[component.source_id]) == maximum
        )
        if len({component.amount for component in authoritative}) == 1:
            selected_total = authoritative[0]
            rejected.update(
                component.component_id
                for component in total_candidates
                if component.component_id != selected_total.component_id
            )
            decisions.append(
                AuthorityDecision(
                    component_type=selected_total.component_type,
                    selected_role=document_roles[selected_total.source_id],
                    selected_component_ids=(selected_total.component_id,),
                    rejected_component_ids=tuple(
                        component.component_id
                        for component in total_candidates
                        if component.component_id != selected_total.component_id
                    ),
                )
            )
    tolerance = Decimal(1).scaleb(-max(component.source_precision for component in values))
    if selected_total is None or not selected_calculation:
        expected: Decimal | None = None
        calculated: Decimal | None = None
        residual: Decimal | None = None
        status = (
            ReconciliationStatus.CONFLICTING
            if total_candidates and selected_total is None
            else ReconciliationStatus.PARTIAL
        )
        formula = "insufficient authoritative components for bundle closure"
    else:
        expected = selected_total.amount
        calculated = sum(
            (
                -component.amount if component.component_type in _DISCOUNTS else component.amount
                for component in selected_calculation
            ),
            start=Decimal("0"),
        )
        residual = expected - calculated
        status = _status(residual, tolerance)
        positive = [
            component.component_type.name
            for component in selected_calculation
            if component.component_type not in _DISCOUNTS
        ]
        discounts = [
            component.component_type.name
            for component in selected_calculation
            if component.component_type in _DISCOUNTS
        ]
        formula = " + ".join(positive)
        if discounts:
            formula += " - " + " - ".join(discounts)
        formula += f" = {selected_total.component_type.name}"
    selected_set = {component.component_id for component in selected_calculation} | (
        {selected_total.component_id} if selected_total is not None else set()
    )
    rejected.update(
        component.component_id for component in values if component.component_id not in selected_set
    )
    selected_ids = tuple(
        component.component_id for component in values if component.component_id in selected_set
    )
    rejected_ids = tuple(
        component.component_id for component in values if component.component_id in rejected
    )
    order_id = values[0].order_ids[0]
    identity = ",".join(sorted(str(value) for value in selected_ids + rejected_ids))
    reconciliation_id = uuid5(
        NAMESPACE_URL,
        f"lunarbit-bundle-reconciliation-v1:{order_id}:{identity}",
    )
    return BundleReconciliationRun(
        reconciliation_id=reconciliation_id,
        order_id=order_id,
        selected_component_ids=selected_ids,
        rejected_component_ids=rejected_ids,
        source_ids=tuple(sorted({component.source_id for component in values})),
        currency=next(iter(currencies)),
        formula=formula,
        expected_amount=expected,
        calculated_amount=calculated,
        residual=residual,
        tolerance=tolerance,
        status=status,
        authority_decisions=tuple(decisions),
        assumptions=(
            "document-role authority is fact-family specific",
            "discount and membership components subtract from customer payable",
            "payment and refund assertions do not prove bank settlement",
        ),
        executed_at=executed_at,
    )
