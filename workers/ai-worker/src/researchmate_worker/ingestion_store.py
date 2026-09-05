"""Persist lease-protected ingestion state transitions and indexed content metadata."""

from __future__ import annotations

import json
import logging
from hashlib import sha256

from researchmate_api.services.store import ChunkEntry
from sqlalchemy import Engine, text

from researchmate_worker.ingestion_models import (
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    PageProjection,
    WikiProjectState,
)

LOGGER = logging.getLogger(__name__)


class SqlIngestionStore:
    """Service-role worker repository with an explicit expiring delivery lease."""

    def __init__(self, engine: Engine) -> None:
        """Bind the SQL engine used for ingestion state transitions."""
        self.engine = engine

    def claim(
        self,
        event: IngestionEvent,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> IngestionRecord | None:
        """Lease an eligible ingestion job and return its work record."""
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    update jobs as j
                    set status = 'running', progress = greatest(j.progress, 5),
                        attempts = j.attempts + 1, lease_owner = :worker_id,
                        lease_expires_at = now() + make_interval(secs => :lease_seconds),
                        started_at = coalesce(j.started_at, now()), updated_at = now(),
                        error_message = null
                    from documents as d
                    join projects as p on p.id = d.project_id
                    where j.id = :job_id and j.type = 'parse_and_index_document'
                      and j.user_id = :user_id
                      and j.project_id = :project_id and j.document_id = :document_id
                      and d.id = j.document_id and d.user_id = j.user_id
                      and d.project_id = j.project_id and d.deleted_at is null
                      and p.user_id = j.user_id and p.status = 'active'
                      and p.deleted_at is null
                      and d.status not in ('deleted', 'expired', 'ready')
                      and (
                        j.status = 'pending'
                        or (j.status = 'running' and j.lease_expires_at < now())
                      )
                    returning j.id as job_id, j.user_id, j.project_id, j.document_id,
                              d.filename, d.file_type, d.r2_object_key,
                              j.payload ->> 'checksum_sha256' as checksum_sha256,
                              j.attempts
                    """
                    ),
                    {
                        "job_id": event.job_id,
                        "user_id": event.user_id,
                        "project_id": event.project_id,
                        "document_id": event.document_id,
                        "worker_id": worker_id,
                        "lease_seconds": lease_seconds,
                    },
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                connection.execute(
                    text(
                        """
                        update documents set status = 'parsing', error_message = null,
                          updated_at = now()
                        where id = :document_id and user_id = :user_id
                        """
                    ),
                    {"document_id": event.document_id, "user_id": event.user_id},
                )
        return None if row is None else IngestionRecord(**dict(row))

    def replace_content(
        self,
        record: IngestionRecord,
        *,
        worker_id: str,
        pages: list[PageProjection],
        chunks: list[ChunkEntry],
        pipeline_version: str,
        wiki_chunks: list[ChunkEntry] | None = None,
        base_knowledge_generation: int = 0,
        recovered_wiki_generation: int | None = None,
    ) -> None:
        """Atomically replace parsed pages and chunks for the leased document."""
        with self.engine.begin() as connection:
            runnable = connection.execute(
                text(
                    """
                    select 1 from jobs j
                    join documents d on d.id = j.document_id and d.user_id = j.user_id
                    join projects p on p.id = j.project_id and p.user_id = j.user_id
                    where j.id = :job_id and j.status = 'running'
                      and j.lease_owner = :worker_id and j.lease_expires_at > now()
                      and d.deleted_at is null
                      and d.status in ('uploaded','parsing','parsed','indexing','failed')
                      and p.status = 'active' and p.deleted_at is null
                    for update of j, d, p
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            ).one_or_none()
            if runnable is None:
                raise IngestionFailure("DOCUMENT_NOT_RUNNABLE", retryable=False)
            generation_row = (
                connection.execute(
                    text(
                        """
                    select knowledge_generation, wiki_generation
                    from projects
                    where id = :project_id and user_id = :user_id
                      and status = 'active' and deleted_at is null
                    for update
                    """
                    ),
                    {"project_id": record.project_id, "user_id": record.user_id},
                )
                .mappings()
                .one_or_none()
            )
            if generation_row is None:
                raise IngestionFailure("DOCUMENT_NOT_RUNNABLE", retryable=False)
            current_generation = int(generation_row["knowledge_generation"])
            current_wiki_generation = int(generation_row["wiki_generation"])
            next_generation = current_generation + 1
            apply_wiki = (
                wiki_chunks is not None
                and current_generation == base_knowledge_generation
                and (
                    current_wiki_generation == current_generation
                    or current_wiki_generation == recovered_wiki_generation
                )
            )
            connection.execute(
                text("delete from document_pages where document_id = :document_id"),
                {"document_id": record.document_id},
            )
            connection.execute(
                text(
                    """
                    delete from chunks
                    where document_id = :document_id
                      and metadata ->> 'wiki_mode' is distinct from 'true'
                    """
                ),
                {"document_id": record.document_id},
            )
            for page in pages:
                connection.execute(
                    text(
                        """
                        insert into document_pages (
                          id, document_id, page_no, slide_no, section_title, text, metadata
                        ) values (
                          :id, :document_id, :page_no, :slide_no, :section_title,
                          :text, cast(:metadata as jsonb)
                        )
                        """
                    ),
                    {
                        "id": page.id,
                        "document_id": record.document_id,
                        "page_no": page.page_no,
                        "slide_no": page.slide_no,
                        "section_title": page.section_title,
                        "text": page.text,
                        "metadata": json.dumps(page.metadata, ensure_ascii=False),
                    },
                )
            persisted_chunks = [*chunks, *(wiki_chunks or [])] if apply_wiki else chunks
            for chunk in persisted_chunks:
                chunk_hash = sha256(chunk.text.encode("utf-8")).hexdigest()
                is_wiki = chunk.metadata.get("wiki_mode") is True
                metadata = {
                    **chunk.metadata,
                    "content_hash": chunk_hash,
                    "pipeline_version": pipeline_version,
                    "knowledge_generation": next_generation,
                }
                if is_wiki:
                    metadata["wiki_generation"] = next_generation
                    merged_page_ids = chunk.metadata.get("wiki_merged_page_ids", [])
                    if isinstance(merged_page_ids, list) and merged_page_ids:
                        connection.execute(
                            text(
                                """
                                delete from chunks
                                where id = any(cast(:merged_page_ids as uuid[]))
                                  and user_id = :user_id and project_id = :project_id
                                  and metadata ->> 'wiki_mode' = 'true'
                                """
                            ),
                            {
                                "merged_page_ids": merged_page_ids,
                                "user_id": record.user_id,
                                "project_id": record.project_id,
                            },
                        )
                connection.execute(
                    text(
                        """
                        insert into chunks (
                          id, user_id, project_id, document_id, source_type, source_title,
                          page_no, slide_no, section_title, section_path, chunk_index,
                          char_start, char_end, text, token_count, qdrant_point_id,
                          has_vector, metadata
                        ) values (
                          :id, :user_id, :project_id, :document_id, 'local_doc', :source_title,
                          :page_no, :slide_no, :section_title, :section_path, :chunk_index,
                          :char_start, :char_end, :text, :token_count, :qdrant_point_id,
                          :has_vector, cast(:metadata as jsonb)
                        )
                        on conflict (id) do update set
                          source_title = excluded.source_title,
                          text = excluded.text,
                          document_id = excluded.document_id,
                          chunk_index = excluded.chunk_index,
                          has_vector = excluded.has_vector,
                          qdrant_point_id = excluded.qdrant_point_id,
                          metadata = excluded.metadata
                        """
                    ),
                    {
                        "id": chunk.id,
                        "user_id": chunk.user_id,
                        "project_id": chunk.project_id,
                        "document_id": None if is_wiki else chunk.document_id,
                        "source_title": chunk.source_title,
                        "page_no": chunk.page_no,
                        "slide_no": chunk.slide_no,
                        "section_title": chunk.section_title,
                        "section_path": list(chunk.section_path),
                        "chunk_index": chunk.chunk_index,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "text": chunk.text,
                        "token_count": len(chunk.text.split()),
                        "qdrant_point_id": str(chunk.id) if chunk.has_vector else None,
                        "has_vector": chunk.has_vector,
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                    },
                )
            if wiki_chunks is not None and not apply_wiki:
                LOGGER.warning(
                    " ".join(
                        (
                            "wiki_generation_not_applied project_id=%s expected_knowledge=%s",
                            "actual_knowledge=%s actual_wiki=%s",
                        )
                    ),
                    record.project_id,
                    base_knowledge_generation,
                    current_generation,
                    current_wiki_generation,
                )
            connection.execute(
                text(
                    """
                    update projects
                    set knowledge_generation = :knowledge_generation,
                        wiki_generation = case
                          when :apply_wiki then :knowledge_generation
                          else wiki_generation
                        end,
                        updated_at = now()
                    where id = :project_id and user_id = :user_id
                    """
                ),
                {
                    "knowledge_generation": next_generation,
                    "apply_wiki": apply_wiki,
                    "project_id": record.project_id,
                    "user_id": record.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    update documents set status = 'indexing', parser = :parser, updated_at = now()
                    where id = :document_id and deleted_at is null
                      and status <> 'deleted'
                    """
                ),
                {"document_id": record.document_id, "parser": pipeline_version},
            )
            connection.execute(
                text("update jobs set progress = 75, updated_at = now() where id = :job_id"),
                {"job_id": record.job_id},
            )

    def load_wiki_state(self, record: IngestionRecord) -> WikiProjectState:
        """Load the owner-scoped canonical Wiki and freshness counters."""
        with self.engine.begin() as connection:
            generation = (
                connection.execute(
                    text(
                        """
                    select knowledge_generation, wiki_generation
                    from projects
                    where id = :project_id and user_id = :user_id
                      and status = 'active' and deleted_at is null
                    for share
                    """
                    ),
                    {"project_id": record.project_id, "user_id": record.user_id},
                )
                .mappings()
                .one_or_none()
            )
            if generation is None:
                raise IngestionFailure("DOCUMENT_NOT_RUNNABLE", retryable=False)
            rows = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, source_type, source_title,
                           text, page_no, slide_no, url, section_title, section_path,
                           chunk_index, char_start, char_end, has_vector, metadata, created_at
                    from chunks
                    where user_id = :user_id and project_id = :project_id
                      and metadata ->> 'wiki_mode' = 'true'
                    order by created_at, id
                    """
                ),
                {"project_id": record.project_id, "user_id": record.user_id},
            ).mappings()
            chunks = [ChunkEntry(**dict(row)) for row in rows]
            pending_rows = connection.execute(
                text(
                    """
                    select c.* from chunks c
                    join documents d on d.id = c.document_id and d.user_id = c.user_id
                    where c.user_id = :user_id and c.project_id = :project_id
                      and c.metadata ->> 'wiki_mode' is distinct from 'true'
                      and d.deleted_at is null and d.status <> 'deleted'
                      and coalesce((c.metadata ->> 'knowledge_generation')::bigint, 0)
                          > :wiki_generation
                    order by coalesce((c.metadata ->> 'knowledge_generation')::bigint, 0),
                             c.document_id, c.chunk_index, c.id
                    """
                ),
                {
                    "user_id": record.user_id,
                    "project_id": record.project_id,
                    "wiki_generation": generation["wiki_generation"],
                },
            ).mappings()
            chunk_fields = ChunkEntry.__dataclass_fields__
            pending_chunks = [
                ChunkEntry(**{key: value for key, value in row.items() if key in chunk_fields})
                for row in pending_rows
            ]
        return WikiProjectState(
            chunks=chunks,
            knowledge_generation=int(generation["knowledge_generation"]),
            wiki_generation=int(generation["wiki_generation"]),
            pending_chunks=pending_chunks,
        )

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None:
        """Commit ready status after projections are persisted and indexed."""
        with self.engine.begin() as connection:
            runnable = connection.execute(
                text(
                    """
                    select 1 from jobs j
                    join documents d on d.id = j.document_id and d.user_id = j.user_id
                    join projects p on p.id = j.project_id and p.user_id = j.user_id
                    where j.id = :job_id and j.status = 'running'
                      and j.lease_owner = :worker_id and j.lease_expires_at > now()
                      and d.deleted_at is null and d.status = 'indexing'
                      and p.status = 'active' and p.deleted_at is null
                    for update of j, d, p
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            ).one_or_none()
            if runnable is None:
                raise IngestionFailure("DOCUMENT_NOT_RUNNABLE", retryable=False)
            connection.execute(
                text(
                    """
                    update jobs set status = 'succeeded', progress = 100, completed_at = now(),
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where id = :job_id and status = 'running' and lease_owner = :worker_id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            )
            connection.execute(
                text(
                    """
                    update documents set status = 'ready', error_message = null, updated_at = now()
                    where id = :document_id and user_id = :user_id
                      and deleted_at is null and status = 'indexing'
                    """
                ),
                {"document_id": record.document_id, "user_id": record.user_id},
            )

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        """Release a leased ingestion for another bounded retry attempt."""
        with self.engine.begin() as connection:
            updated = connection.execute(
                text(
                    """
                    update jobs j set status = 'pending', error_message = :code,
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where j.id = :job_id and j.lease_owner = :worker_id
                      and exists (
                        select 1 from documents d
                        join projects p on p.id = d.project_id and p.user_id = d.user_id
                        where d.id = j.document_id and d.user_id = j.user_id
                          and d.deleted_at is null and d.status <> 'deleted'
                          and p.status = 'active' and p.deleted_at is null
                      )
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id, "code": code[:80]},
            )
            if not updated.rowcount:
                connection.execute(
                    text(
                        """
                        update jobs set status = 'failed', error_message = 'DOCUMENT_NOT_RUNNABLE',
                          lease_owner = null, lease_expires_at = null, completed_at = now(),
                          updated_at = now()
                        where id = :job_id and lease_owner = :worker_id
                        """
                    ),
                    {"job_id": record.job_id, "worker_id": worker_id},
                )

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        """Persist terminal ingestion failure and its safe diagnostic code."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update jobs set status = 'failed', error_message = :code,
                      lease_owner = null, lease_expires_at = null, completed_at = now(),
                      updated_at = now()
                    where id = :job_id and lease_owner = :worker_id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id, "code": code[:80]},
            )
            connection.execute(
                text(
                    """
                    update documents set status = 'failed', error_message = :code, updated_at = now()
                    where id = :document_id and user_id = :user_id
                      and deleted_at is null and status <> 'deleted'
                    """
                ),
                {"document_id": record.document_id, "user_id": record.user_id, "code": code[:80]},
            )
