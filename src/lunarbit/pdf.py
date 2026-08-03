from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import redirect_stdout
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from itertools import pairwise
from pathlib import Path
from typing import Any

import pymupdf

from lunarbit.models import (
    BoundingBox,
    DocumentManifest,
    DocumentRecord,
    ExtractionMethod,
    KeyValueBlock,
    OrderIdSource,
    PageImage,
    PageQualityProfile,
    PageRecord,
    PrivacyStatus,
    ProcessedDocument,
    ProcessingStatus,
    SourceDocument,
    TableCell,
    TableRecord,
    TextBlock,
)

EXTRACTION_VERSION = "1.0.0"
_KEY_VALUE_PATTERN = re.compile(r"^\s*([^:\n]{2,80}):\s*(\S.*?)\s*$")


class PdfProcessingError(Exception):
    """Raised when PDF bytes cannot produce trustworthy deterministic artifacts."""


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _bounding_box(
    values: tuple[float, float, float, float] | list[float],
    *,
    width: float,
    height: float,
) -> BoundingBox:
    x0, y0, x1, y1 = (float(value) for value in values)
    return BoundingBox(
        x0=max(0.0, min(x0, width)),
        y0=max(0.0, min(y0, height)),
        x1=max(0.0, min(x1, width)),
        y1=max(0.0, min(y1, height)),
    )


def _text_blocks(
    page: pymupdf.Page,
    *,
    page_number: int,
    width: float,
    height: float,
) -> tuple[TextBlock, ...]:
    blocks: list[TextBlock] = []
    for raw_block in page.get_text("blocks", sort=True):  # type: ignore[no-untyped-call]
        if len(raw_block) < 7 or int(raw_block[6]) != 0:
            continue
        text = str(raw_block[4]).strip()
        if not text:
            continue
        reading_order = len(blocks)
        blocks.append(
            TextBlock(
                block_id=f"block_{page_number:03}_{reading_order:04}",
                bbox=_bounding_box(
                    [float(value) for value in raw_block[:4]],
                    width=width,
                    height=height,
                ),
                text_private=text,
                reading_order=reading_order,
            )
        )
    return tuple(blocks)


def _key_value_blocks(
    text_blocks: tuple[TextBlock, ...],
    *,
    page_number: int,
) -> tuple[KeyValueBlock, ...]:
    key_values: list[KeyValueBlock] = []
    for block in text_blocks:
        for line in block.text_private.splitlines():
            match = _KEY_VALUE_PATTERN.match(line)
            if match is None:
                continue
            key_values.append(
                KeyValueBlock(
                    key_value_id=f"kv_{page_number:03}_{len(key_values):04}",
                    source_block_id=block.block_id,
                    bbox=block.bbox,
                    key_private=match.group(1).strip(),
                    value_private=match.group(2).strip(),
                    confidence=Decimal("0.75"),
                )
            )
    return tuple(key_values)


def _grid_span(start: float, end: float, boundaries: tuple[float, ...]) -> int:
    tolerance = 0.01
    return max(
        1,
        sum(
            left >= start - tolerance and right <= end + tolerance
            for left, right in pairwise(boundaries)
        ),
    )


def _table_records(
    page: pymupdf.Page,
    *,
    page_number: int,
    width: float,
    height: float,
) -> tuple[TableRecord, ...]:
    with redirect_stdout(StringIO()):
        finder = page.find_tables()  # type: ignore[no-untyped-call]
    records: list[TableRecord] = []
    for table_index, table in enumerate(finder.tables):
        table_id = f"table_{page_number:03}_{table_index:03}"
        extracted_rows = table.extract()
        header_in_first_row = not table.header.external and any(table.header.names)
        detected_bounds = tuple(
            cell_bounds
            for row in table.rows
            for cell_bounds in row.cells
            if cell_bounds is not None
        )
        column_boundaries = tuple(
            sorted({float(value) for bounds in detected_bounds for value in (bounds[0], bounds[2])})
        )
        row_boundaries = tuple(
            sorted({float(value) for bounds in detected_bounds for value in (bounds[1], bounds[3])})
        )
        header_ids_by_column: dict[int, str] = {}
        if header_in_first_row:
            for column_index, cell_bounds in enumerate(table.rows[0].cells):
                if cell_bounds is None:
                    continue
                column_span = _grid_span(
                    float(cell_bounds[0]),
                    float(cell_bounds[2]),
                    column_boundaries,
                )
                header_id = f"{table_id}_cell_0_{column_index}"
                for covered_column in range(column_index, column_index + column_span):
                    header_ids_by_column[covered_column] = header_id
        cells: list[TableCell] = []
        for row_index in range(table.row_count):
            geometry_row = table.rows[row_index]
            for column_index in range(table.col_count):
                raw_value = extracted_rows[row_index][column_index] or ""
                cell_bounds = geometry_row.cells[column_index]
                if cell_bounds is None:
                    continue
                column_span = _grid_span(
                    float(cell_bounds[0]),
                    float(cell_bounds[2]),
                    column_boundaries,
                )
                row_span = _grid_span(
                    float(cell_bounds[1]),
                    float(cell_bounds[3]),
                    row_boundaries,
                )
                is_header = header_in_first_row and row_index == 0
                linked_headers = tuple(
                    dict.fromkeys(
                        header_ids_by_column[covered_column]
                        for covered_column in range(
                            column_index,
                            column_index + column_span,
                        )
                        if covered_column in header_ids_by_column
                    )
                )
                cells.append(
                    TableCell(
                        cell_id=f"{table_id}_cell_{row_index}_{column_index}",
                        row_index=row_index,
                        column_index=column_index,
                        row_span=row_span,
                        column_span=column_span,
                        bbox=_bounding_box(cell_bounds, width=width, height=height),
                        raw_text_private=str(raw_value),
                        normalized_text_private=" ".join(str(raw_value).split()),
                        is_header=is_header,
                        header_cell_ids=() if is_header else linked_headers,
                        confidence=Decimal("0.90"),
                    )
                )
        records.append(
            TableRecord(
                table_id=table_id,
                bbox=_bounding_box(table.bbox, width=width, height=height),
                row_count=table.row_count,
                column_count=table.col_count,
                cells=tuple(cells),
                confidence=Decimal("0.90"),
            )
        )
    return tuple(records)


def _page_images(
    page: pymupdf.Page,
    *,
    page_number: int,
    width: float,
    height: float,
) -> tuple[PageImage, ...]:
    images: list[PageImage] = []
    for image_index, raw_image in enumerate(page.get_image_info(xrefs=True)):
        bounds = raw_image.get("bbox")
        pixel_width = int(raw_image.get("width", 0))
        pixel_height = int(raw_image.get("height", 0))
        if bounds is None or pixel_width < 1 or pixel_height < 1:
            continue
        images.append(
            PageImage(
                image_id=f"image_{page_number:03}_{image_index:03}",
                bbox=_bounding_box(bounds, width=width, height=height),
                pixel_width=pixel_width,
                pixel_height=pixel_height,
                xref=int(raw_image.get("xref", 0)),
            )
        )
    return tuple(images)


def _extract_page(page: pymupdf.Page, document_id: str, page_number: int) -> PageRecord:
    width = float(page.rect.width)
    height = float(page.rect.height)
    issues: list[str] = []

    try:
        text_blocks = _text_blocks(
            page,
            page_number=page_number,
            width=width,
            height=height,
        )
    except Exception:
        text_blocks = ()
        issues.append("native_text_extraction_failed")

    key_value_blocks = _key_value_blocks(text_blocks, page_number=page_number)
    try:
        tables = _table_records(
            page,
            page_number=page_number,
            width=width,
            height=height,
        )
    except Exception:
        tables = ()
        issues.append("table_extraction_failed")

    try:
        images = _page_images(
            page,
            page_number=page_number,
            width=width,
            height=height,
        )
    except Exception:
        images = ()
        issues.append("image_extraction_failed")

    text_character_count = sum(len(block.text_private) for block in text_blocks)
    if text_character_count == 0:
        issues.append("native_text_missing")
    issues = sorted(set(issues))
    accepted = not issues
    quality_profile = PageQualityProfile(
        text_character_count=text_character_count,
        text_block_count=len(text_blocks),
        key_value_count=len(key_value_blocks),
        table_count=len(tables),
        image_count=len(images),
        accepted=accepted,
        ocr_required=not accepted,
        issues=tuple(issues),
    )
    return PageRecord(
        document_id=document_id,
        page_number=page_number,
        width=width,
        height=height,
        text_blocks=text_blocks,
        key_value_blocks=key_value_blocks,
        tables=tables,
        images=images,
        reading_order=tuple(block.block_id for block in text_blocks),
        extraction_method=ExtractionMethod.NATIVE,
        quality_profile=quality_profile,
    )


def _probable_order_id(source: SourceDocument) -> str | None:
    values = {
        candidate.value_private
        for candidate in source.order_candidates
        if candidate.source is OrderIdSource.PDF_LABEL
    }
    return next(iter(values)) if len(values) == 1 else None


def _template_signature(source: SourceDocument, pages: tuple[PageRecord, ...]) -> str:
    structure = {
        "document_role": source.role.value,
        "page_count": len(pages),
        "pages": [
            {
                "height": round(page.height, 2),
                "image_count": len(page.images),
                "table_shapes": [[table.row_count, table.column_count] for table in page.tables],
                "text_block_count": len(page.text_blocks),
                "width": round(page.width, 2),
            }
            for page in pages
        ],
        "platform": source.platform.value,
    }
    serialized = json.dumps(structure, sort_keys=True, separators=(",", ":")).encode()
    return _digest(serialized)


def extract_pdf_document(source: SourceDocument, payload: bytes) -> ProcessedDocument:
    digest = _digest(payload)
    if digest != source.sha256 or len(payload) != source.byte_count:
        raise PdfProcessingError("PDF payload disagrees with the source document manifest")
    if f"doc_{digest[:16]}" != source.document_id:
        raise PdfProcessingError("PDF payload disagrees with the content-addressed document ID")

    try:
        pdf = pymupdf.open(  # type: ignore[no-untyped-call]
            stream=payload,
            filetype="pdf",
        )
    except Exception as exc:
        raise PdfProcessingError("PDF payload cannot be opened") from exc
    try:
        if pdf.page_count != source.page_count:
            raise PdfProcessingError("PDF page count disagrees with the source inventory")
        pages = tuple(
            _extract_page(
                pdf.load_page(index),  # type: ignore[no-untyped-call]
                source.document_id,
                index + 1,
            )
            for index in range(pdf.page_count)
        )
    finally:
        pdf.close()  # type: ignore[no-untyped-call]

    full_text = "\f".join(
        "\n".join(block.text_private for block in page.text_blocks) for page in pages
    )
    quality_accepted = all(page.quality_profile.accepted for page in pages)
    ocr_required = any(page.quality_profile.ocr_required for page in pages)
    manifest = DocumentManifest(
        document_id=source.document_id,
        sha256=source.sha256,
        source_filename_private=source.source_filename_private,
        file_size=source.byte_count,
        page_count=source.page_count,
        probable_platform=source.platform,
        probable_document_type=source.role,
        probable_order_id_private=_probable_order_id(source),
        template_signature=_template_signature(source, pages),
        native_text_available=all(page.quality_profile.text_character_count > 0 for page in pages),
        ocr_required=ocr_required,
        extraction_version=EXTRACTION_VERSION,
        processing_status=(
            ProcessingStatus.COMPLETE if quality_accepted else ProcessingStatus.QUARANTINED
        ),
        privacy_status=PrivacyStatus.PRIVATE,
    )
    document = DocumentRecord(
        document_id=source.document_id,
        page_count=len(pages),
        page_numbers=tuple(page.page_number for page in pages),
        full_text_sha256=_digest(full_text.encode()),
        text_character_count=sum(page.quality_profile.text_character_count for page in pages),
        table_count=sum(len(page.tables) for page in pages),
        image_count=sum(len(page.images) for page in pages),
        quality_accepted=quality_accepted,
    )
    return ProcessedDocument(manifest=manifest, document=document, pages=pages)


def _atomic_private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _inspection_markdown(processed: ProcessedDocument) -> str:
    sections = [
        f"# Document {processed.manifest.document_id}",
        "",
        "> Private inspection artifact. Do not publish without review and redaction.",
    ]
    for page in processed.pages:
        sections.extend(("", f"## Page {page.page_number}", ""))
        sections.extend(block.text_private for block in page.text_blocks)
        if not page.text_blocks:
            sections.append("_[No native text extracted; page requires OCR review.]_")
    return "\n".join(sections) + "\n"


def _render_pages(payload: bytes) -> tuple[bytes, ...]:
    pdf = pymupdf.open(  # type: ignore[no-untyped-call]
        stream=payload,
        filetype="pdf",
    )
    try:
        rendered: list[bytes] = []
        for page_index in range(pdf.page_count):
            page = pdf.load_page(page_index)  # type: ignore[no-untyped-call]
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5),  # type: ignore[no-untyped-call]
                alpha=False,
            )
            rendered.append(
                pixmap.pil_tobytes(
                    format="WEBP",
                    lossless=True,
                    method=6,
                    exact=True,
                )
            )
        return tuple(rendered)
    finally:
        pdf.close()  # type: ignore[no-untyped-call]


def _quarantine_payload(processed: ProcessedDocument) -> bytes:
    payload: dict[str, Any] = {
        "document_id": processed.manifest.document_id,
        "ocr_required": processed.manifest.ocr_required,
        "pages": [
            {
                "issues": list(page.quality_profile.issues),
                "page_number": page.page_number,
            }
            for page in processed.pages
            if not page.quality_profile.accepted
        ],
        "processing_status": processed.manifest.processing_status.value,
    }
    return f"{json.dumps(payload, indent=2, sort_keys=True)}\n".encode()


def write_document_artifacts(
    processed: ProcessedDocument,
    payload: bytes,
    output_root: Path,
) -> Path:
    if _digest(payload) != processed.manifest.sha256:
        raise PdfProcessingError("artifact payload disagrees with the processed document")
    document_root = output_root / processed.manifest.document_id
    _atomic_private_write(
        document_root / "manifest.json",
        f"{processed.manifest.model_dump_json(indent=2)}\n".encode(),
    )
    _atomic_private_write(
        document_root / "document.json",
        f"{processed.document.model_dump_json(indent=2)}\n".encode(),
    )
    _atomic_private_write(
        document_root / "pages.jsonl",
        "".join(f"{page.model_dump_json()}\n" for page in processed.pages).encode(),
    )
    _atomic_private_write(
        document_root / "document.md",
        _inspection_markdown(processed).encode(),
    )
    for page_number, rendered in enumerate(_render_pages(payload), start=1):
        _atomic_private_write(
            document_root / "evidence" / f"page-render-{page_number:03}.webp",
            rendered,
        )

    quarantine_path = document_root / "quarantine.json"
    if processed.manifest.processing_status is ProcessingStatus.QUARANTINED:
        _atomic_private_write(quarantine_path, _quarantine_payload(processed))
    else:
        quarantine_path.unlink(missing_ok=True)
    return document_root
