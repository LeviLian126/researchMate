"""Parse supported documents into bounded, provenance-aware blocks for ingestion.

This package was split out of the former single-file ``parsing.py`` module. The public
surface is preserved: ``DoclingDocumentParser``, ``SUPPORTED_FILE_TYPES`` and the
helpers used across the test suite continue to import cleanly from
``researchmate_worker.parsing``.

The dispatch entry point is the ``DoclingDocumentParser.parse`` method, which routes
each supported file type to a format-specific mixin. Mixins live alongside this
``__init__`` module:

* ``_common`` — shared archive readers, text decoder, and the HTML/text parsers.
* ``_pdf`` — pypdf lightweight extraction and the Docling visual pipeline fallback.
* ``_docx`` — OOXML Word paragraphs and heading hierarchy.
* ``_pptx`` — OOXML slide ordering and text extraction.
* ``_xlsx`` — OOXML worksheet streaming, shared strings, and bounded rows.
* ``_notebook`` — Jupyter notebook source cells without outputs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing._common import (
    MAX_OOXML_TOTAL_DECOMPRESSED_BYTES,  # noqa: F401 - re-exported for backward compatibility
    MAX_TEXT_BLOCK_CHARS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_CELLS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_COLUMNS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_DENSE_CELL_GAP,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_DENSE_ROW_COLUMNS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_OUTPUT_CHARS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_ROWS,  # noqa: F401 - re-exported for backward compatibility
    MAX_XLSX_SHARED_STRINGS,  # noqa: F401 - re-exported for backward compatibility
    SUPPORTED_FILE_TYPES,  # noqa: F401 - re-exported for backward compatibility
    TEXT_FILE_TYPES,  # noqa: F401 - re-exported for backward compatibility
    _ArchiveReadBudget,  # noqa: F401 - re-exported for backward compatibility
    _ParserMixinBase,  # noqa: F401 - re-exported for backward compatibility
    _VisibleHTMLTextParser,  # noqa: F401 - re-exported for backward compatibility
)
from researchmate_worker.parsing._docx import _DocxParserMixin
from researchmate_worker.parsing._notebook import _NotebookParserMixin
from researchmate_worker.parsing._pdf import _PDFParserMixin, convert_with_docling
from researchmate_worker.parsing._pptx import _PptxParserMixin
from researchmate_worker.parsing._xlsx import _XlsxParserMixin
from researchmate_worker.parsing_helpers import (  # noqa: F401 - re-exported for backward compatibility
    _normalized_archive_member,
    _package_version,
    _serialize_provenance,
)

LOGGER = logging.getLogger(__name__)

__all__ = [
    "DoclingDocumentParser",
    "SUPPORTED_FILE_TYPES",
    "TEXT_FILE_TYPES",
    "MAX_TEXT_BLOCK_CHARS",
    "MAX_OOXML_TOTAL_DECOMPRESSED_BYTES",
    "MAX_XLSX_ROWS",
    "MAX_XLSX_CELLS",
    "MAX_XLSX_COLUMNS",
    "MAX_XLSX_SHARED_STRINGS",
    "MAX_XLSX_DENSE_ROW_COLUMNS",
    "MAX_XLSX_DENSE_CELL_GAP",
    "MAX_XLSX_OUTPUT_CHARS",
    "_serialize_provenance",
    "_ArchiveReadBudget",
    "_VisibleHTMLTextParser",
]


class DoclingDocumentParser(
    _DocxParserMixin,
    _PptxParserMixin,
    _XlsxParserMixin,
    _NotebookParserMixin,
    _PDFParserMixin,
):
    """Resource-aware parser that reserves Docling's visual pipeline for PDFs.

    Each format mixin inherits ``_ParserMixinBase`` for the shared archive readers,
    text decoder, and HTML/text parsers. The PDF mixin adds the lightweight
    pypdf extractor and the Docling visual pipeline fallback.
    """

    def __init__(
        self,
        *,
        max_file_size: int,
        max_num_pages: int,
        artifacts_path: Path | None = None,
        converter: Any | None = None,
        pdf_backend: str = "pypdf",
    ) -> None:
        self.max_file_size = max_file_size
        self.max_num_pages = max_num_pages
        self.artifacts_path = artifacts_path
        self.converter = converter
        self.pdf_backend = "docling" if converter is not None else pdf_backend

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        """Validate the file boundary and route it to the configured bounded parser."""
        if file_type not in SUPPORTED_FILE_TYPES:
            raise ParserAdapterError("UNSUPPORTED_DOCUMENT_TYPE")
        try:
            if source.stat().st_size > self.max_file_size:
                raise ParserAdapterError("PARSER_FILE_TOO_LARGE")
            if file_type == "docx":
                blocks = self._parse_docx(source)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if file_type == "pptx":
                blocks = self._parse_pptx(source)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if file_type == "xlsx":
                blocks = self._parse_xlsx(source)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if file_type == "html":
                blocks = self._parse_html(source)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if file_type == "ipynb":
                blocks = self._parse_notebook(source)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if file_type in TEXT_FILE_TYPES:
                blocks = self._parse_text(source, file_type=file_type)
                if not blocks:
                    raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
                return blocks
            if self.pdf_backend == "pypdf":
                return self._parse_pdf_lightweight(source)
        except ParserAdapterError:
            raise
        except (
            BadZipFile,
            ElementTree.ParseError,
            json.JSONDecodeError,
            IndexError,
            KeyError,
            OSError,
            ValueError,
        ) as exc:
            LOGGER.exception(
                "office_document_parse_failed file_type=%s source_size=%s error_type=%s",
                file_type,
                source.stat().st_size if source.exists() else None,
                type(exc).__name__,
            )
            raise ParserAdapterError("PARSER_EXECUTION_FAILED") from exc
        try:
            from docling_core.types.doc.document import ContentLayer, TableItem, TextItem

            result = convert_with_docling(
                converter=self._pdf_converter(),
                source=source,
                max_file_size=self.max_file_size,
                max_num_pages=self.max_num_pages,
            )
        except ParserAdapterError:
            raise
        except Exception as exc:
            raise ParserAdapterError("PARSER_EXECUTION_FAILED") from exc
        if getattr(result.status, "value", str(result.status)) != "success":
            raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")

        document = result.document
        locator_kind = "page"
        parser_metadata = {
            "parser_name": "docling",
            "parser_version": _package_version("docling"),
            "parser_core_version": _package_version("docling-core"),
        }
        blocks: list[ParsedBlock] = []
        section_stack: list[str] = []
        try:
            items = document.iterate_items(
                with_groups=False,
                traverse_pictures=False,
                included_content_layers={ContentLayer.BODY},
            )
            for ordinal, (item, level) in enumerate(items):
                if isinstance(item, TextItem):
                    item_text = item.text.strip()
                elif isinstance(item, TableItem):
                    item_text = item.export_to_markdown(doc=document).strip()
                else:
                    continue
                if not item_text:
                    continue
                label = getattr(item.label, "value", str(item.label))
                if label in {"title", "section_header"}:
                    heading_level = max(1, int(level or 1))
                    section_stack = section_stack[: heading_level - 1]
                    section_stack.append(item_text)
                active_section = section_stack[-1] if section_stack else None
                anchors = _serialize_provenance(item, locator_kind=locator_kind)
                primary_page = anchors[0]["page_no"]
                blocks.append(
                    ParsedBlock(
                        text=item_text,
                        page_no=primary_page,
                        slide_no=None,
                        section_title=active_section,
                        metadata={
                            **parser_metadata,
                            "source_item_ref": item.self_ref,
                            "source_ordinal": ordinal,
                            "source_label": label,
                            "source_level": level,
                            "section_path": list(section_stack),
                            "source_anchors": anchors,
                        },
                    )
                )
        except Exception as exc:
            raise ParserAdapterError("PARSER_OUTPUT_INVALID") from exc
        return blocks
