"""PDF text extraction without loading Docling's high-memory vision models."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing._common import _ParserMixinBase
from researchmate_worker.parsing_helpers import _package_version


class _PDFParserMixin(_ParserMixinBase):
    """Reserve Docling's visual pipeline for PDFs that lack an extractable text layer."""

    artifacts_path: Any | None
    converter: Any | None

    def _parse_pdf_lightweight(self, source: Path) -> list[ParsedBlock]:
        """Extract searchable PDF text without loading Docling's vision models."""
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ParserAdapterError("PARSER_NOT_INSTALLED") from exc
        try:
            reader = PdfReader(source, strict=False)
            if len(reader.pages) > self.max_num_pages:  # type: ignore[attr-defined]
                raise ParserAdapterError("PARSER_PAGE_LIMIT_EXCEEDED")
            blocks: list[ParsedBlock] = []
            for page_index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if not text:
                    continue
                item_ref = f"pdf#page-{page_index}"
                blocks.append(
                    ParsedBlock(
                        text=text,
                        page_no=page_index,
                        metadata={
                            "parser_name": "pypdf",
                            "parser_version": _package_version("pypdf"),
                            "source_item_ref": item_ref,
                            "source_ordinal": page_index - 1,
                            "source_label": "page_text",
                            "source_level": None,
                            "source_anchors": self._structural_anchor(
                                item_ref,
                                locator_kind="page",
                                page_no=page_index,
                            ),
                        },
                    )
                )
        except ParserAdapterError:
            raise
        except Exception as exc:
            raise ParserAdapterError("PARSER_EXECUTION_FAILED") from exc
        if not blocks:
            raise ParserAdapterError("PARSER_TEXT_LAYER_NOT_FOUND")
        return blocks

    def _pdf_converter(self) -> Any:
        if self.converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import (
                    DocumentConverter,
                    PdfFormatOption,
                )
            except ImportError as exc:
                raise ParserAdapterError("PARSER_NOT_INSTALLED") from exc
            pdf_options = PdfPipelineOptions(
                artifacts_path=self.artifacts_path,
                enable_remote_services=False,
            )
            self.converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                },
            )
        return self.converter


def convert_with_docling(
    *,
    converter: Any,
    source: Path,
    max_file_size: int,
    max_num_pages: int,
) -> Any:
    """Drive the Docling DocumentConverter for a PDF that lacks a lightweight text layer."""
    from docling.datamodel.base_models import DocumentStream

    return converter.convert(
        DocumentStream(name=source.name, stream=BytesIO(source.read_bytes())),
        raises_on_error=False,
        max_file_size=max_file_size,
        max_num_pages=max_num_pages,
    )
