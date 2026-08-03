from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from stat import S_IMODE

import pytest

from lunarbit.chunk import (
    chunk_document,
    chunk_message,
    route_document_strategy,
    validate_chunk_proposals,
    write_chunk_result,
)
from lunarbit.models import (
    BoundingBox,
    CandidateFactType,
    CandidateMoneyType,
    ChunkStrategy,
    ChunkType,
    DocumentManifest,
    DocumentRecord,
    DocumentRole,
    EntityType,
    EvidenceSourceKind,
    ExtractionMethod,
    OrderCategory,
    PageQualityProfile,
    PageRecord,
    Platform,
    PrivacyStatus,
    ProcessedDocument,
    ProcessingStatus,
    QueryFamily,
    SourceMessage,
    TableCell,
    TableRecord,
    TextBlock,
    ValidationStatus,
)

DOCUMENT_ID = "doc_0123456789abcdef"
MESSAGE_ID = "msg_0123456789abcdef"


def _processed_document(
    *,
    role: DocumentRole = DocumentRole.ZOMATO_ORDER_SUMMARY,
    text: str = (
        "Order ID: 1234567890\n"
        "Restaurant: Test Kitchen\n"
        "Delivery Partner: Alex Example\n"
        "Total: INR 123.40"
    ),
    tables: tuple[TableRecord, ...] = (),
) -> ProcessedDocument:
    text_block = TextBlock(
        block_id="block_001_0000",
        bbox=BoundingBox(x0=20, y0=20, x1=280, y1=100),
        text_private=text,
        reading_order=0,
    )
    page = PageRecord(
        document_id=DOCUMENT_ID,
        page_number=1,
        width=300,
        height=200,
        text_blocks=(text_block,),
        key_value_blocks=(),
        tables=tables,
        images=(),
        reading_order=(text_block.block_id,),
        extraction_method=ExtractionMethod.NATIVE,
        quality_profile=PageQualityProfile(
            text_character_count=len(text),
            text_block_count=1,
            key_value_count=0,
            table_count=len(tables),
            image_count=0,
            accepted=True,
            ocr_required=False,
        ),
    )
    return ProcessedDocument(
        manifest=DocumentManifest(
            document_id=DOCUMENT_ID,
            sha256="0" * 64,
            source_filename_private="synthetic.pdf",
            file_size=100,
            page_count=1,
            probable_platform=Platform.ZOMATO,
            probable_document_type=role,
            probable_order_id_private="1234567890",
            template_signature="1" * 64,
            native_text_available=True,
            ocr_required=False,
            extraction_version="1.0.0",
            processing_status=ProcessingStatus.COMPLETE,
            privacy_status=PrivacyStatus.PRIVATE,
        ),
        document=DocumentRecord(
            document_id=DOCUMENT_ID,
            page_count=1,
            page_numbers=(1,),
            full_text_sha256=sha256(text.encode()).hexdigest(),
            text_character_count=len(text),
            table_count=len(tables),
            image_count=0,
            quality_accepted=True,
        ),
        pages=(page,),
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    (
        (DocumentRole.ZOMATO_ORDER_SUMMARY, ChunkStrategy.ORDER_COMPONENT),
        (DocumentRole.SWIGGY_RESTAURANT_INVOICE, ChunkStrategy.TABLE_PRESERVING_INVOICE),
        (DocumentRole.ZOMATO_PLATFORM_FEE_INVOICE, ChunkStrategy.FEE_AND_TAX),
        (DocumentRole.SWIGGY_ORDER_HISTORY_REPORT, ChunkStrategy.HISTORY_TABLE),
        (DocumentRole.UNKNOWN, ChunkStrategy.UNKNOWN_LAYOUT),
    ),
)
def test_document_strategy_router_is_role_driven(
    role: DocumentRole,
    expected: ChunkStrategy,
) -> None:
    assert route_document_strategy(role) is expected


def test_document_chunks_are_deterministic_and_source_supported() -> None:
    processed = _processed_document()

    first = chunk_document(processed)
    second = chunk_document(processed)

    assert first == second
    assert first.validation_status is ValidationStatus.ACCEPTED
    assert first.strategy is ChunkStrategy.ORDER_COMPONENT
    assert len(first.chunks) == 1
    chunk = first.chunks[0]
    assert chunk.source_kind is EvidenceSourceKind.DOCUMENT
    assert chunk.document_id == DOCUMENT_ID
    assert chunk.message_id is None
    assert chunk.page_number == 1
    assert chunk.chunk_type is ChunkType.ORDER_HEADER
    assert chunk.source_region_ids == ("block_001_0000",)
    assert chunk.source_hash == sha256(chunk.raw_text_private.encode()).hexdigest()
    assert chunk.validation_status is ValidationStatus.ACCEPTED
    assert QueryFamily.ORDER_LOOKUP in chunk.query_families

    assertions = {candidate.fact_type: candidate for candidate in chunk.candidate_assertions}
    assert assertions[CandidateFactType.ORDER_ID].raw_value_private == "1234567890"
    assert assertions[CandidateFactType.MERCHANT_NAME].raw_value_private == "Test Kitchen"
    assert (
        chunk.raw_text_private[
            assertions[CandidateFactType.ORDER_ID].source_span_start : assertions[
                CandidateFactType.ORDER_ID
            ].source_span_end
        ]
        == "1234567890"
    )

    entities = {mention.entity_type: mention for mention in chunk.entity_mentions}
    assert entities[EntityType.MERCHANT].raw_value_private == "Test Kitchen"
    assert entities[EntityType.DELIVERY_PARTNER].raw_value_private == "Alex Example"
    money = chunk.candidate_money_components[0]
    assert money.component_type is CandidateMoneyType.INVOICE_TOTAL
    assert money.amount == Decimal("123.40")
    assert money.source_amount_string_private == "123.40"
    assert money.source_precision == 2


def test_table_chunker_preserves_rows_headers_and_item_amounts() -> None:
    table = TableRecord(
        table_id="table_001_000",
        bbox=BoundingBox(x0=20, y0=110, x1=280, y1=190),
        row_count=2,
        column_count=2,
        cells=(
            TableCell(
                cell_id="header_item",
                row_index=0,
                column_index=0,
                row_span=1,
                column_span=1,
                bbox=BoundingBox(x0=20, y0=110, x1=150, y1=150),
                raw_text_private="Item",
                normalized_text_private="Item",
                is_header=True,
                confidence=Decimal("0.90"),
            ),
            TableCell(
                cell_id="header_amount",
                row_index=0,
                column_index=1,
                row_span=1,
                column_span=1,
                bbox=BoundingBox(x0=150, y0=110, x1=280, y1=150),
                raw_text_private="Amount",
                normalized_text_private="Amount",
                is_header=True,
                confidence=Decimal("0.90"),
            ),
            TableCell(
                cell_id="item_meal",
                row_index=1,
                column_index=0,
                row_span=1,
                column_span=1,
                bbox=BoundingBox(x0=20, y0=150, x1=150, y1=190),
                raw_text_private="Meal",
                normalized_text_private="Meal",
                is_header=False,
                header_cell_ids=("header_item",),
                confidence=Decimal("0.90"),
            ),
            TableCell(
                cell_id="item_amount",
                row_index=1,
                column_index=1,
                row_span=1,
                column_span=1,
                bbox=BoundingBox(x0=150, y0=150, x1=280, y1=190),
                raw_text_private="123.40",
                normalized_text_private="123.40",
                is_header=False,
                header_cell_ids=("header_amount",),
                confidence=Decimal("0.90"),
            ),
        ),
        confidence=Decimal("0.90"),
    )

    result = chunk_document(
        _processed_document(
            role=DocumentRole.SWIGGY_RESTAURANT_INVOICE,
            text="Tax Invoice",
            tables=(table,),
        )
    )

    table_chunk = next(chunk for chunk in result.chunks if chunk.chunk_type is ChunkType.ITEM_TABLE)
    row_chunk = next(chunk for chunk in result.chunks if chunk.chunk_type is ChunkType.ITEM_ROW)
    assert table_chunk.table_id == table.table_id
    assert row_chunk.parent_region_id == table.table_id
    assert row_chunk.row_index == 1
    assert row_chunk.column_headers_private == ("Item", "Amount")
    assert row_chunk.raw_text_private == "Meal | 123.40"
    assert row_chunk.source_region_ids == ("item_meal", "item_amount")
    assert row_chunk.candidate_money_components[0].component_type is CandidateMoneyType.ITEM_AMOUNT
    assert row_chunk.candidate_money_components[0].amount == Decimal("123.40")


def test_mail_only_message_becomes_one_provenance_linked_order_chunk() -> None:
    body = "Order ID: 1234567890\nRestaurant: Mail Kitchen\nTotal: INR 88.50"
    message = SourceMessage(
        message_id=MESSAGE_ID,
        raw_sha256="2" * 64,
        platform=Platform.ZOMATO,
        category=OrderCategory.FOOD,
        occurred_at=datetime(2026, 8, 3, tzinfo=UTC),
        subject_private="Your Zomato order",
        sender_private="receipts@zomato.com",
        source_locator_private="private/orders.mbox#message-1",
        body_sha256=sha256(body.encode()).hexdigest(),
        body_text_private=body,
    )

    result = chunk_message(message)

    assert result.validation_status is ValidationStatus.ACCEPTED
    assert result.strategy is ChunkStrategy.MESSAGE_ORDER
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.source_kind is EvidenceSourceKind.MESSAGE
    assert chunk.message_id == MESSAGE_ID
    assert chunk.document_id is None
    assert chunk.page_number is None
    assert chunk.extraction_method is ExtractionMethod.EMAIL
    assert chunk.source_region_ids == (f"{MESSAGE_ID}:body",)
    assert any(
        candidate.fact_type is CandidateFactType.ORDER_ID
        for candidate in chunk.candidate_assertions
    )
    assert chunk.candidate_money_components[0].amount == Decimal("88.50")
    assert "Mail Kitchen" not in repr(chunk)


def test_legacy_mail_order_number_format_remains_id_resolved() -> None:
    body = "Ordered from:\nLegacy Kitchen\nOrder no:\n#12345678901"
    message = SourceMessage(
        message_id=MESSAGE_ID,
        raw_sha256="2" * 64,
        platform=Platform.SWIGGY,
        category=OrderCategory.FOOD,
        source_locator_private="private/orders.mbox#message-1",
        body_sha256=sha256(body.encode()).hexdigest(),
        body_text_private=body,
    )

    result = chunk_message(message)

    order_ids = [
        candidate.raw_value_private
        for candidate in result.chunks[0].candidate_assertions
        if candidate.fact_type is CandidateFactType.ORDER_ID
    ]
    assert order_ids == ["12345678901"]
    merchants = [
        mention.raw_value_private
        for mention in result.chunks[0].entity_mentions
        if mention.entity_type is EntityType.MERCHANT
    ]
    assert merchants == ["Legacy Kitchen"]


def test_unknown_template_is_quarantined_without_canonical_chunks() -> None:
    result = chunk_document(_processed_document(role=DocumentRole.UNKNOWN))

    assert result.strategy is ChunkStrategy.UNKNOWN_LAYOUT
    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.chunks == ()
    assert result.quarantine_reasons == ("unknown_document_role",)


def test_invalid_agentic_proposal_is_quarantined_without_partial_acceptance() -> None:
    baseline = chunk_document(_processed_document())
    proposal = baseline.chunks[0].model_dump(mode="json")
    proposal["candidate_assertions"][0]["source_span_end"] += 1

    result = validate_chunk_proposals(
        source_kind=EvidenceSourceKind.DOCUMENT,
        source_id=DOCUMENT_ID,
        strategy=ChunkStrategy.ORDER_COMPONENT,
        proposals=(proposal,),
    )

    assert result.validation_status is ValidationStatus.QUARANTINED
    assert result.chunks == ()
    assert result.quarantine_reasons == ("invalid_chunk_proposal",)


def test_chunk_artifacts_are_private_and_idempotent(tmp_path: Path) -> None:
    result = chunk_document(_processed_document())

    chunk_root = write_chunk_result(result, tmp_path)
    first_write = {
        path.name: path.read_bytes() for path in sorted(chunk_root.iterdir()) if path.is_file()
    }
    write_chunk_result(result, tmp_path)
    second_write = {
        path.name: path.read_bytes() for path in sorted(chunk_root.iterdir()) if path.is_file()
    }

    assert set(first_write) == {"chunk-manifest.json", "chunks.jsonl"}
    assert second_write == first_write
    assert all(
        S_IMODE(path.stat().st_mode) == 0o600 for path in chunk_root.iterdir() if path.is_file()
    )
