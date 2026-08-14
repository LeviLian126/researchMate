"""Bounded OOXML parser for Word document.xml paragraphs and headings."""

from __future__ import annotations

from pathlib import Path
from re import IGNORECASE, search
from zipfile import ZipFile

from researchmate_worker.ingestion import ParsedBlock
from researchmate_worker.parsing._common import _ParserMixinBase


class _DocxParserMixin(_ParserMixinBase):
    """Extract Word paragraphs while tracking the active heading path."""

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
