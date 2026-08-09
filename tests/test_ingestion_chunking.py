"""Verify structure-aware chunk boundaries, overlap, and provenance offsets."""

from __future__ import annotations

from researchmate_worker.ingestion_chunking import build_structure_chunks
from researchmate_worker.ingestion_models import ParsedBlock


def _block(
    text: str,
    *,
    page: int = 1,
    section: str = "Retrieval",
    path: list[str] | None = None,
) -> ParsedBlock:
    return ParsedBlock(
        text=text,
        page_no=page,
        section_title=section,
        metadata={
            "section_path": path or [section],
            "source_anchors": [{"item_ref": text[:8]}],
        },
    )


def test_chunks_never_cross_locator_or_section_boundaries() -> None:
    """Keep every citation locator and heading path unambiguous."""
    chunks = build_structure_chunks(
        [
            _block("Dense evidence.", page=1, section="Dense"),
            _block("BM25 evidence.", page=1, section="Lexical"),
            _block("Second page.", page=2, section="Lexical"),
        ]
    )
    assert [(item.page_no, item.section_title) for item in chunks] == [
        (1, "Dense"),
        (1, "Lexical"),
        (2, "Lexical"),
    ]


def test_overlap_reuses_a_whole_semantic_unit_with_stable_offsets() -> None:
    """Overlap paragraphs without cutting characters or inventing source positions."""
    first = "A" * 400
    bridge = "B" * 120
    last = "C" * 400
    chunks = build_structure_chunks([_block(first), _block(bridge), _block(last)])
    assert len(chunks) == 2
    assert chunks[0].text == f"{first}\n\n{bridge}"
    assert chunks[1].text == f"{bridge}\n\n{last}"
    assert chunks[1].char_start == len(first) + 2
    assert chunks[1].char_end == len(first) + len(bridge) + len(last) + 4
    assert chunks[0].metadata["offset_contract"] == "normalized_locator_section_stream_v1"
