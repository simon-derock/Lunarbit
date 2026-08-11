from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from lunarbit.agentic import AgenticMoneyInterpretation, AgenticMoneyMeaning
from lunarbit.models import CandidateMoneyComponent, CandidateMoneyType, ContractModel

FINANCE_POLICY_VERSION = "financial-truth-v1.0.0"


class TruthScope(StrEnum):
    DOCUMENT_ASSERTED = "document_asserted"
    CROSS_DOCUMENT_DERIVED = "cross_document_derived"
    PAYMENT_EVIDENCED = "payment_evidenced"
    BANK_CONFIRMED = "bank_confirmed"
    USER_CONFIRMED = "user_confirmed"


class EpistemicMode(StrEnum):
    OBSERVED = "observed"
    NORMALIZED = "normalized"
    RESOLVED = "resolved"
    CALCULATED = "calculated"
    INFERRED = "inferred"
    SIMULATED = "simulated"


class FinancialScope(StrEnum):
    ORDER = "order"
    MERCHANT_INVOICE = "merchant_invoice"
    PLATFORM_SERVICE_INVOICE = "platform_service_invoice"
    DELIVERY_SERVICE_INVOICE = "delivery_service_invoice"
    ITEM = "item"
    PAYMENT = "payment"
    REFUND = "refund"
    UNKNOWN = "unknown"


class FinancialComponentType(StrEnum):
    ITEM_GROSS = "item_gross"
    ITEM_DISCOUNT = "item_discount"
    ITEM_NET = "item_net"
    SUBTOTAL = "subtotal"
    PACKING_CHARGE = "packing_charge"
    HANDLING_FEE = "handling_fee"
    DELIVERY_CHARGE = "delivery_charge"
    PLATFORM_FEE = "platform_fee"
    OTHER_CHARGE = "other_charge"
    CGST = "cgst"
    SGST = "sgst"
    IGST = "igst"
    CESS = "cess"
    TAX = "tax"
    COUPON_DISCOUNT = "coupon_discount"
    MEMBERSHIP_BENEFIT = "membership_benefit"
    INVOICE_TOTAL = "invoice_total"
    CUSTOMER_TOTAL = "customer_total"
    PAYMENT_ASSERTION = "payment_assertion"
    REFUND = "refund"
    ROUNDING_ADJUSTMENT = "rounding_adjustment"
    UNRESOLVED = "unresolved"
    UNEXPLAINED_DISCOUNT_RESIDUAL = "unexplained_discount_residual"
    UNEXPLAINED_FINANCIAL_RESIDUAL = "unexplained_financial_residual"


class FundingStatus(StrEnum):
    MERCHANT_OBSERVED = "merchant_observed"
    PLATFORM_OBSERVED = "platform_observed"
    EXTERNAL_OBSERVED = "external_observed"
    MIXED_OBSERVED = "mixed_observed"
    CONSISTENT_WITH_PLATFORM_FUNDING = "consistent_with_platform_funding"
    PROBABLE_PLATFORM_FUNDING = "probable_platform_funding"
    UNRESOLVED = "unresolved"


class ReconciliationStatus(StrEnum):
    EXACT = "exact"
    WITHIN_SOURCE_PRECISION = "within_source_precision"
    WITHIN_ROUNDING = "within_rounding"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"


class MoneyComponent(ContractModel):
    component_id: UUID
    source_component_id: UUID
    order_ids: tuple[UUID, ...]
    component_type: FinancialComponentType
    amount: Decimal
    source_amount_string_private: str = Field(repr=False, min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_precision: int = Field(ge=0)
    scope: FinancialScope
    epistemic_mode: EpistemicMode
    truth_scope: TruthScope
    funding_status: FundingStatus
    source_id: str = Field(pattern=r"^(?:doc|msg)_[0-9a-f]{16}$")
    source_chunk_id: UUID

    @model_validator(mode="after")
    def source_amount_is_preserved(self) -> MoneyComponent:
        try:
            parsed = Decimal(self.source_amount_string_private.replace(",", ""))
        except InvalidOperation as error:
            raise ValueError("source amount string must remain Decimal-readable") from error
        if parsed != self.amount:
            raise ValueError("normalized amount must equal its source amount string")
        return self


class ReconciliationRun(ContractModel):
    reconciliation_id: UUID
    component_ids: tuple[UUID, ...] = Field(min_length=2)
    scope: FinancialScope
    source_id: str = Field(pattern=r"^(?:doc|msg)_[0-9a-f]{16}$")
    formula: str = Field(min_length=1)
    expected_amount: Decimal
    calculated_amount: Decimal
    residual: Decimal
    tolerance: Decimal = Field(ge=Decimal("0"))
    explained_value_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    status: ReconciliationStatus
    assumptions: tuple[str, ...]
    algorithm_version: str = Field(min_length=1)
    executed_at: datetime

    @model_validator(mode="after")
    def arithmetic_and_time_are_valid(self) -> ReconciliationRun:
        if self.expected_amount - self.calculated_amount != self.residual:
            raise ValueError("reconciliation residual must be exact Decimal subtraction")
        if self.executed_at.tzinfo is None or self.executed_at.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return self


class FinancialArchiveSummary(ContractModel):
    money_components: int = Field(ge=0)
    assigned_order_components: int = Field(ge=0)
    unassigned_order_components: int = Field(ge=0)
    reconciliation_runs: int = Field(ge=0)
    exact_reconciliations: int = Field(ge=0)
    conflicting_reconciliations: int = Field(ge=0)


class FinancialArchive(ContractModel):
    policy_version: str = Field(min_length=1)
    components: tuple[MoneyComponent, ...]
    reconciliation_runs: tuple[ReconciliationRun, ...]
    summary: FinancialArchiveSummary

    @model_validator(mode="after")
    def components_are_unique(self) -> FinancialArchive:
        if len({item.component_id for item in self.components}) != len(self.components):
            raise ValueError("canonical money component IDs must be unique")
        source_ids = [item.source_component_id for item in self.components]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("every source money component must normalize exactly once")
        known_ids = {item.component_id for item in self.components}
        if any(not set(run.component_ids) <= known_ids for run in self.reconciliation_runs):
            raise ValueError("reconciliation references an unknown money component")
        return self


_CHARGE_TYPE_MAP = {
    CandidateMoneyType.PACKING_CHARGE: FinancialComponentType.PACKING_CHARGE,
    CandidateMoneyType.HANDLING_FEE: FinancialComponentType.HANDLING_FEE,
    CandidateMoneyType.DELIVERY_CHARGE: FinancialComponentType.DELIVERY_CHARGE,
    CandidateMoneyType.PLATFORM_FEE: FinancialComponentType.PLATFORM_FEE,
}


def normalize_money_component(
    source: CandidateMoneyComponent,
    interpretation: AgenticMoneyInterpretation,
    *,
    source_id: str,
    order_ids: tuple[UUID, ...],
) -> MoneyComponent:
    meaning = interpretation.money_meaning
    if meaning is AgenticMoneyMeaning.ITEM_GROSS:
        component_type = FinancialComponentType.ITEM_GROSS
    elif meaning is AgenticMoneyMeaning.ITEM_NET:
        component_type = FinancialComponentType.ITEM_NET
    elif meaning is AgenticMoneyMeaning.SUBTOTAL:
        component_type = FinancialComponentType.SUBTOTAL
    elif meaning is AgenticMoneyMeaning.CHARGE:
        component_type = _CHARGE_TYPE_MAP.get(
            source.component_type, FinancialComponentType.OTHER_CHARGE
        )
    elif meaning is AgenticMoneyMeaning.DISCOUNT:
        component_type = FinancialComponentType.COUPON_DISCOUNT
    elif meaning is AgenticMoneyMeaning.BENEFIT:
        component_type = FinancialComponentType.MEMBERSHIP_BENEFIT
    elif meaning is AgenticMoneyMeaning.TAX:
        component_type = FinancialComponentType.TAX
    elif meaning is AgenticMoneyMeaning.TOTAL:
        component_type = (
            FinancialComponentType.CUSTOMER_TOTAL
            if interpretation.money_scope.value == FinancialScope.ORDER.value
            else FinancialComponentType.INVOICE_TOTAL
        )
    elif meaning is AgenticMoneyMeaning.PAYMENT_ASSERTION:
        component_type = FinancialComponentType.PAYMENT_ASSERTION
    elif meaning is AgenticMoneyMeaning.REFUND:
        component_type = FinancialComponentType.REFUND
    else:
        component_type = FinancialComponentType.UNRESOLVED
    component_id = uuid5(
        NAMESPACE_URL,
        f"lunarbit-money-component-v1:{source.component_id}:"
        f"{interpretation.money_scope.value}:{meaning.value}",
    )
    return MoneyComponent(
        component_id=component_id,
        source_component_id=source.component_id,
        order_ids=tuple(sorted(set(order_ids), key=str)),
        component_type=component_type,
        amount=source.amount,
        source_amount_string_private=source.source_amount_string_private,
        currency=source.currency,
        source_precision=source.source_precision,
        scope=FinancialScope(interpretation.money_scope.value),
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        funding_status=FundingStatus.UNRESOLVED,
        source_id=source_id,
        source_chunk_id=interpretation.source_chunk_id,
    )


_DISCOUNT_TYPES = {
    FinancialComponentType.ITEM_DISCOUNT,
    FinancialComponentType.COUPON_DISCOUNT,
    FinancialComponentType.MEMBERSHIP_BENEFIT,
}
_EXCLUDED_CALCULATION_TYPES = {
    FinancialComponentType.INVOICE_TOTAL,
    FinancialComponentType.CUSTOMER_TOTAL,
    FinancialComponentType.PAYMENT_ASSERTION,
    FinancialComponentType.REFUND,
    FinancialComponentType.SUBTOTAL,
    FinancialComponentType.UNRESOLVED,
}


def reconcile_document_scope(
    components: Iterable[MoneyComponent],
    *,
    executed_at: datetime,
) -> ReconciliationRun | None:
    values = tuple(components)
    if len(values) < 2:
        return None
    if executed_at.tzinfo is None or executed_at.utcoffset() is None:
        raise ValueError("executed_at must be timezone-aware")
    scopes = {component.scope for component in values}
    source_ids = {component.source_id for component in values}
    currencies = {component.currency for component in values}
    if len(scopes) != 1 or len(source_ids) != 1 or len(currencies) != 1:
        raise ValueError("document reconciliation cannot mix source, scope, or currency")
    totals = tuple(
        component
        for component in values
        if component.component_type
        in {FinancialComponentType.INVOICE_TOTAL, FinancialComponentType.CUSTOMER_TOTAL}
    )
    if len(totals) != 1:
        return None
    calculation_components = tuple(
        component
        for component in values
        if component.component_type not in _EXCLUDED_CALCULATION_TYPES
    )
    if not calculation_components:
        return None
    calculated = sum(
        (
            -component.amount if component.component_type in _DISCOUNT_TYPES else component.amount
            for component in calculation_components
        ),
        start=Decimal("0"),
    )
    expected = totals[0].amount
    residual = expected - calculated
    tolerance = Decimal(1).scaleb(-max(component.source_precision for component in values))
    absolute_residual = abs(residual)
    if residual == 0:
        status = ReconciliationStatus.EXACT
    elif absolute_residual <= tolerance:
        status = ReconciliationStatus.WITHIN_SOURCE_PRECISION
    elif absolute_residual <= Decimal("0.05"):
        status = ReconciliationStatus.WITHIN_ROUNDING
    else:
        status = ReconciliationStatus.CONFLICTING
    positive_names = [
        component.component_type.name
        for component in calculation_components
        if component.component_type not in _DISCOUNT_TYPES
    ]
    discount_names = [
        component.component_type.name
        for component in calculation_components
        if component.component_type in _DISCOUNT_TYPES
    ]
    formula = " + ".join(positive_names)
    if discount_names:
        formula += " - " + " - ".join(discount_names)
    formula += f" = {totals[0].component_type.name}"
    explained_ratio = (
        Decimal("1")
        if expected == 0 and residual == 0
        else max(Decimal("0"), Decimal("1") - absolute_residual / abs(expected))
        if expected != 0
        else Decimal("0")
    )
    component_ids = tuple(component.component_id for component in values)
    reconciliation_id = uuid5(
        NAMESPACE_URL,
        "lunarbit-document-reconciliation-v1:"
        + ",".join(sorted(str(component_id) for component_id in component_ids)),
    )
    return ReconciliationRun(
        reconciliation_id=reconciliation_id,
        component_ids=component_ids,
        scope=values[0].scope,
        source_id=values[0].source_id,
        formula=formula,
        expected_amount=expected,
        calculated_amount=calculated,
        residual=residual,
        tolerance=tolerance,
        explained_value_ratio=explained_ratio,
        status=status,
        assumptions=("component signs follow the governed financial type policy",),
        algorithm_version=FINANCE_POLICY_VERSION,
        executed_at=executed_at,
    )
