from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

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
    EMAIL = "email"


class ProcessingStatus(StrEnum):
    COMPLETE = "complete"
    QUARANTINED = "quarantined"


class PrivacyStatus(StrEnum):
    PRIVATE = "private"


class ChunkStrategy(StrEnum):
    ORDER_COMPONENT = "order_component"
    TABLE_PRESERVING_INVOICE = "table_preserving_invoice"
    FEE_AND_TAX = "fee_and_tax"
    HISTORY_TABLE = "history_table"
    MESSAGE_ORDER = "message_order"
    UNKNOWN_LAYOUT = "unknown_layout"


class ChunkType(StrEnum):
    ORDER_HEADER = "ORDER_HEADER"
    ORDER_PARTIES = "ORDER_PARTIES"
    DELIVERY_MENTION = "DELIVERY_MENTION"
    ITEM_TABLE = "ITEM_TABLE"
    ITEM_ROW = "ITEM_ROW"
    SUBTOTAL = "SUBTOTAL"
    DISCOUNT_BLOCK = "DISCOUNT_BLOCK"
    MEMBERSHIP_BENEFIT = "MEMBERSHIP_BENEFIT"
    PACKING_CHARGE = "PACKING_CHARGE"
    HANDLING_FEE = "HANDLING_FEE"
    DELIVERY_CHARGE = "DELIVERY_CHARGE"
    PLATFORM_FEE = "PLATFORM_FEE"
    TAX_BLOCK = "TAX_BLOCK"
    PAYMENT_ASSERTION = "PAYMENT_ASSERTION"
    REFUND_BLOCK = "REFUND_BLOCK"
    LEGAL_ENTITY_BLOCK = "LEGAL_ENTITY_BLOCK"
    REGULATORY_BLOCK = "REGULATORY_BLOCK"
    TERMS_BLOCK = "TERMS_BLOCK"
    OTHER_EVIDENCE = "OTHER_EVIDENCE"


class SemanticRole(StrEnum):
    ORDER_IDENTITY = "order_identity"
    PARTY_IDENTITY = "party_identity"
    DELIVERY_EVIDENCE = "delivery_evidence"
    ITEM_DETAIL = "item_detail"
    FINANCIAL_DETAIL = "financial_detail"
    PAYMENT_EVIDENCE = "payment_evidence"
    LEGAL_DETAIL = "legal_detail"
    REGULATORY_DETAIL = "regulatory_detail"
    GENERAL_EVIDENCE = "general_evidence"


class FinancialRole(StrEnum):
    NONE = "none"
    ITEM = "item"
    CHARGE = "charge"
    DISCOUNT = "discount"
    TAX = "tax"
    TOTAL = "total"
    PAYMENT = "payment"
    REFUND = "refund"


class EvidenceSourceKind(StrEnum):
    DOCUMENT = "document"
    MESSAGE = "message"


class ValidationStatus(StrEnum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


class CandidateFactType(StrEnum):
    ORDER_ID = "order_id"
    ORDER_DATE = "order_date"
    MERCHANT_NAME = "merchant_name"
    LEGAL_ENTITY_NAME = "legal_entity_name"
    DELIVERY_PARTNER_NAME = "delivery_partner_name"
    INVOICE_NUMBER = "invoice_number"
    PAYMENT_METHOD = "payment_method"


class EntityType(StrEnum):
    MERCHANT = "merchant"
    LEGAL_ENTITY = "legal_entity"
    DELIVERY_PARTNER = "delivery_partner"


class CandidateMoneyType(StrEnum):
    ITEM_AMOUNT = "item_amount"
    SUBTOTAL = "subtotal"
    DISCOUNT = "discount"
    PACKING_CHARGE = "packing_charge"
    HANDLING_FEE = "handling_fee"
    DELIVERY_CHARGE = "delivery_charge"
    PLATFORM_FEE = "platform_fee"
    TAX = "tax"
    INVOICE_TOTAL = "invoice_total"
    REFUND = "refund"


class QueryFamily(StrEnum):
    ORDER_LOOKUP = "order_lookup"
    ITEM_SEARCH = "item_search"
    FINANCIAL_BREAKDOWN = "financial_breakdown"
    MERCHANT_ANALYSIS = "merchant_analysis"
    DELIVERY_ANALYSIS = "delivery_analysis"
    TAX_ANALYSIS = "tax_analysis"
    PAYMENT_ANALYSIS = "payment_analysis"
    EVIDENCE_REPLAY = "evidence_replay"


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
    body_text_private: str = Field(default="", repr=False)
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


class CandidateAssertion(ContractModel):
    assertion_id: UUID
    fact_type: CandidateFactType
    raw_value_private: str = Field(repr=False, min_length=1)
    normalized_value_private: str = Field(repr=False, min_length=1)
    source_span_start: int = Field(ge=0)
    source_span_end: int = Field(gt=0)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    @model_validator(mode="after")
    def source_span_is_ordered(self) -> CandidateAssertion:
        if self.source_span_end <= self.source_span_start:
            raise ValueError("source_span_end must be greater than source_span_start")
        return self


class EntityMention(ContractModel):
    mention_id: UUID
    entity_type: EntityType
    raw_value_private: str = Field(repr=False, min_length=1)
    normalized_value_private: str = Field(repr=False, min_length=1)
    source_span_start: int = Field(ge=0)
    source_span_end: int = Field(gt=0)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    @model_validator(mode="after")
    def source_span_is_ordered(self) -> EntityMention:
        if self.source_span_end <= self.source_span_start:
            raise ValueError("source_span_end must be greater than source_span_start")
        return self


class CandidateMoneyComponent(ContractModel):
    component_id: UUID
    component_type: CandidateMoneyType
    amount: Decimal
    source_amount_string_private: str = Field(repr=False, min_length=1)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    source_precision: int = Field(ge=0)
    source_span_start: int = Field(ge=0)
    source_span_end: int = Field(gt=0)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    @model_validator(mode="after")
    def source_span_is_ordered(self) -> CandidateMoneyComponent:
        if self.source_span_end <= self.source_span_start:
            raise ValueError("source_span_end must be greater than source_span_start")
        return self


class GraphCandidate(ContractModel):
    candidate_id: UUID
    candidate_type: str = Field(min_length=1)
    source_candidate_ids: tuple[UUID, ...]


class EvidenceChunk(ContractModel):
    chunk_id: UUID
    source_kind: EvidenceSourceKind
    source_id: str = Field(pattern=r"^(?:doc|msg)_[0-9a-f]{16}$")
    document_id: str | None = Field(default=None, pattern=r"^doc_[0-9a-f]{16}$")
    message_id: str | None = Field(default=None, pattern=r"^msg_[0-9a-f]{16}$")
    page_number: int | None = Field(default=None, ge=1)
    chunk_type: ChunkType
    semantic_role: SemanticRole
    financial_role: FinancialRole
    raw_text_private: str = Field(repr=False, min_length=1)
    normalized_text_private: str = Field(repr=False, min_length=1)
    semantic_summary_private: str = Field(repr=False, min_length=1)
    embedding_text_private: str = Field(repr=False, min_length=1)
    bounding_box: BoundingBox | None = None
    reading_order: int = Field(ge=0)
    table_id: str | None = None
    row_index: int | None = Field(default=None, ge=0)
    column_headers_private: tuple[str, ...] = Field(default=(), repr=False)
    parent_region_id: str | None = None
    source_region_ids: tuple[str, ...] = Field(min_length=1)
    entity_mentions: tuple[EntityMention, ...] = ()
    candidate_assertions: tuple[CandidateAssertion, ...] = ()
    candidate_money_components: tuple[CandidateMoneyComponent, ...] = ()
    query_families: tuple[QueryFamily, ...]
    graph_candidates: tuple[GraphCandidate, ...] = ()
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_method: ExtractionMethod
    extraction_confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    chunk_completeness: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    validation_status: ValidationStatus
    privacy_class: PrivacyStatus
    embedding_model: str | None = None
    embedding_dimension: int | None = Field(default=None, ge=1)
    embedding_version: str | None = None

    @model_validator(mode="after")
    def provenance_and_candidates_are_supported(self) -> EvidenceChunk:
        if self.source_kind is EvidenceSourceKind.DOCUMENT:
            if self.document_id != self.source_id or self.message_id is not None:
                raise ValueError("document chunks require only the matching document_id")
            if self.page_number is None or self.bounding_box is None:
                raise ValueError("document chunks require page and bounding-box provenance")
        elif self.message_id != self.source_id or self.document_id is not None:
            raise ValueError("message chunks require only the matching message_id")

        if sha256(self.raw_text_private.encode()).hexdigest() != self.source_hash:
            raise ValueError("source_hash must match raw_text_private")
        for candidate in self.candidate_assertions:
            if candidate.source_span_end > len(self.raw_text_private):
                raise ValueError("candidate source span exceeds raw chunk text")
            if (
                self.raw_text_private[candidate.source_span_start : candidate.source_span_end]
                != candidate.raw_value_private
            ):
                raise ValueError("candidate value must match its raw source span")
        for mention in self.entity_mentions:
            if mention.source_span_end > len(self.raw_text_private):
                raise ValueError("mention source span exceeds raw chunk text")
            if (
                self.raw_text_private[mention.source_span_start : mention.source_span_end]
                != mention.raw_value_private
            ):
                raise ValueError("mention value must match its raw source span")
        for component in self.candidate_money_components:
            if component.source_span_end > len(self.raw_text_private):
                raise ValueError("money source span exceeds raw chunk text")
            if (
                self.raw_text_private[component.source_span_start : component.source_span_end]
                != component.source_amount_string_private
            ):
                raise ValueError("money value must match its raw source span")
        return self


class ChunkingResult(ContractModel):
    source_kind: EvidenceSourceKind
    source_id: str = Field(pattern=r"^(?:doc|msg)_[0-9a-f]{16}$")
    strategy: ChunkStrategy
    chunks: tuple[EvidenceChunk, ...]
    validation_status: ValidationStatus
    quarantine_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def result_state_is_consistent(self) -> ChunkingResult:
        if any(
            chunk.source_id != self.source_id or chunk.source_kind is not self.source_kind
            for chunk in self.chunks
        ):
            raise ValueError("all chunks must match the result source")
        if self.validation_status is ValidationStatus.ACCEPTED:
            if not self.chunks or self.quarantine_reasons:
                raise ValueError("accepted results require chunks and no quarantine reasons")
        elif self.chunks or not self.quarantine_reasons:
            raise ValueError("quarantined results require reasons and no canonical chunks")
        return self


class ChunkArchiveSummary(ContractModel):
    document_sources: int = Field(ge=0)
    message_sources: int = Field(ge=0)
    accepted_sources: int = Field(ge=0)
    quarantined_sources: int = Field(ge=0)
    chunks: int = Field(ge=0)
    assertions: int = Field(ge=0)
    entity_mentions: int = Field(ge=0)
    money_candidates: int = Field(ge=0)


class ChunkBenchmarkSummary(ContractModel):
    expected_sources: int = Field(ge=0)
    evaluated_sources: int = Field(ge=0)
    accepted_sources: int = Field(ge=0)
    quarantined_sources: int = Field(ge=0)
    valid_chunks: int = Field(ge=0)
    invalid_chunks: int = Field(ge=0)
    phase1_tables: int = Field(ge=0)
    item_table_chunks: int = Field(ge=0)
    message_sources: int = Field(ge=0)
    messages_with_one_chunk: int = Field(ge=0)
    mail_only_sources: int = Field(ge=0)
    mail_only_with_order_id: int = Field(ge=0)
    mail_only_with_merchant: int = Field(ge=0)
    mail_only_with_money: int = Field(ge=0)
    candidate_assertions: int = Field(ge=0)
    entity_mentions: int = Field(ge=0)
    money_candidates: int = Field(ge=0)
    unsupported_candidate_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    passed: bool
