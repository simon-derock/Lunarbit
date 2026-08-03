from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Strict, immutable base for canonical ingestion contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )


class Platform(StrEnum):
    ZOMATO = "zomato"
    SWIGGY = "swiggy"


class OrderCategory(StrEnum):
    FOOD = "food"
    INSTAMART = "instamart"


class DocumentRole(StrEnum):
    ZOMATO_ORDER_SUMMARY = "ZOMATO_ORDER_SUMMARY"
    ZOMATO_MERCHANT_INVOICE = "ZOMATO_MERCHANT_INVOICE"
    ZOMATO_PLATFORM_FEE_INVOICE = "ZOMATO_PLATFORM_FEE_INVOICE"
    ZOMATO_DELIVERY_SERVICE_INVOICE = "ZOMATO_DELIVERY_SERVICE_INVOICE"
    SWIGGY_RESTAURANT_INVOICE = "SWIGGY_RESTAURANT_INVOICE"
    SWIGGY_INSTAMART_SELLER_INVOICE = "SWIGGY_INSTAMART_SELLER_INVOICE"
    SWIGGY_PLATFORM_FEE_INVOICE = "SWIGGY_PLATFORM_FEE_INVOICE"
    SWIGGY_ORDER_HISTORY_REPORT = "SWIGGY_ORDER_HISTORY_REPORT"
    UNKNOWN = "UNKNOWN"


class OrderIdSource(StrEnum):
    PDF_LABEL = "PDF_LABEL"
    EMAIL_FIELD = "EMAIL_FIELD"
    HISTORY_ROW = "HISTORY_ROW"
    ATTACHMENT_FILENAME = "ATTACHMENT_FILENAME"
    MANIFEST_HINT = "MANIFEST_HINT"


class OrderEvidenceKind(StrEnum):
    PDF_BUNDLE = "PDF_BUNDLE"
    EMAIL_ONLY = "EMAIL_ONLY"
    HISTORY_ROW = "HISTORY_ROW"


class OrderIdCandidate(ContractModel):
    value_private: str = Field(repr=False, min_length=1, pattern=r"^\d+$")
    source: OrderIdSource
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class SourceDocument(ContractModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{16}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_id: str = Field(pattern=r"^msg_[0-9a-f]{16}$")
    platform: Platform
    category: OrderCategory
    role: DocumentRole
    source_filename_private: str = Field(repr=False, min_length=1)
    source_locator_private: str = Field(repr=False, min_length=1)
    mime_type: str
    byte_count: int = Field(ge=1)
    page_count: int = Field(ge=1)
    native_text_available: bool
    order_candidates: tuple[OrderIdCandidate, ...] = ()


class SourceMessage(ContractModel):
    message_id: str = Field(pattern=r"^msg_[0-9a-f]{16}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    platform: Platform
    category: OrderCategory
    occurred_at: datetime | None = None
    subject_private: str = Field(default="", repr=False)
    sender_private: str = Field(default="", repr=False)
    source_locator_private: str = Field(repr=False, min_length=1)
    provider_message_id_private: str | None = Field(default=None, repr=False)
    body_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attachment_document_ids: tuple[str, ...] = ()
    order_candidates: tuple[OrderIdCandidate, ...] = ()


class OrderEvidence(ContractModel):
    evidence_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    platform: Platform
    kind: OrderEvidenceKind
    order_id_private: str | None = Field(default=None, repr=False, pattern=r"^\d+$")

    @model_validator(mode="after")
    def history_rows_require_an_order_id(self) -> OrderEvidence:
        if self.kind is OrderEvidenceKind.HISTORY_ROW and self.order_id_private is None:
            raise ValueError("history-row evidence requires an order ID")
        return self


class OrderCountSummary(ContractModel):
    resolved_orders: int = Field(ge=0)
    provisional_orders: int = Field(ge=0)
    total_orders: int = Field(ge=0)
    history_duplicates: int = Field(ge=0)

    @model_validator(mode="after")
    def total_matches_components(self) -> OrderCountSummary:
        if self.total_orders != self.resolved_orders + self.provisional_orders:
            raise ValueError("total_orders must equal resolved_orders + provisional_orders")
        return self


class SourceInventorySummary(ContractModel):
    relevant_messages: int = Field(ge=0)
    excluded_messages: int = Field(ge=0)
    unique_pdf_documents: int = Field(ge=0)
    pdf_pages: int = Field(ge=0)
    pdf_backed_order_messages: int = Field(ge=0)
    mail_only_order_messages: int = Field(ge=0)
    history_report_documents: int = Field(ge=0)
    duplicate_pdf_documents: int = Field(ge=0)
    orders: OrderCountSummary


class SourceInventory(ContractModel):
    messages: tuple[SourceMessage, ...]
    documents: tuple[SourceDocument, ...]
    order_evidence: tuple[OrderEvidence, ...]
    summary: SourceInventorySummary
