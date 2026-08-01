"""Parse supported documents into bounded, provenance-aware blocks for ingestion."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from re import search
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing_helpers import (
    _normalized_archive_member,
    _package_version,
    _serialize_provenance,
)

LOGGER = logging.getLogger(__name__)


class DoclingDocumentParser:
    """Resource-aware parser that reserves Docling's visual pipeline for PDFs."""

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

    def _parse_pdf_lightweight(self, source: Path) -> list[ParsedBlock]:
        """Extract searchable PDF text without loading Docling's vision models."""
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ParserAdapterError("PARSER_NOT_INSTALLED") from exc
        try:
            reader = PdfReader(source, strict=False)
            if len(reader.pages) > self.max_num_pages:
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

    def _read_bounded_xml(self, archive: ZipFile, member: str) -> ElementTree.Element:
        requested = _normalized_archive_member(member)
        resolved = next(
            (
                candidate
                for candidate in archive.namelist()
                if _normalized_archive_member(candidate) == requested
            ),
            member,
        )
        info = archive.getinfo(resolved)
        max_xml_bytes = min(self.max_file_size * 4, 32 * 1024 * 1024)
        if info.file_size > max_xml_bytes:
            raise ParserAdapterError("PARSER_FILE_TOO_LARGE")
        return ElementTree.fromstring(archive.read(resolved))

    @staticmethod
    def _structural_anchor(
        item_ref: str,
        *,
        locator_kind: str,
        page_no: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "item_ref": item_ref,
                "locator_kind": locator_kind,
                "page_no": page_no,
                "bbox": None,
                "charspan": None,
            }
        ]

    def _parse_docx(self, source: Path) -> list[ParsedBlock]:
        word_namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ns = {"w": word_namespace}
        value_attribute = f"{{{word_namespace}}}val"
        with ZipFile(source) as archive:
            root = self._read_bounded_xml(archive, "word/document.xml")
        blocks: list[ParsedBlock] = []
        active_section: str | None = None
        for ordinal, paragraph in enumerate(root.findall(".//w:p", ns)):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
            if not text:
                continue
            style = paragraph.find("./w:pPr/w:pStyle", ns)
            style_name = style.attrib.get(value_attribute, "") if style is not None else ""
            if style_name.lower().startswith(("heading", "title")):
                active_section = text
            item_ref = f"word/document.xml#paragraph-{ordinal}"
            blocks.append(
                ParsedBlock(
                    text=text,
                    section_title=active_section,
                    metadata={
                        "parser_name": "ooxml",
                        "parser_version": "stdlib",
                        "source_item_ref": item_ref,
                        "source_ordinal": ordinal,
                        "source_label": style_name or "paragraph",
                        "source_level": None,
                        "source_anchors": self._structural_anchor(
                            item_ref, locator_kind="structural"
                        ),
                    },
                )
            )
        return blocks

    def _parse_pptx(self, source: Path) -> list[ParsedBlock]:
        drawing_namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
        ns = {"a": drawing_namespace}
        with ZipFile(source) as archive:
            members = [
                member
                for member in archive.namelist()
                if search(
                    r"^ppt/slides/slide\d+\.xml$",
                    _normalized_archive_member(member),
                )
            ]
            members.sort(
                key=lambda member: int(
                    search(
                        r"slide(\d+)\.xml$",
                        _normalized_archive_member(member),
                    ).group(1)  # type: ignore[union-attr]
                )
            )
            if len(members) > self.max_num_pages:
                raise ParserAdapterError("PARSER_PAGE_LIMIT_EXCEEDED")
            roots = [(member, self._read_bounded_xml(archive, member)) for member in members]
        blocks: list[ParsedBlock] = []
        for member, root in roots:
            normalized_member = _normalized_archive_member(member)
            match = search(r"slide(\d+)\.xml$", normalized_member)
            slide_no = int(match.group(1)) if match else None
            slide_texts = []
            for paragraph in root.findall(".//a:p", ns):
                text = "".join(node.text or "" for node in paragraph.findall(".//a:t", ns)).strip()
                if text:
                    slide_texts.append(text)
            section_title = slide_texts[0] if slide_texts else None
            for ordinal, text in enumerate(slide_texts):
                item_ref = f"{normalized_member}#paragraph-{ordinal}"
                blocks.append(
                    ParsedBlock(
                        text=text,
                        slide_no=slide_no,
                        section_title=section_title,
                        metadata={
                            "parser_name": "ooxml",
                            "parser_version": "stdlib",
                            "source_item_ref": item_ref,
                            "source_ordinal": ordinal,
                            "source_label": "slide_text",
                            "source_level": None,
                            "source_anchors": self._structural_anchor(
                                item_ref, locator_kind="slide"
                            ),
                        },
                    )
                )
        return blocks

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        """Validate the file boundary and route it to the configured bounded parser."""
        if file_type not in {"pdf", "docx", "pptx"}:
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
            if self.pdf_backend == "pypdf":
                return self._parse_pdf_lightweight(source)
        except ParserAdapterError:
            raise
        except (BadZipFile, ElementTree.ParseError, KeyError, OSError) as exc:
            LOGGER.exception(
                "office_document_parse_failed file_type=%s source_size=%s error_type=%s",
                file_type,
                source.stat().st_size if source.exists() else None,
                type(exc).__name__,
            )
            raise ParserAdapterError("PARSER_EXECUTION_FAILED") from exc
        try:
            from docling.datamodel.base_models import DocumentStream
            from docling_core.types.doc import ContentLayer, TableItem, TextItem

            result = self._pdf_converter().convert(
                DocumentStream(name=source.name, stream=BytesIO(source.read_bytes())),
                raises_on_error=False,
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
        active_section: str | None = None
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
                    active_section = item_text
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
                            "source_anchors": anchors,
                        },
                    )
                )
        except Exception as exc:
            raise ParserAdapterError("PARSER_OUTPUT_INVALID") from exc
        return blocks
