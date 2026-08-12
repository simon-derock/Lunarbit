from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from lunarbit.bundle_reconciliation import reconcile_transaction_bundle
from lunarbit.finance import (
    EpistemicMode,
    FinancialComponentType,
    FinancialScope,
    FundingStatus,
    MoneyComponent,
    ReconciliationStatus,
    TruthScope,
)
from lunarbit.models import DocumentRole


ORDER_ID = UUID("30000000-0000-0000-0000-000000000001")


def _component(
    suffix: int,
    source_id: str,
    component_type: FinancialComponentType,
    amount: str,
) -> MoneyComponent:
    return MoneyComponent(
        component_id=UUID(f"10000000-0000-0000-0000-{suffix:012d}"),
        source_component_id=UUID(f"20000000-0000-0000-0000-{suffix:012d}"),
        order_ids=(ORDER_ID,),
        component_type=component_type,
        amount=Decimal(amount),
        source_amount_string_private=amount,
        currency="INR",
        source_precision=2,
        scope=FinancialScope.ORDER,
        epistemic_mode=EpistemicMode.OBSERVED,
        truth_scope=TruthScope.DOCUMENT_ASSERTED,
        funding_status=FundingStatus.UNRESOLVED,
        source_id=source_id,
        source_chunk_id=UUID(f"40000000-0000-0000-0000-{suffix:012d}"),
    )


def test_multi_document_reconciliation_closes_merchant_platform_and_summary_legs() -> None:
    components = (
        _component(1, "doc_0000000000000001", FinancialComponentType.ITEM_GROSS, "400.00"),
        _component(2, "doc_0000000000000001", FinancialComponentType.TAX, "20.00"),
        _component(3, "doc_0000000000000002", FinancialComponentType.PLATFORM_FEE, "10.00"),
        _component(4, "doc_0000000000000003", FinancialComponentType.CUSTOMER_TOTAL, "430.00"),
    )
    roles = {
        "doc_0000000000000001": DocumentRole.ZOMATO_MERCHANT_INVOICE,
        "doc_0000000000000002": DocumentRole.ZOMATO_PLATFORM_FEE_INVOICE,
        "doc_0000000000000003": DocumentRole.ZOMATO_ORDER_SUMMARY,
    }

    result = reconcile_transaction_bundle(
        components,
        document_roles=roles,
        executed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert result.status is ReconciliationStatus.EXACT
    assert result.expected_amount == Decimal("430.00")
    assert result.calculated_amount == Decimal("430.00")
    assert result.residual == Decimal("0.00")
    assert result.selected_component_ids == tuple(item.component_id for item in components)
    assert "ITEM_GROSS" in result.formula
    assert "PLATFORM_FEE" in result.formula


def test_document_authority_prevents_summary_duplicates_from_double_counting() -> None:
    merchant_item = _component(
        1, "doc_0000000000000001", FinancialComponentType.ITEM_GROSS, "400.00"
    )
    summary_duplicate = _component(
        2, "doc_0000000000000002", FinancialComponentType.ITEM_GROSS, "400.00"
    )
    total = _component(
        3, "doc_0000000000000002", FinancialComponentType.CUSTOMER_TOTAL, "400.00"
    )

    result = reconcile_transaction_bundle(
        (merchant_item, summary_duplicate, total),
        document_roles={
            "doc_0000000000000001": DocumentRole.ZOMATO_MERCHANT_INVOICE,
            "doc_0000000000000002": DocumentRole.ZOMATO_ORDER_SUMMARY,
        },
        executed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert result.status is ReconciliationStatus.EXACT
    assert result.calculated_amount == Decimal("400.00")
    assert summary_duplicate.component_id in result.rejected_component_ids
    assert merchant_item.component_id in result.selected_component_ids


def test_conflicting_bundle_preserves_residual_instead_of_forcing_balance() -> None:
    result = reconcile_transaction_bundle(
        (
            _component(1, "doc_0000000000000001", FinancialComponentType.ITEM_GROSS, "300.00"),
            _component(
                2,
                "doc_0000000000000002",
                FinancialComponentType.MEMBERSHIP_BENEFIT,
                "50.00",
            ),
            _component(
                3, "doc_0000000000000001", FinancialComponentType.CUSTOMER_TOTAL, "280.00"
            ),
        ),
        document_roles={
            "doc_0000000000000001": DocumentRole.SWIGGY_RESTAURANT_INVOICE,
            "doc_0000000000000002": DocumentRole.SWIGGY_PLATFORM_FEE_INVOICE,
        },
        executed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert result.status is ReconciliationStatus.CONFLICTING
    assert result.calculated_amount == Decimal("250.00")
    assert result.residual == Decimal("30.00")


def test_bundle_reconciliation_rejects_cross_order_or_currency_arithmetic() -> None:
    first = _component(1, "doc_0000000000000001", FinancialComponentType.ITEM_GROSS, "10.00")
    second = _component(2, "doc_0000000000000002", FinancialComponentType.CUSTOMER_TOTAL, "10.00")

    with pytest.raises(ValueError, match="order"):
        reconcile_transaction_bundle(
            (first, second.model_copy(update={"order_ids": (UUID(int=9),)})),
            document_roles={
                first.source_id: DocumentRole.ZOMATO_MERCHANT_INVOICE,
                second.source_id: DocumentRole.ZOMATO_ORDER_SUMMARY,
            },
            executed_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="currency"):
        reconcile_transaction_bundle(
            (first, second.model_copy(update={"currency": "USD"})),
            document_roles={
                first.source_id: DocumentRole.ZOMATO_MERCHANT_INVOICE,
                second.source_id: DocumentRole.ZOMATO_ORDER_SUMMARY,
            },
            executed_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
