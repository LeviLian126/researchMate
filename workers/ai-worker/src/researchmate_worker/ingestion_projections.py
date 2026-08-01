"""Build bounded chunk and page projections from parser output for indexing."""

from __future__ import annotations

from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.store import ChunkEntry

from researchmate_worker.ingestion_models import IngestionRecord, PageProjection, ParsedBlock
from researchmate_worker.jobs import chunk_text_for_index


def build_projections(
    record: IngestionRecord,
    blocks: list[ParsedBlock],
    *,
    pipeline_version: str,
) -> tuple[list[PageProjection], list[ChunkEntry]]:
    """Project parsed blocks into deterministic page and retrieval chunk records."""
    pages: list[PageProjection] = []
    chunks: list[ChunkEntry] = []
    for block_index, block in enumerate(blocks):
        normalized = block.text.strip()
        if not normalized:
            continue
        content_hash = sha256(normalized.encode("utf-8")).hexdigest()
        page_id = uuid5(
            NAMESPACE_URL,
            f"researchmate:{record.document_id}:{pipeline_version}:block:{block_index}:{content_hash}",
        )
        metadata = {
            **block.metadata,
            "content_hash": content_hash,
            "pipeline_version": pipeline_version,
            "block_index": block_index,
        }
        pages.append(
            PageProjection(
                id=page_id,
                page_no=block.page_no,
                slide_no=block.slide_no,
                section_title=block.section_title,
                text=normalized,
                metadata=metadata,
            )
        )
        for chunk_index, chunk_text in enumerate(chunk_text_for_index(normalized)):
            chunk_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
            chunk_id = uuid5(
                NAMESPACE_URL,
                f"researchmate:{record.document_id}:{pipeline_version}:chunk:"
                f"{block_index}:{chunk_index}:{chunk_hash}",
            )
            chunks.append(
                ChunkEntry(
                    id=chunk_id,
                    user_id=record.user_id,
                    project_id=record.project_id,
                    document_id=record.document_id,
                    source_type=SourceType.LOCAL_DOC,
                    source_title=record.filename,
                    text=chunk_text,
                    page_no=block.page_no,
                    slide_no=block.slide_no,
                )
            )
    return pages, chunks
