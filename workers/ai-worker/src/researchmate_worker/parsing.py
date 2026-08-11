"""Parse supported documents into bounded, provenance-aware blocks for ingestion."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from re import IGNORECASE, search
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

TEXT_FILE_TYPES = {
    "txt",
    "md",
    "csv",
    "tsv",
    "json",
    "jsonl",
    "xml",
    "yaml",
    "toml",
    "rst",
    "log",
    "tex",
    "bib",
    "py",
    "js",
    "jsx",
    "ts",
    "tsx",
    "css",
    "scss",
    "sql",
    "sh",
    "ps1",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "go",
    "rs",
    "php",
    "rb",
    "swift",
    "kt",
    "kts",
}
SUPPORTED_FILE_TYPES = {"pdf", "docx", "pptx", "xlsx", "html", "ipynb", *TEXT_FILE_TYPES}
MAX_TEXT_BLOCK_CHARS = 8_000
MAX_OOXML_TOTAL_DECOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_XLSX_ROWS = 20_000
MAX_XLSX_CELLS = 200_000
MAX_XLSX_COLUMNS = 16_384
MAX_XLSX_SHARED_STRINGS = 100_000
MAX_XLSX_DENSE_ROW_COLUMNS = 1_024
MAX_XLSX_DENSE_CELL_GAP = 32
MAX_XLSX_OUTPUT_CHARS = 8 * 1024 * 1024


@dataclass
class _ArchiveReadBudget:
    """Track aggregate decompressed XML before parsed objects can amplify one archive."""

    limit_bytes: int
    consumed_bytes: int = 0

    def consume(self, count: int) -> None:
        """Reject an archive once its cumulative decompressed XML exceeds the limit."""
        self.consumed_bytes += count
        if self.consumed_bytes > self.limit_bytes:
            raise ParserAdapterError("PARSER_FILE_TOO_LARGE")


class _VisibleHTMLTextParser(HTMLParser):
    """Collect visible HTML text while excluding executable and styling content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif not self.hidden_depth and tag in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


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

    def _archive_read_budget(self) -> _ArchiveReadBudget:
        """Create one shared decompression budget for an OOXML package."""
        return _ArchiveReadBudget(
            limit_bytes=min(self.max_file_size * 4, MAX_OOXML_TOTAL_DECOMPRESSED_BYTES)
        )

    def _read_bounded_xml(
        self,
        archive: ZipFile,
        member: str,
        *,
        budget: _ArchiveReadBudget,
    ) -> ElementTree.Element:
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
        # Stream-decompress with a running byte counter to guard against zip bombs
        # that report a small file_size but embed a large decompressed payload.
        decompressed = bytearray()
        with archive.open(resolved) as stream:
            while len(decompressed) <= max_xml_bytes:
                chunk = stream.read(65536)
                if not chunk:
                    break
                budget.consume(len(chunk))
                decompressed.extend(chunk)
            if len(decompressed) > max_xml_bytes:
                raise ParserAdapterError("PARSER_FILE_TOO_LARGE")
        return ElementTree.fromstring(decompressed)

    def _iter_bounded_xlsx_rows(
        self,
        archive: ZipFile,
        member: str,
        *,
        budget: _ArchiveReadBudget,
    ) -> Iterator[ElementTree.Element]:
        """Stream worksheet rows so limits apply before a full XML tree is retained."""
        requested = _normalized_archive_member(member)
        resolved = next(
            (
                candidate
                for candidate in archive.namelist()
                if _normalized_archive_member(candidate) == requested
            ),
            None,
        )
        if resolved is None:
            raise KeyError(requested)
        max_xml_bytes = min(self.max_file_size * 4, MAX_OOXML_TOTAL_DECOMPRESSED_BYTES)
        row_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"
        parser = ElementTree.XMLPullParser(events=("start", "end"))
        stack: list[ElementTree.Element] = []
        member_bytes = 0
        try:
            with archive.open(resolved) as stream:
                while chunk := stream.read(65_536):
                    member_bytes += len(chunk)
                    budget.consume(len(chunk))
                    if member_bytes > max_xml_bytes:
                        raise ParserAdapterError("PARSER_FILE_TOO_LARGE")
                    parser.feed(chunk)
                    for event, element in parser.read_events():
                        if event == "start":
                            stack.append(element)
                            continue
                        if element.tag == row_tag:
                            yield element
                            if len(stack) > 1:
                                stack[-2].remove(element)
                        stack.pop()
            parser.close()
        except ElementTree.ParseError as exc:
            raise ParserAdapterError("PARSER_INVALID_OOXML") from exc

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
            root = self._read_bounded_xml(
                archive,
                "word/document.xml",
                budget=self._archive_read_budget(),
            )
        blocks: list[ParsedBlock] = []
        section_stack: list[str] = []
        for ordinal, paragraph in enumerate(root.findall(".//w:p", ns)):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
            if not text:
                continue
            style = paragraph.find("./w:pPr/w:pStyle", ns)
            style_name = style.attrib.get(value_attribute, "") if style is not None else ""
            style_match = search(r"(?:heading|title)\s*(\d+)?", style_name, flags=IGNORECASE)
            heading_level = int(style_match.group(1) or 1) if style_match else None
            if heading_level is not None:
                section_stack = section_stack[: heading_level - 1]
                section_stack.append(text)
            active_section = section_stack[-1] if section_stack else None
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
                        "source_level": heading_level,
                        "section_path": list(section_stack),
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
            budget = self._archive_read_budget()
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
            roots = [
                (member, self._read_bounded_xml(archive, member, budget=budget))
                for member in members
            ]
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
                            "section_path": [section_title] if section_title else [],
                            "source_anchors": self._structural_anchor(
                                item_ref, locator_kind="slide"
                            ),
                        },
                    )
                )
        return blocks

    @staticmethod
    def _decode_text(data: bytes) -> str:
        """Decode common text encodings and reject binary-looking payloads."""
        encodings = ["utf-8-sig"]
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            encodings.insert(0, "utf-16")
        encodings.extend(["gb18030", "cp1252"])
        for encoding in encodings:
            try:
                text = data.decode(encoding)
            except UnicodeDecodeError:
                continue
            controls = sum(ord(char) < 32 and char not in "\n\r\t\f" for char in text)
            if "\x00" not in text and controls <= max(4, len(text) // 50):
                return text
        raise ParserAdapterError("PARSER_TEXT_ENCODING_UNSUPPORTED")

    def _text_blocks(self, text: str, *, parser_name: str, source_label: str) -> list[ParsedBlock]:
        """Split decoded text into bounded blocks with stable line-based provenance."""
        blocks: list[ParsedBlock] = []
        pending: list[str] = []
        pending_chars = 0
        start_line = 1

        def flush(end_line: int) -> None:
            nonlocal pending, pending_chars, start_line
            value = "\n".join(pending).strip()
            if value:
                ordinal = len(blocks)
                item_ref = f"text#line-{start_line}-{end_line}"
                blocks.append(
                    ParsedBlock(
                        text=value,
                        metadata={
                            "parser_name": parser_name,
                            "parser_version": "stdlib",
                            "source_item_ref": item_ref,
                            "source_ordinal": ordinal,
                            "source_label": source_label,
                            "source_level": None,
                            "section_path": [],
                            "source_anchors": self._structural_anchor(
                                item_ref, locator_kind="line"
                            ),
                        },
                    )
                )
            pending = []
            pending_chars = 0

        for line_no, line in enumerate(text.splitlines(), start=1):
            if pending and (
                not line.strip() or pending_chars + len(line) + 1 > MAX_TEXT_BLOCK_CHARS
            ):
                flush(line_no - 1)
                start_line = line_no + (0 if line.strip() else 1)
            if line.strip():
                if not pending:
                    start_line = line_no
                pending.append(line.rstrip())
                pending_chars += len(line) + 1
        flush(max(start_line, len(text.splitlines())))
        return blocks

    def _parse_text(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        text = self._decode_text(source.read_bytes())
        return self._text_blocks(text, parser_name="text", source_label=file_type)

    def _parse_html(self, source: Path) -> list[ParsedBlock]:
        parser = _VisibleHTMLTextParser()
        parser.feed(self._decode_text(source.read_bytes()))
        return self._text_blocks(
            "".join(parser.parts), parser_name="html.parser", source_label="visible_text"
        )

    def _parse_notebook(self, source: Path) -> list[ParsedBlock]:
        payload = json.loads(self._decode_text(source.read_bytes()))
        if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
            raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")
        blocks: list[ParsedBlock] = []
        for ordinal, cell in enumerate(payload["cells"]):
            if not isinstance(cell, dict) or cell.get("cell_type") not in {
                "markdown",
                "code",
                "raw",
            }:
                continue
            source_value = cell.get("source")
            if isinstance(source_value, list):
                text = "".join(str(part) for part in source_value).strip()
            elif isinstance(source_value, str):
                text = source_value.strip()
            else:
                continue
            if not text:
                continue
            item_ref = f"notebook#cell-{ordinal}"
            blocks.append(
                ParsedBlock(
                    text=text,
                    metadata={
                        "parser_name": "json",
                        "parser_version": "stdlib",
                        "source_item_ref": item_ref,
                        "source_ordinal": ordinal,
                        "source_label": str(cell["cell_type"]),
                        "source_level": None,
                        "section_path": [],
                        "source_anchors": self._structural_anchor(item_ref, locator_kind="cell"),
                    },
                )
            )
        return blocks

    def _parse_xlsx(self, source: Path) -> list[ParsedBlock]:
        spreadsheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        ns = {"s": spreadsheet_ns}
        with ZipFile(source) as archive:
            budget = self._archive_read_budget()
            shared_strings: list[str] = []
            try:
                shared_root = self._read_bounded_xml(
                    archive,
                    "xl/sharedStrings.xml",
                    budget=budget,
                )
            except KeyError:
                shared_root = None
            if shared_root is not None:
                shared_strings = [
                    "".join(node.text or "" for node in item.findall(".//s:t", ns))
                    for item in shared_root.findall(".//s:si", ns)
                ]
                if len(shared_strings) > MAX_XLSX_SHARED_STRINGS:
                    raise ParserAdapterError("PARSER_SPREADSHEET_LIMIT_EXCEEDED")
            members = [
                member
                for member in archive.namelist()
                if search(r"^xl/worksheets/sheet\d+\.xml$", _normalized_archive_member(member))
            ]
            members.sort(
                key=lambda member: int(
                    search(r"sheet(\d+)\.xml$", _normalized_archive_member(member)).group(1)  # type: ignore[union-attr]
                )
            )
            if len(members) > self.max_num_pages:
                raise ParserAdapterError("PARSER_PAGE_LIMIT_EXCEEDED")
            blocks: list[ParsedBlock] = []
            row_count = 0
            cell_count = 0
            output_chars = 0
            for sheet_index, member in enumerate(members, start=1):
                for row in self._iter_bounded_xlsx_rows(archive, member, budget=budget):
                    row_count += 1
                    cells = row.findall("s:c", ns)
                    cell_count += len(cells)
                    if row_count > MAX_XLSX_ROWS or cell_count > MAX_XLSX_CELLS:
                        raise ParserAdapterError("PARSER_SPREADSHEET_LIMIT_EXCEEDED")
                    values: list[tuple[int, str]] = []
                    for fallback_column, cell in enumerate(cells):
                        reference = cell.attrib.get("r", "")
                        column = (
                            self._xlsx_column_index(reference) if reference else fallback_column
                        )
                        if column >= MAX_XLSX_COLUMNS:
                            raise ParserAdapterError("PARSER_SPREADSHEET_LIMIT_EXCEEDED")
                        cell_type = cell.attrib.get("t")
                        if cell_type == "inlineStr":
                            value = "".join(node.text or "" for node in cell.findall(".//s:t", ns))
                        else:
                            value_node = cell.find("s:v", ns)
                            value = (value_node.text or "") if value_node is not None else ""
                            if cell_type == "s" and value:
                                index = int(value)
                                value = (
                                    shared_strings[index]
                                    if 0 <= index < len(shared_strings)
                                    else value
                                )
                            elif cell_type == "b":
                                value = "TRUE" if value == "1" else "FALSE"
                        values.append((column, value.strip()))
                    row_text = self._render_xlsx_row(values)
                    if not row_text:
                        continue
                    output_chars += len(row_text)
                    if output_chars > MAX_XLSX_OUTPUT_CHARS:
                        raise ParserAdapterError("PARSER_SPREADSHEET_LIMIT_EXCEEDED")
                    row_no = int(row.attrib.get("r", len(blocks) + 1))
                    item_ref = f"{_normalized_archive_member(member)}#row-{row_no}"
                    blocks.append(
                        ParsedBlock(
                            text=row_text,
                            page_no=sheet_index,
                            section_title=f"Sheet {sheet_index}",
                            metadata={
                                "parser_name": "ooxml",
                                "parser_version": "stdlib",
                                "source_item_ref": item_ref,
                                "source_ordinal": row_no - 1,
                                "source_label": "spreadsheet_row",
                                "source_level": None,
                                "section_path": [f"Sheet {sheet_index}"],
                                "source_anchors": self._structural_anchor(
                                    item_ref, locator_kind="sheet", page_no=sheet_index
                                ),
                            },
                        )
                    )
        return blocks

    @staticmethod
    def _render_xlsx_row(values: list[tuple[int, str]]) -> str:
        """Render dense rows as TSV and sparse rows with explicit column labels."""
        if not values:
            return ""
        ordered = sorted(values)
        maximum_column = ordered[-1][0]
        largest_gap = max(
            (right[0] - left[0] for left, right in zip(ordered, ordered[1:], strict=False)),
            default=0,
        )
        if maximum_column < MAX_XLSX_DENSE_ROW_COLUMNS and largest_gap <= MAX_XLSX_DENSE_CELL_GAP:
            dense_values = [""] * (maximum_column + 1)
            for column, value in ordered:
                dense_values[column] = value
            return "\t".join(dense_values).rstrip()
        return "\t".join(
            f"{DoclingDocumentParser._xlsx_column_label(column)}={value}"
            for column, value in ordered
            if value
        )

    @staticmethod
    def _xlsx_column_label(index: int) -> str:
        """Convert a zero-based column index to an A1-style column label."""
        label = ""
        current = index + 1
        while current:
            current, remainder = divmod(current - 1, 26)
            label = chr(ord("A") + remainder) + label
        return label

    @staticmethod
    def _xlsx_column_index(reference: str) -> int:
        """Convert an A1-style cell reference to a zero-based column index."""
        letters = "".join(character for character in reference.upper() if character.isalpha())
        if not letters:
            return 0
        index = 0
        for character in letters:
            index = index * 26 + ord(character) - ord("A") + 1
        return index - 1

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
            from docling.datamodel.base_models import DocumentStream
            from docling_core.types.doc.document import ContentLayer, TableItem, TextItem

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
