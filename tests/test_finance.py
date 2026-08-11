from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from lunarbit.finance import (
    EpistemicMode,
    FinancialComponentType,
    FinancialScope,
    FundingStatus,
    MoneyComponent,
    ReconciliationStatus,
    TruthScope,
    reconcile_document_scope,
)


def _component(
    suffix: int,
    component_type: FinancialComponentType,
    amount: str,
) -> MoneyComponent:
    return MoneyComponent(
        component_id=UUID(f"10000000-0000-0000-0000-{suffix:012d}"),
        source_component_id=UUID(f"20000000-0000-0000-0000-{suffix:012d}"),
        order_ids=(UUID("30000000-0000-0000-0000-000000000001"),),
        component_type=component_type,
        amount=Decimal(amount),
        source_amount_string_private=amount,
        currency="INR",
        source_precision=2,
        scope=FinancialScope.MERCHANT_INVOICE,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        funding_status=FundingStatus.UNRESOLVED,
        source_id="doc_0000000000000001",
        source_chunk_id=UUID(f"40000000-0000-0000-0000-{suffix:012d}"),
    )


def test_document_reconciliation_uses_decimal_and_preserves_financial_scope() -> None:
    components = (
        _component(1, FinancialComponentType.ITEM_GROSS, "100.00"),
        _component(2, FinancialComponentType.PACKING_CHARGE, "10.00"),
        _component(3, FinancialComponentType.COUPON_DISCOUNT, "20.00"),
        _component(4, FinancialComponentType.INVOICE_TOTAL, "90.00"),
    )

    run = reconcile_document_scope(
        components,
        executed_at=datetime(2026, 8, 11, tzinfo=UTC),
    )

    assert run is not None
    assert run.expected_amount == Decimal("90.00")
    assert run.calculated_amount == Decimal("90.00")
    assert run.residual == Decimal("0.00")
    assert run.status is ReconciliationStatus.EXACT
    assert run.component_ids == tuple(component.component_id for component in components)
    assert "ITEM_GROSS + PACKING_CHARGE - COUPON_DISCOUNT" in run.formula


def test_payment_assertions_remain_document_claims_not_bank_confirmation() -> None:
    payment = _component(1, FinancialComponentType.PAYMENT_ASSERTION, "90.00")

    assert payment.truth_scope is TruthScope.DOCUMENT_ASSERTED
    assert payment.epistemic_mode is EpistemicMode.OBSERVED
    assert TruthScope.BANK_CONFIRMED is not payment.truth_scope
