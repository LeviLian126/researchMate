"""Load workflow evidence only through owner- and project-scoped SQL queries."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from researchmate_api.services.store import ChunkEntry
from sqlalchemy import text


class WorkflowEvidenceLoaderMixin:
    """Resolve evidence referenced by workflow state without widening its ownership scope."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in SqlEvidenceWorkflowDomain.
        from sqlalchemy import Engine

        engine: Engine

    def _load_chunks(
        self, user_id: UUID, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry]:
        if not chunk_ids:
            return []
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select id,user_id,project_id,document_id,source_type,source_title,text,
                           page_no,slide_no,url,section_title,section_path,chunk_index,
                           char_start,char_end,metadata,created_at
                    from chunks where user_id=:user_id and project_id=:project_id
                      and id = any(:ids)
                    """
                    ),
                    {"user_id": user_id, "project_id": project_id, "ids": chunk_ids},
                )
                .mappings()
                .all()
            )
        by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]
