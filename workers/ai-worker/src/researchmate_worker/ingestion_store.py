"""Persist lease-protected ingestion state transitions and indexed content metadata."""

from __future__ import annotations

import json
from hashlib import sha256

from researchmate_api.services.store import ChunkEntry
from sqlalchemy import Engine, text

from researchmate_worker.ingestion_models import (
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    PageProjection,
)


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
            connection.execute(
                text("delete from document_pages where document_id = :document_id"),
                {"document_id": record.document_id},
            )
            connection.execute(
                text("delete from chunks where document_id = :document_id"),
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
            for chunk in chunks:
                chunk_hash = sha256(chunk.text.encode("utf-8")).hexdigest()
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
                        """
                    ),
                    {
                        "id": chunk.id,
                        "user_id": chunk.user_id,
                        "project_id": chunk.project_id,
                        "document_id": chunk.document_id,
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
                        "metadata": json.dumps(
                            {
                                **chunk.metadata,
                                "content_hash": chunk_hash,
                                "pipeline_version": pipeline_version,
                            },
                            ensure_ascii=False,
                        ),
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
