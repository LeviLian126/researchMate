"""Create structure-aware retrieval chunks with stable normalized provenance offsets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from researchmate_worker.ingestion_models import ParsedBlock

MAX_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 180


@dataclass(frozen=True)
class ChunkProjection:
    """Describe one chunk before owner and deterministic identity fields are attached."""

    text: str
    page_no: int | None
    slide_no: int | None
    section_title: str | None
    section_path: tuple[str, ...]
    chunk_index: int
    char_start: int
    char_end: int
    metadata: dict[str, object]


@dataclass(frozen=True)
class _Unit:
    """Carry one indivisible semantic unit and its normalized group-stream offsets."""

    text: str
    start: int
    end: int
    anchors: list[object]


def build_structure_chunks(blocks: list[ParsedBlock]) -> list[ChunkProjection]:
    """Chunk only within a shared locator and section, preserving whole-unit overlap."""
    projections: list[ChunkProjection] = []
    groups: list[list[ParsedBlock]] = []
    for block in blocks:
        if not block.text.strip():
            continue
        key = _group_key(block)
        if not groups or _group_key(groups[-1][0]) != key:
            groups.append([block])
        else:
            groups[-1].append(block)

    for group in groups:
        units = _group_units(group)
        cursor = 0
        while cursor < len(units):
            selected: list[_Unit] = []
            size = 0
            while cursor < len(units):
                unit = units[cursor]
                separator = 2 if selected else 0
                if selected and size + separator + len(unit.text) > MAX_CHUNK_CHARS:
                    break
                selected.append(unit)
                size += separator + len(unit.text)
                cursor += 1
                if size >= MAX_CHUNK_CHARS:
                    break
            if not selected:
                cursor += 1
                continue
            block = group[0]
            path = _section_path(block)
            projections.append(
                ChunkProjection(
                    text="\n\n".join(unit.text for unit in selected),
                    page_no=block.page_no,
                    slide_no=block.slide_no,
                    section_title=block.section_title,
                    section_path=path,
                    chunk_index=len(projections),
                    char_start=selected[0].start,
                    char_end=selected[-1].end,
                    metadata={
                        "offset_contract": "normalized_locator_section_stream_v1",
                        "source_anchors": [anchor for unit in selected for anchor in unit.anchors],
                    },
                )
            )
            if cursor < len(units) and len(selected) > 1:
                overlap = selected[-1]
                if len(overlap.text) <= MIN_CHUNK_CHARS:
                    cursor -= 1
    return projections


def _group_key(block: ParsedBlock) -> tuple[int | None, int | None, tuple[str, ...]]:
    """Prevent a retrieval chunk from crossing a citation locator or section path."""
    return block.page_no, block.slide_no, _section_path(block)


def _section_path(block: ParsedBlock) -> tuple[str, ...]:
    """Normalize parser-specific hierarchy metadata into one tuple contract."""
    raw = block.metadata.get("section_path")
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if str(item).strip())
    return (block.section_title,) if block.section_title else ()


def _group_units(group: list[ParsedBlock]) -> list[_Unit]:
    """Build paragraph or sentence units and offsets in the normalized group stream."""
    units: list[_Unit] = []
    offset = 0
    for block in group:
        anchors = block.metadata.get("source_anchors")
        safe_anchors = anchors if isinstance(anchors, list) else []
        parts = _split_oversized(block.text.strip())
        for part in parts:
            start = offset
            end = start + len(part)
            units.append(_Unit(part, start, end, safe_anchors))
            offset = end + 2
    return units


def _split_oversized(text: str) -> list[str]:
    """Prefer sentence boundaries and hard-split only a pathological single sentence."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    sentences = [item.strip() for item in re.split(r"(?<=[.!?。！？；;])\s*", text) if item.strip()]
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > MAX_CHUNK_CHARS:
            if current:
                parts.append(current)
                current = ""
            parts.extend(
                sentence[index : index + MAX_CHUNK_CHARS]
                for index in range(0, len(sentence), MAX_CHUNK_CHARS)
            )
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > MAX_CHUNK_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts
