from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from sqlalchemy import Engine, text

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_api.services.qdrant_store import VectorStoreRequestError
from researchmate_api.services.store import ChunkEntry
from researchmate_worker.jobs import chunk_text_for_index


class IngestionEvent(BaseModel):
    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID


@dataclass(frozen=True)
class IngestionRecord:
    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID
    filename: str
    file_type: str
    r2_object_key: str
    checksum_sha256: str | None
    attempts: int


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    page_no: int | None = None
    slide_no: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PageProjection:
    id: UUID
    page_no: int | None
    slide_no: int | None
    section_title: str | None
    text: str
    metadata: dict[str, Any]


class ParserAdapterError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class IngestionFailure(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class DocumentParser(Protocol):
    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]: ...


class ObjectReader(Protocol):
    def download_to_file(self, object_key: str, destination: Path) -> None: ...


class VectorProjection(Protocol):
    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None: ...


class IngestionStore(Protocol):
    def claim(self, event: IngestionEvent, *, worker_id: str, lease_seconds: int) -> IngestionRecord | None: ...

    def replace_content(
        self,
        record: IngestionRecord,
        *,
        worker_id: str,
        pages: list[PageProjection],
        chunks: list[ChunkEntry],
        pipeline_version: str,
    ) -> None: ...

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None: ...

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None: ...

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None: ...


def build_projections(
    record: IngestionRecord,
    blocks: list[ParsedBlock],
    *,
    pipeline_version: str,
) -> tuple[list[PageProjection], list[ChunkEntry]]:
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


class SqlIngestionStore:
    """Service-role worker repository with an explicit expiring delivery lease."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def claim(
        self,
        event: IngestionEvent,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> IngestionRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    update jobs as j
                    set status = 'running', progress = greatest(j.progress, 5),
                        attempts = j.attempts + 1, lease_owner = :worker_id,
                        lease_expires_at = now() + make_interval(secs => :lease_seconds),
                        started_at = coalesce(j.started_at, now()), updated_at = now(),
                        error_message = null
                    from documents as d
                    where j.id = :job_id and j.user_id = :user_id
                      and j.project_id = :project_id and j.document_id = :document_id
                      and d.id = j.document_id and d.user_id = j.user_id
                      and d.project_id = j.project_id and d.deleted_at is null
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
            ).mappings().one_or_none()
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
        with self.engine.begin() as connection:
            lease = connection.execute(
                text(
                    """
                    select 1 from jobs
                    where id = :job_id and status = 'running' and lease_owner = :worker_id
                      and lease_expires_at > now()
                    for update
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            ).one_or_none()
            if lease is None:
                raise IngestionFailure("JOB_LEASE_LOST", retryable=True)
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
                          page_no, slide_no, text, token_count, qdrant_point_id, metadata
                        ) values (
                          :id, :user_id, :project_id, :document_id, 'local_doc', :source_title,
                          :page_no, :slide_no, :text, :token_count, :qdrant_point_id,
                          cast(:metadata as jsonb)
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
                        "text": chunk.text,
                        "token_count": len(chunk.text.split()),
                        "qdrant_point_id": str(chunk.id),
                        "metadata": json.dumps(
                            {"content_hash": chunk_hash, "pipeline_version": pipeline_version}
                        ),
                    },
                )
            connection.execute(
                text(
                    """
                    update documents set status = 'indexing', parser = :parser, updated_at = now()
                    where id = :document_id
                    """
                ),
                {"document_id": record.document_id, "parser": pipeline_version},
            )
            connection.execute(
                text("update jobs set progress = 75, updated_at = now() where id = :job_id"),
                {"job_id": record.job_id},
            )

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None:
        with self.engine.begin() as connection:
            updated = connection.execute(
                text(
                    """
                    update jobs set status = 'succeeded', progress = 100, completed_at = now(),
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where id = :job_id and status = 'running' and lease_owner = :worker_id
                    returning id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            ).one_or_none()
            if updated is None:
                raise IngestionFailure("JOB_LEASE_LOST", retryable=True)
            connection.execute(
                text(
                    """
                    update documents set status = 'ready', error_message = null, updated_at = now()
                    where id = :document_id and user_id = :user_id
                    """
                ),
                {"document_id": record.document_id, "user_id": record.user_id},
            )

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update jobs set status = 'pending', error_message = :code,
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where id = :job_id and lease_owner = :worker_id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id, "code": code[:80]},
            )

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
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
                    """
                ),
                {"document_id": record.document_id, "user_id": record.user_id, "code": code[:80]},
            )


class DocumentIngestionService:
    def __init__(
        self,
        *,
        store: IngestionStore,
        object_reader: ObjectReader,
        parser: DocumentParser,
        vector_projection: VectorProjection,
        pipeline_version: str,
        lease_seconds: int,
        max_attempts: int,
        max_upload_bytes: int,
    ) -> None:
        self.store = store
        self.object_reader = object_reader
        self.parser = parser
        self.vector_projection = vector_projection
        self.pipeline_version = pipeline_version
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.max_upload_bytes = max_upload_bytes

    def handle(self, event: IngestionEvent, *, worker_id: str) -> str:
        record = self.store.claim(event, worker_id=worker_id, lease_seconds=self.lease_seconds)
        if record is None:
            return "not_claimed"
        try:
            with TemporaryDirectory(prefix="researchmate-ingest-") as directory:
                source = Path(directory) / f"source.{record.file_type}"
                self.object_reader.download_to_file(record.r2_object_key, source)
                if source.stat().st_size > self.max_upload_bytes:
                    raise IngestionFailure("DOCUMENT_TOO_LARGE", retryable=False)
                actual_checksum = sha256(source.read_bytes()).hexdigest()
                if record.checksum_sha256 and actual_checksum != record.checksum_sha256:
                    raise IngestionFailure("CHECKSUM_MISMATCH", retryable=False)
                blocks = self.parser.parse(source, file_type=record.file_type)
            pages, chunks = build_projections(
                record,
                blocks,
                pipeline_version=self.pipeline_version,
            )
            if not pages or not chunks:
                raise IngestionFailure("NO_EXTRACTABLE_TEXT", retryable=False)
            self.store.replace_content(
                record,
                worker_id=worker_id,
                pages=pages,
                chunks=chunks,
                pipeline_version=self.pipeline_version,
            )
            self.vector_projection.upsert_chunks(chunks, pipeline_version=self.pipeline_version)
            self.store.mark_ready(record, worker_id=worker_id)
            return "succeeded"
        except ObjectStorageRequestError as exc:
            self._record_failure(record, worker_id, "OBJECT_STORAGE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("OBJECT_STORAGE_UNAVAILABLE", retryable=exc.retryable) from exc
        except VectorStoreRequestError as exc:
            self._record_failure(record, worker_id, "VECTOR_STORE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("VECTOR_STORE_UNAVAILABLE", retryable=exc.retryable) from exc
        except ParserAdapterError as exc:
            self._record_failure(record, worker_id, exc.code, exc.retryable)
            raise IngestionFailure(exc.code, retryable=exc.retryable) from exc
        except IngestionFailure as exc:
            self._record_failure(record, worker_id, exc.code, exc.retryable)
            raise
        except Exception as exc:
            self._record_failure(record, worker_id, "INGESTION_INTERNAL_ERROR", False)
            raise IngestionFailure("INGESTION_INTERNAL_ERROR", retryable=False) from exc

    def _record_failure(
        self,
        record: IngestionRecord,
        worker_id: str,
        code: str,
        retryable: bool,
    ) -> None:
        if retryable and record.attempts < self.max_attempts:
            self.store.mark_retryable(record, worker_id=worker_id, code=code)
        else:
            self.store.mark_failed(record, worker_id=worker_id, code=code)
