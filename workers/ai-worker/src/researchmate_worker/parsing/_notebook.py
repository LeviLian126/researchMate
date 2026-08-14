"""Bounded parser for Jupyter notebook cells excluding generated outputs."""

from __future__ import annotations

import json
from pathlib import Path

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError
from researchmate_worker.parsing._common import _ParserMixinBase


class _NotebookParserMixin(_ParserMixinBase):
    """Index notebook source cells while excluding generated output payloads."""

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
