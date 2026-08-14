"""Bounded OOXML parser for PowerPoint slides and ordered slide text."""

from __future__ import annotations

from pathlib import Path
from re import search
from zipfile import ZipFile

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing._common import _ParserMixinBase
from researchmate_worker.parsing_helpers import _normalized_archive_member


class _PptxParserMixin(_ParserMixinBase):
    """Preserve logical slide order independently of archive member ordering."""

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
            if len(members) > self.max_num_pages:  # type: ignore[attr-defined]
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
