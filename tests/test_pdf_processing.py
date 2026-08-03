from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from stat import S_IMODE

import pytest
from pydantic import ValidationError

from lunarbit.extract import document_id_from_bytes
from lunarbit.models import (
    BoundingBox,
    DocumentRole,
    ExtractionMethod,
    OrderCategory,
    Platform,
    PrivacyStatus,
    ProcessingStatus,
    SourceDocument,
    TableCell,
)
from lunarbit.pdf import extract_pdf_document, write_document_artifacts


def _pdf_bytes(*, blank: bool = False, with_table: bool = False) -> bytes:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    if not blank:
        page.insert_text((36, 36), "Synthetic invoice")
        page.insert_text((36, 60), "Order ID: 1234567890")
        page.insert_text((36, 84), "Total: 123.40")
    if with_table:
        for start, end in (
            ((30, 110), (270, 110)),
            ((30, 150), (270, 150)),
            ((30, 190), (270, 190)),
            ((30, 110), (30, 190)),
            ((150, 110), (150, 190)),
            ((270, 110), (270, 190)),
        ):
            page.draw_line(start, end)
        page.insert_text((40, 135), "Item")
        page.insert_text((160, 135), "Amount")
        page.insert_text((40, 175), "Meal")
        page.insert_text((160, 175), "123.40")
    payload = document.tobytes(garbage=4, deflate=True)
    document.close()
    return payload


def _source_document(payload: bytes, *, native_text_available: bool = True) -> SourceDocument:
    return SourceDocument(
        document_id=document_id_from_bytes(payload),
        sha256=sha256(payload).hexdigest(),
        message_id="msg_0123456789abcdef",
        platform=Platform.ZOMATO,
        category=OrderCategory.FOOD,
        role=DocumentRole.ZOMATO_ORDER_SUMMARY,
        source_filename_private="synthetic-invoice.pdf",
        source_locator_private="private/synthetic-invoice.pdf",
        mime_type="application/pdf",
        byte_count=len(payload),
        page_count=1,
        native_text_available=native_text_available,
    )


def _merged_table_pdf_bytes() -> bytes:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    for start, end in (
        ((30, 30), (270, 30)),
        ((30, 80), (270, 80)),
        ((30, 130), (270, 130)),
        ((30, 30), (30, 130)),
        ((270, 30), (270, 130)),
        ((150, 80), (150, 130)),
    ):
        page.draw_line(start, end)
    page.insert_text((40, 60), "Order lines")
    page.insert_text((40, 110), "Meal")
    page.insert_text((160, 110), "123.40")
    payload = document.tobytes(garbage=4, deflate=True)
    document.close()
    return payload


def test_layout_contracts_preserve_source_values_and_reject_invalid_geometry() -> None:
    bounds = BoundingBox(x0=10, y0=20, x1=110, y1=45)
    cell = TableCell(
        cell_id="tbl_1_cell_1_1",
        row_index=1,
        column_index=1,
        row_span=1,
        column_span=1,
        bbox=bounds,
        raw_text_private="123.40",
        normalized_text_private="123.40",
        is_header=False,
        header_cell_ids=("tbl_1_cell_0_1",),
        confidence=Decimal("0.98"),
    )

    assert cell.raw_text_private == "123.40"
    assert cell.model_dump(mode="json")["confidence"] == "0.98"
    with pytest.raises(ValidationError, match="x1"):
        BoundingBox(x0=20, y0=20, x1=10, y1=45)


def test_native_pdf_extraction_emits_ordered_page_layout() -> None:
    payload = _pdf_bytes()
    source = _source_document(payload)

    processed = extract_pdf_document(source, payload)

    assert processed.manifest.document_id == source.document_id
    assert processed.manifest.processing_status is ProcessingStatus.COMPLETE
    assert processed.manifest.privacy_status is PrivacyStatus.PRIVATE
    assert processed.manifest.native_text_available is True
    assert processed.manifest.ocr_required is False
    assert len(processed.manifest.template_signature) == 64
    assert (
        processed.document.full_text_sha256
        == sha256(
            "\n".join(block.text_private for block in processed.pages[0].text_blocks).encode()
        ).hexdigest()
    )

    page = processed.pages[0]
    assert page.page_number == 1
    assert page.extraction_method is ExtractionMethod.NATIVE
    assert page.quality_profile.accepted is True
    assert page.quality_profile.ocr_required is False
    assert page.reading_order == tuple(block.block_id for block in page.text_blocks)
    assert "123.40" in " ".join(block.text_private for block in page.text_blocks)
    assert all(block.bbox.x1 <= page.width for block in page.text_blocks)
    assert all(block.bbox.y1 <= page.height for block in page.text_blocks)


def test_native_pdf_extraction_preserves_table_cells_and_header_links() -> None:
    payload = _pdf_bytes(with_table=True)

    processed = extract_pdf_document(_source_document(payload), payload)

    table = processed.pages[0].tables[0]
    cells = {(cell.row_index, cell.column_index): cell for cell in table.cells}
    assert (table.row_count, table.column_count) == (2, 2)
    assert cells[0, 0].raw_text_private == "Item"
    assert cells[0, 1].raw_text_private == "Amount"
    assert cells[1, 1].raw_text_private == "123.40"
    assert cells[1, 1].header_cell_ids == (f"{table.table_id}_cell_0_1",)


def test_native_pdf_extraction_preserves_merged_cell_spans() -> None:
    payload = _merged_table_pdf_bytes()

    table = extract_pdf_document(_source_document(payload), payload).pages[0].tables[0]
    cells = {(cell.row_index, cell.column_index): cell for cell in table.cells}

    assert len(cells) == 3
    assert cells[0, 0].column_span == 2
    assert cells[0, 0].raw_text_private == "Order lines"
    assert cells[1, 0].header_cell_ids == (cells[0, 0].cell_id,)
    assert cells[1, 1].header_cell_ids == (cells[0, 0].cell_id,)


def test_blank_page_is_quarantined_and_artifacts_are_private_and_idempotent(
    tmp_path: Path,
) -> None:
    payload = _pdf_bytes(blank=True)
    source = _source_document(payload, native_text_available=False)
    processed = extract_pdf_document(source, payload)

    page = processed.pages[0]
    assert page.quality_profile.accepted is False
    assert page.quality_profile.ocr_required is True
    assert "native_text_missing" in page.quality_profile.issues
    assert processed.manifest.processing_status is ProcessingStatus.QUARANTINED
    assert processed.manifest.ocr_required is True

    document_root = write_document_artifacts(processed, payload, tmp_path)
    expected_files = {
        "document.json",
        "document.md",
        "evidence/page-render-001.webp",
        "manifest.json",
        "pages.jsonl",
        "quarantine.json",
    }
    first_write = {
        path.relative_to(document_root).as_posix(): path.read_bytes()
        for path in sorted(document_root.rglob("*"))
        if path.is_file()
    }

    write_document_artifacts(processed, payload, tmp_path)

    second_write = {
        path.relative_to(document_root).as_posix(): path.read_bytes()
        for path in sorted(document_root.rglob("*"))
        if path.is_file()
    }
    assert set(first_write) == expected_files
    assert second_write == first_write
    assert all(
        S_IMODE(path.stat().st_mode) == 0o600 for path in document_root.rglob("*") if path.is_file()
    )
