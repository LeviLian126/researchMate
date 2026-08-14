"""Shared parser constants, bounds, and helpers used across document formats."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from re import IGNORECASE, search  # noqa: F401 - re-exported for format modules
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing_helpers import (
    _normalized_archive_member,
    _serialize_provenance,  # noqa: F401 - re-exported for backward compatibility
)

LOGGER = logging.getLogger(__name__)

# Plain-text extensions routed through the lightweight text decoder.
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
# Every format the bounded parser can route without raising UNSUPPORTED_DOCUMENT_TYPE.
SUPPORTED_FILE_TYPES = {"pdf", "docx", "pptx", "xlsx", "html", "ipynb", *TEXT_FILE_TYPES}

# Text-decomposition bounds shared by the plain-text and HTML parsers.
MAX_TEXT_BLOCK_CHARS = 8_000

# Aggregate decompression budget for any OOXML package before parsed rows amplify it.
MAX_OOXML_TOTAL_DECOMPRESSED_BYTES = 64 * 1024 * 1024

# XLSX-specific guardrails so one compressed workbook cannot fan out unbounded rows.
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


class _ParserMixinBase:
    """Hold the shared OOXML archive readers, text decoder, and bounded text splitter."""

    max_file_size: int
    max_num_pages: int
    artifacts_path: Any | None
    converter: Any | None
    pdf_backend: str

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

    def _parse_text(self, source: Any, *, file_type: str) -> list[ParsedBlock]:
        text = self._decode_text(source.read_bytes())
        return self._text_blocks(text, parser_name="text", source_label=file_type)

    def _parse_html(self, source: Any) -> list[ParsedBlock]:
        parser = _VisibleHTMLTextParser()
        parser.feed(self._decode_text(source.read_bytes()))
        return self._text_blocks(
            "".join(parser.parts), parser_name="html.parser", source_label="visible_text"
        )
