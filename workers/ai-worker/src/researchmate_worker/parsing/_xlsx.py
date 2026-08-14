"""Bounded OOXML parser for XLSX rows, shared strings, and sparse columns."""

from __future__ import annotations

from pathlib import Path
from re import search
from zipfile import ZipFile

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing._common import (
    MAX_XLSX_CELLS,
    MAX_XLSX_COLUMNS,
    MAX_XLSX_DENSE_CELL_GAP,
    MAX_XLSX_DENSE_ROW_COLUMNS,
    MAX_XLSX_OUTPUT_CHARS,
    MAX_XLSX_ROWS,
    MAX_XLSX_SHARED_STRINGS,
    _ParserMixinBase,
)
from researchmate_worker.parsing_helpers import _normalized_archive_member


class _XlsxParserMixin(_ParserMixinBase):
    """Extract spreadsheet rows without loading a heavyweight workbook runtime."""

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
            if len(members) > self.max_num_pages:  # type: ignore[attr-defined]
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
            f"{XlsxColumnLabels.from_index(column)}={value}" for column, value in ordered if value
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


# Expose the column label helper as a module-level callable so the static render method
# in _render_xlsx_row can reference it without leaking a private name into the public class
# symbol table. Kept for parity with the original single-file parser.
class XlsxColumnLabels:
    """Wrap A1-style column label conversion for module-level reuse."""

    @staticmethod
    def from_index(index: int) -> str:
        """Mirror the private _xlsx_column_label static method on the parser mixin."""
        label = ""
        current = index + 1
        while current:
            current, remainder = divmod(current - 1, 26)
            label = chr(ord("A") + remainder) + label
        return label
