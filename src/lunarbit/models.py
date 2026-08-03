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


class ExtractionMethod(StrEnum):
    NATIVE = "native"
    OCR = "ocr"


class ProcessingStatus(StrEnum):
    COMPLETE = "complete"
    QUARANTINED = "quarantined"


class PrivacyStatus(StrEnum):
    PRIVATE = "private"


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


class BoundingBox(ContractModel):
    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)

    @model_validator(mode="after")
    def coordinates_are_ordered(self) -> BoundingBox:
        if self.x1 < self.x0:
            raise ValueError("x1 must be greater than or equal to x0")
        if self.y1 < self.y0:
            raise ValueError("y1 must be greater than or equal to y0")
        return self


class TextBlock(ContractModel):
    block_id: str = Field(min_length=1)
    bbox: BoundingBox
    text_private: str = Field(repr=False, min_length=1)
    reading_order: int = Field(ge=0)


class KeyValueBlock(ContractModel):
    key_value_id: str = Field(min_length=1)
    source_block_id: str = Field(min_length=1)
    bbox: BoundingBox
    key_private: str = Field(repr=False, min_length=1)
    value_private: str = Field(repr=False, min_length=1)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class TableCell(ContractModel):
    cell_id: str = Field(min_length=1)
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(ge=1)
    column_span: int = Field(ge=1)
    bbox: BoundingBox | None = None
    raw_text_private: str = Field(default="", repr=False)
    normalized_text_private: str = Field(default="", repr=False)
    is_header: bool
    header_cell_ids: tuple[str, ...] = ()
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class TableRecord(ContractModel):
    table_id: str = Field(min_length=1)
    bbox: BoundingBox
    row_count: int = Field(ge=1)
    column_count: int = Field(ge=1)
    cells: tuple[TableCell, ...]
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class PageImage(ContractModel):
    image_id: str = Field(min_length=1)
    bbox: BoundingBox
    pixel_width: int = Field(ge=1)
    pixel_height: int = Field(ge=1)
    xref: int | None = Field(default=None, ge=0)


class PageQualityProfile(ContractModel):
    text_character_count: int = Field(ge=0)
    text_block_count: int = Field(ge=0)
    key_value_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    accepted: bool
    ocr_required: bool
    issues: tuple[str, ...] = ()


class PageRecord(ContractModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{16}$")
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    text_blocks: tuple[TextBlock, ...]
    key_value_blocks: tuple[KeyValueBlock, ...]
    tables: tuple[TableRecord, ...]
    images: tuple[PageImage, ...]
    reading_order: tuple[str, ...]
    extraction_method: ExtractionMethod
    quality_profile: PageQualityProfile


class DocumentManifest(ContractModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{16}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_filename_private: str = Field(repr=False, min_length=1)
    file_size: int = Field(ge=1)
    page_count: int = Field(ge=1)
    probable_platform: Platform
    probable_document_type: DocumentRole
    probable_order_id_private: str | None = Field(default=None, repr=False, pattern=r"^\d+$")
    template_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_text_available: bool
    ocr_required: bool
    extraction_version: str = Field(min_length=1)
    processing_status: ProcessingStatus
    privacy_status: PrivacyStatus


class DocumentRecord(ContractModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{16}$")
    page_count: int = Field(ge=1)
    page_numbers: tuple[int, ...]
    full_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_character_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    quality_accepted: bool


class ProcessedDocument(ContractModel):
    manifest: DocumentManifest
    document: DocumentRecord
    pages: tuple[PageRecord, ...]

    @model_validator(mode="after")
    def document_members_are_consistent(self) -> ProcessedDocument:
        document_id = self.manifest.document_id
        if self.document.document_id != document_id:
            raise ValueError("document record must match manifest document_id")
        if any(page.document_id != document_id for page in self.pages):
            raise ValueError("page records must match manifest document_id")
        if len(self.pages) != self.manifest.page_count:
            raise ValueError("page records must match manifest page_count")
        if self.document.page_numbers != tuple(page.page_number for page in self.pages):
            raise ValueError("document page_numbers must match page records")
        return self
