from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from researchmate_api.schemas.common import (
    Citation,
    CurrentUser,
    ExecutionPlan,
    JobStatus,
    SourceSummary,
    SourceType,
)
from researchmate_api.schemas.conversation import (
    ConversationMessage,
    ConversationSummary,
    RuntimeRerankConfig,
)
from researchmate_api.schemas.document import DocumentRecord, UploadUrlRequest, UploadUrlResponse
from researchmate_api.schemas.job import JobRecord
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.schemas.quiz import QuizQuestion, QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.schemas.trace import DeveloperTrace, ToolCallTrace
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    StoredObjectMetadata,
    UploadVerificationError,
)
from researchmate_api.services.store import ChunkEntry

UploadUrlFactory = Callable[[UUID, str, UploadUrlRequest], str]
ObjectMetadataReader = Callable[[str], StoredObjectMetadata]


def _enum_value(value: str | Enum) -> str:
    return str(value.value if isinstance(value, Enum) else value)


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def _safe_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized[:180] or "document"


def _psycopg_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class PostgresResearchMateRepository:
    """SQLAlchemy Core adapter for the current API contract and Supabase schema.

    Every resource query contains an explicit user predicate. The transaction also sets the
    Supabase JWT subject setting so RLS remains useful when the connection role does not bypass it.
    Object upload signing is intentionally injected; the default URL is an explicit reservation
    marker and must be replaced by the R2 adapter before a production upload can succeed.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        default_project_ttl_days: int = 7,
        upload_url_factory: UploadUrlFactory | None = None,
        object_metadata_reader: ObjectMetadataReader | None = None,
    ) -> None:
        self.engine = engine
        self.default_project_ttl_days = default_project_ttl_days
        self.upload_url_factory = upload_url_factory or (
            lambda document_id, _key, _payload: f"r2-reservation://{document_id}"
        )
        self.object_metadata_reader = object_metadata_reader

    @classmethod
    def from_database_url(
        cls,
        database_url: str,
        *,
        default_project_ttl_days: int = 7,
        upload_url_factory: UploadUrlFactory | None = None,
        object_metadata_reader: ObjectMetadataReader | None = None,
    ) -> PostgresResearchMateRepository:
        engine = create_engine(
            _psycopg_url(database_url),
            pool_pre_ping=True,
            pool_recycle=300,
            future=True,
        )
        return cls(
            engine,
            default_project_ttl_days=default_project_ttl_days,
            upload_url_factory=upload_url_factory,
            object_metadata_reader=object_metadata_reader,
        )

    @contextmanager
    def _transaction(self, user: CurrentUser | None = None) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            if user is not None:
                connection.execute(
                    text("select set_config('request.jwt.claim.sub', :user_id, true)"),
                    {"user_id": str(user.id)},
                )
            yield connection

    def ensure_user(self, user: CurrentUser) -> CurrentUser:
        with self._transaction(user) as connection:
            connection.execute(
                text(
                    """
                    insert into profiles (id, email, provider, role)
                    values (:id, :email, 'supabase', :role)
                    on conflict (id) do update
                    set email = excluded.email, role = excluded.role, updated_at = now()
                    where profiles.id = :id
                    """
                ),
                {"id": user.id, "email": user.email, "role": user.role},
            )
        return user

    def create_project(self, user: CurrentUser, payload: ProjectCreate) -> ProjectRecord:
        self.ensure_user(user)
        project_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(days=self.default_project_ttl_days)
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    insert into projects (id, user_id, name, expires_at)
                    select :id, :user_id, :name, :expires_at
                    where exists (select 1 from profiles where id = :user_id)
                    returning id, user_id, name, status, expires_at, created_at, updated_at, deleted_at
                    """
                ),
                {
                    "id": project_id,
                    "user_id": user.id,
                    "name": payload.name,
                    "expires_at": expires_at,
                },
            ).mappings().one()
        return ProjectRecord.model_validate(dict(row))

    def list_projects(self, user: CurrentUser) -> list[ProjectRecord]:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, name, status, expires_at, created_at, updated_at, deleted_at
                    from projects
                    where user_id = :user_id and status in ('active', 'deleting')
                      and deleted_at is null
                    order by updated_at desc, id
                    """
                ),
                {"user_id": user.id},
            ).mappings()
            return [ProjectRecord.model_validate(dict(row)) for row in rows]

    def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, name, status, expires_at, created_at, updated_at, deleted_at
                    from projects
                    where id = :project_id and user_id = :user_id and deleted_at is null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().one_or_none()
        return None if row is None else ProjectRecord.model_validate(dict(row))

    def delete_project(self, user: CurrentUser, project_id: UUID) -> JobRecord | None:
        with self._transaction(user) as connection:
            project = connection.execute(
                text(
                    """
                    select status from projects
                    where id = :project_id and user_id = :user_id
                      and status in ('active', 'deleting') and deleted_at is null
                    for update
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().one_or_none()
            if project is None:
                return None
            if project["status"] == "deleting":
                existing = connection.execute(
                    text(
                        """
                        select id, user_id, project_id, document_id, type, status, progress,
                               error_message, created_at, updated_at
                        from jobs
                        where project_id = :project_id and user_id = :user_id
                          and type = 'delete_project'
                        order by created_at desc, id desc limit 1
                        """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                ).mappings().one_or_none()
                if existing is not None and existing["status"] in {"pending", "running"}:
                    if existing["status"] == "pending":
                        self._enqueue_project_deletion(
                            connection,
                            user_id=user.id,
                            project_id=project_id,
                            job_id=existing["id"],
                            delivery_id=uuid4(),
                        )
                    return JobRecord.model_validate(dict(existing))
                if existing is None or existing["status"] != "failed":
                    return None
            else:
                connection.execute(
                    text(
                        """
                        update projects set status = 'deleting', updated_at = now()
                        where id = :project_id and user_id = :user_id and status = 'active'
                        """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
            connection.execute(
                text(
                    """
                    update jobs
                    set status = 'failed', error_message = 'PROJECT_DELETING',
                      completed_at = now(), updated_at = now()
                    where project_id = :project_id and user_id = :user_id
                      and type = 'parse_and_index_document' and status = 'pending'
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            )
            object_keys = connection.execute(
                text(
                    """
                    select r2_object_key from documents
                    where project_id = :project_id and user_id = :user_id
                      and r2_object_key is not null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).scalars().all()
            point_ids = connection.execute(
                text(
                    """
                    select qdrant_point_id from chunks
                    where project_id = :project_id and user_id = :user_id
                      and qdrant_point_id is not null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).scalars().all()
            job = self._insert_job(
                connection,
                user=user,
                project_id=project_id,
                document_id=None,
                job_type="delete_project",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_keys": list(object_keys),
                    "qdrant_point_ids": list(point_ids),
                },
            )
            connection.execute(
                text(
                    """
                    insert into deletion_jobs (id, user_id, project_id, status)
                    values (:id, :user_id, :project_id, 'pending')
                    """
                ),
                {"id": job.id, "user_id": user.id, "project_id": project_id},
            )
            self._enqueue_project_deletion(
                connection,
                user_id=user.id,
                project_id=project_id,
                job_id=job.id,
                delivery_id=job.id,
            )
            return job

    def create_upload_url(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> UploadUrlResponse | None:
        document_id = uuid4()
        filename = _safe_filename(payload.filename)
        object_key = (
            f"users/{user.id}/projects/{payload.project_id}/documents/{document_id}/{filename}"
        )
        upload_url = self.upload_url_factory(document_id, object_key, payload)
        expires_at = datetime.now(UTC) + timedelta(days=self.default_project_ttl_days)
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, payload.project_id):
                return None
            row = connection.execute(
                text(
                    """
                    insert into documents (
                      id, user_id, project_id, filename, file_type, mime_type, size_bytes,
                      r2_object_key, status, expires_at
                    )
                    select :id, :user_id, p.id, :filename, :file_type, :mime_type, :size_bytes,
                           :object_key, 'uploaded', :expires_at
                    from projects p
                    where p.id = :project_id and p.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    returning id
                    """
                ),
                {
                    "id": document_id,
                    "user_id": user.id,
                    "project_id": payload.project_id,
                    "filename": payload.filename,
                    "file_type": payload.file_type,
                    "mime_type": payload.mime_type,
                    "size_bytes": payload.size_bytes,
                    "object_key": object_key,
                    "expires_at": expires_at,
                },
            ).one_or_none()
            if row is None:
                return None
        return UploadUrlResponse(
            document_id=document_id,
            upload_url=upload_url,
            r2_object_key=object_key,
            expires_in_seconds=600,
        )

    def create_document(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> DocumentRecord | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, project_id, filename, file_type, mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents d
                    where d.user_id = :user_id and d.project_id = :project_id
                      and d.filename = :filename and d.size_bytes = :size_bytes
                      and d.deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id = d.project_id and p.user_id = d.user_id
                          and p.status = 'active' and p.deleted_at is null
                      )
                    order by created_at desc
                    limit 1
                    """
                ),
                {
                    "user_id": user.id,
                    "project_id": payload.project_id,
                    "filename": payload.filename,
                    "size_bytes": payload.size_bytes,
                },
            ).mappings().one_or_none()
        if row is not None:
            return DocumentRecord.model_validate(dict(row))
        reservation = self.create_upload_url(user, payload)
        return None if reservation is None else self.get_document(user, reservation.document_id)

    def list_project_documents(
        self, user: CurrentUser, project_id: UUID
    ) -> list[DocumentRecord] | None:
        if self.get_project(user, project_id) is None:
            return None
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, project_id, filename, file_type, mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents
                    where user_id = :user_id and project_id = :project_id and deleted_at is null
                    order by created_at desc, id
                    """
                ),
                {"user_id": user.id, "project_id": project_id},
            ).mappings()
            return [DocumentRecord.model_validate(dict(row)) for row in rows]

    def get_document(self, user: CurrentUser, document_id: UUID) -> DocumentRecord | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, project_id, filename, file_type, mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents
                    where id = :document_id and user_id = :user_id and deleted_at is null
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
        return None if row is None else DocumentRecord.model_validate(dict(row))

    def complete_document(
        self,
        user: CurrentUser,
        document_id: UUID,
        extracted_text: str | None,
        checksum_sha256: str | None = None,
    ) -> JobRecord | None:
        if self.object_metadata_reader is None:
            raise ObjectStorageConfigurationError("R2 metadata verification is not configured")
        with self._transaction(user) as connection:
            reserved = connection.execute(
                text(
                    """
                    select d.r2_object_key, d.size_bytes, d.mime_type
                    from documents d
                    join projects p on p.id = d.project_id and p.user_id = d.user_id
                    where d.id = :document_id and d.user_id = :user_id
                      and d.deleted_at is null and p.status = 'active'
                      and p.deleted_at is null
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
        if reserved is None:
            return None
        metadata = self.object_metadata_reader(reserved["r2_object_key"])
        if metadata.size_bytes != reserved["size_bytes"]:
            raise UploadVerificationError(
                "UPLOAD_SIZE_MISMATCH",
                "Uploaded object size does not match the reservation.",
            )
        if metadata.content_type and metadata.content_type != reserved["mime_type"]:
            raise UploadVerificationError(
                "UPLOAD_TYPE_MISMATCH",
                "Uploaded object content type does not match the reservation.",
            )
        with self._transaction(user) as connection:
            owner = connection.execute(
                text(
                    """
                    select project_id from documents
                    where id = :document_id and user_id = :user_id and deleted_at is null
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if owner is None or not self._lock_active_project(
                connection, user.id, owner["project_id"]
            ):
                return None
            document = connection.execute(
                text(
                    """
                    update documents d
                    set status = 'parsing', error_message = null, updated_at = now()
                    from projects p
                    where d.id = :document_id and d.user_id = :user_id
                      and d.project_id = p.id and p.user_id = d.user_id
                      and d.deleted_at is null and p.status = 'active'
                      and p.deleted_at is null and d.status in ('uploaded', 'failed')
                    returning d.project_id, d.r2_object_key
                    """
                ),
                {
                    "document_id": document_id,
                    "user_id": user.id,
                },
            ).mappings().one_or_none()
            if document is None:
                existing = connection.execute(
                    text(
                        """
                        select id, user_id, project_id, document_id, type, status, progress,
                               error_message, created_at, updated_at
                        from jobs
                        where document_id = :document_id and user_id = :user_id
                          and type = 'parse_and_index_document'
                          and exists (
                            select 1 from projects p
                            where p.id = jobs.project_id and p.user_id = jobs.user_id
                              and p.status = 'active' and p.deleted_at is null
                          )
                        order by created_at desc limit 1
                        """
                    ),
                    {"document_id": document_id, "user_id": user.id},
                ).mappings().one_or_none()
                if existing is not None and existing["status"] == "pending":
                    self._enqueue_document_event(
                        connection,
                        event_type="document.ingest.requested",
                        document_id=document_id,
                        user_id=user.id,
                        project_id=existing["project_id"],
                        job_id=existing["id"],
                        delivery_id=uuid4(),
                    )
                return None if existing is None else JobRecord.model_validate(dict(existing))
            job = self._insert_job(
                connection,
                user=user,
                project_id=document["project_id"],
                document_id=document_id,
                job_type="parse_and_index_document",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_key": document["r2_object_key"],
                    "checksum_sha256": checksum_sha256.lower() if checksum_sha256 else None,
                },
            )
            self._enqueue_document_event(
                connection,
                event_type="document.ingest.requested",
                document_id=document_id,
                user_id=user.id,
                project_id=document["project_id"],
                job_id=job.id,
                delivery_id=job.id,
            )
            return job

    def delete_document(self, user: CurrentUser, document_id: UUID) -> JobRecord | None:
        with self._transaction(user) as connection:
            document = connection.execute(
                text(
                    """
                    select d.project_id, d.r2_object_key, d.deleted_at
                    from documents d
                    join projects p on p.id = d.project_id and p.user_id = d.user_id
                    where d.id = :document_id and d.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    for update of d, p
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if document is None:
                return None
            connection.execute(
                text(
                    """
                    update jobs
                    set status = 'failed', error_message = 'DOCUMENT_DELETING',
                      completed_at = now(), updated_at = now()
                    where document_id = :document_id and user_id = :user_id
                      and type = 'parse_and_index_document' and status = 'pending'
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            )
            existing = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, type, status, progress,
                           error_message, created_at, updated_at
                    from jobs
                    where document_id = :document_id and user_id = :user_id
                      and type = 'delete_document'
                    order by created_at desc, id desc limit 1
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if document["deleted_at"] is not None and existing is not None:
                if existing["status"] == "pending":
                    self._enqueue_document_event(
                        connection,
                        event_type="document.delete.requested",
                        document_id=document_id,
                        user_id=user.id,
                        project_id=document["project_id"],
                        job_id=existing["id"],
                        delivery_id=uuid4(),
                    )
                    return JobRecord.model_validate(dict(existing))
                if existing["status"] in {"running", "succeeded"}:
                    return JobRecord.model_validate(dict(existing))
                if existing["status"] not in {"failed", "cancelled"}:
                    return None
            elif document["deleted_at"] is None:
                connection.execute(
                    text(
                        """
                        update documents
                        set status = 'deleted', deleted_at = now(), updated_at = now()
                        where id = :document_id and user_id = :user_id
                        """
                    ),
                    {"document_id": document_id, "user_id": user.id},
                )
            point_ids = connection.execute(
                text(
                    """
                    select qdrant_point_id from chunks
                    where document_id = :document_id and user_id = :user_id
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).scalars().all()
            job = self._insert_job(
                connection,
                user=user,
                project_id=document["project_id"],
                document_id=document_id,
                job_type="delete_document",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_key": document["r2_object_key"],
                    "qdrant_point_ids": list(point_ids),
                },
            )
            connection.execute(
                text(
                    """
                    insert into deletion_jobs (id, user_id, project_id, document_id, status)
                    values (:id, :user_id, :project_id, :document_id, 'pending')
                    """
                ),
                {
                    "id": job.id,
                    "user_id": user.id,
                    "project_id": document["project_id"],
                    "document_id": document_id,
                },
            )
            self._enqueue_document_event(
                connection,
                event_type="document.delete.requested",
                document_id=document_id,
                user_id=user.id,
                project_id=document["project_id"],
                job_id=job.id,
                delivery_id=job.id,
            )
            return job

    def get_job(self, user: CurrentUser, job_id: UUID) -> JobRecord | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, type, status, progress,
                           error_message, created_at, updated_at
                    from jobs where id = :job_id and user_id = :user_id
                    """
                ),
                {"job_id": job_id, "user_id": user.id},
            ).mappings().one_or_none()
        return None if row is None else JobRecord.model_validate(dict(row))

    def get_run_sources(
        self, user: CurrentUser, run_id: UUID
    ) -> RunSourcesResponse | None:
        with self._transaction(user) as connection:
            run = connection.execute(
                text("select id from ask_runs where id = :run_id and user_id = :user_id"),
                {"run_id": run_id, "user_id": user.id},
            ).one_or_none()
            if run is None:
                return None
            citations = self._load_citations(connection, user.id, run_id)
        return RunSourcesResponse(
            run_id=run_id,
            summary=SourceSummary(
                local_chunks=sum(c.source_type == SourceType.LOCAL_DOC for c in citations),
                web_pages=sum(c.source_type == SourceType.WEB_PAGE for c in citations),
            ),
            citations=citations,
        )

    def get_trace(self, user: CurrentUser, trace_id: UUID) -> DeveloperTrace | None:
        privileged = user.role in {"developer", "admin"}
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select token_usage -> 'researchmate_trace' as trace
                    from ask_runs
                    where token_usage -> 'researchmate_trace' ->> 'trace_id' = :trace_id
                      and (user_id = :user_id or :privileged)
                    """
                ),
                {
                    "trace_id": str(trace_id),
                    "user_id": user.id,
                    "privileged": privileged,
                },
            ).mappings().one_or_none()
        if row is None or not isinstance(row["trace"], dict):
            return None
        return DeveloperTrace.model_validate(row["trace"])

    def record_run(
        self,
        user: CurrentUser,
        project_id: UUID,
        message: str,
        plan: ExecutionPlan,
        router_reason: str,
        retrieved_chunks: list[ChunkEntry],
        citations: list[Citation],
        tool_calls: list[ToolCallTrace],
        validation_result: dict,
        conversation_id: UUID | None = None,
        runtime_metadata: dict | None = None,
        assistant_answer: str | None = None,
    ) -> tuple[UUID, UUID]:
        run_id, trace_id = uuid4(), uuid4()
        passed = bool(validation_result.get("passed", False))
        trace = DeveloperTrace(
            trace_id=trace_id,
            user_id=user.id,
            project_id=project_id,
            run_id=run_id,
            execution_plan=plan,
            router_reason=router_reason,
            retrieved_chunks=[
                {
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id) if chunk.document_id else None,
                    "source_title": chunk.source_title,
                    "page_no": chunk.page_no,
                    "score_context": chunk.text[:240],
                }
                for chunk in retrieved_chunks
            ],
            tool_calls=tool_calls,
            validation_result=validation_result,
            latency_ms=0,
            token_usage=runtime_metadata,
            errors=[] if passed else ["validation_failed"],
            created_at=datetime.now(UTC),
        )
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, project_id):
                raise ValueError("project is not owned by the current user")
            inserted = connection.execute(
                text(
                    """
                    insert into ask_runs (
                      id, user_id, project_id, conversation_id, message, task_type,
                      web_enabled, context_strategy, rerank_provider, rerank_config_version,
                      rerank_degraded, fallback_reason, status, validation_status,
                      latency_ms, token_usage
                    )
                    select :id, :user_id, p.id, :conversation_id, :message, :task_type,
                           :web_enabled, :context_strategy, :rerank_provider,
                           :rerank_config_version, :rerank_degraded, :fallback_reason,
                           'succeeded', :validation_status, 0, cast(:token_usage as jsonb)
                    from projects p
                    where p.id = :project_id and p.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    returning id
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "message": message,
                    "task_type": _enum_value(plan.task_type),
                    "web_enabled": bool((runtime_metadata or {}).get("web_enabled", False)),
                    "context_strategy": plan.context_strategy,
                    "rerank_provider": (runtime_metadata or {}).get("rerank_provider"),
                    "rerank_config_version": (runtime_metadata or {}).get(
                        "rerank_config_version"
                    ),
                    "rerank_degraded": bool(
                        (runtime_metadata or {}).get("rerank_degraded", False)
                    ),
                    "fallback_reason": (runtime_metadata or {}).get("fallback_reason"),
                    "validation_status": "passed" if passed else "failed",
                    "token_usage": _json(
                        {
                            **(runtime_metadata or {}),
                            "researchmate_trace": trace.model_dump(mode="json"),
                        }
                    ),
                },
            ).one_or_none()
            if inserted is None:
                raise ValueError("project is not owned by the current user")
            for call in tool_calls:
                connection.execute(
                    text(
                        """
                        insert into tool_calls (
                          id, ask_run_id, tool_name, input, output_summary, status,
                          latency_ms, error_message
                        ) values (
                          :id, :run_id, :tool_name, cast(:input as jsonb),
                          cast(:output as jsonb), :status, :latency_ms, :error_message
                        )
                        """
                    ),
                    {
                        "id": call.id,
                        "run_id": run_id,
                        "tool_name": call.tool_name,
                        "input": _json(call.input_summary),
                        "output": _json(call.output_summary) if call.output_summary is not None else "null",
                        "status": call.status,
                        "latency_ms": call.latency_ms,
                        "error_message": call.error_message,
                    },
                )
            for citation in citations:
                connection.execute(
                    text(
                        """
                        insert into citations (
                          id, ask_run_id, chunk_id, document_id, source_type, page_no,
                          slide_no, url, quote, claim_id
                        ) values (
                          :id, :run_id, :chunk_id, :document_id, :source_type, :page_no,
                          :slide_no, :url, :quote, :claim_id
                        )
                        """
                    ),
                    {
                        "id": citation.id,
                        "run_id": run_id,
                        "chunk_id": citation.chunk_id,
                        "document_id": citation.document_id,
                        "source_type": _enum_value(citation.source_type),
                        "page_no": citation.page_no,
                        "slide_no": citation.slide_no,
                        "url": citation.url,
                        "quote": citation.quote,
                        "claim_id": citation.claim_id,
                    },
                )
            if conversation_id is not None and assistant_answer is not None:
                conversation = connection.execute(
                    text(
                        """
                        select c.project_id
                        from conversations c
                        join projects p on p.id=c.project_id
                        where c.id=:id and c.project_id=:project_id and c.user_id=:user_id
                          and c.deleted_at is null
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                        for update of c,p
                        """
                    ),
                    {
                        "id": conversation_id,
                        "project_id": project_id,
                        "user_id": user.id,
                    },
                ).mappings().one_or_none()
                if conversation is None:
                    raise ValueError("conversation is not owned by the current user")
                user_message_id = uuid4()
                connection.execute(
                    text(
                        """
                        insert into messages (
                          id,user_id,project_id,conversation_id,ask_run_id,role,content
                        ) values (
                          :user_message_id,:user_id,:project_id,:conversation_id,null,'user',:prompt
                        ),(
                          :assistant_message_id,:user_id,:project_id,:conversation_id,:run_id,
                          'assistant',:answer
                        )
                        """
                    ),
                    {
                        "user_message_id": user_message_id,
                        "assistant_message_id": uuid4(),
                        "user_id": user.id,
                        "project_id": project_id,
                        "conversation_id": conversation_id,
                        "run_id": run_id,
                        "prompt": message,
                        "answer": assistant_answer,
                    },
                )
                connection.execute(
                    text(
                        """
                        update ask_runs set message_id=:message_id
                        where id=:run_id and user_id=:user_id
                        """
                    ),
                    {
                        "message_id": user_message_id,
                        "run_id": run_id,
                        "user_id": user.id,
                    },
                )
                connection.execute(
                    text("update conversations set updated_at=now() where id=:id"),
                    {"id": conversation_id},
                )
        return run_id, trace_id

    def save_quiz_set(
        self, user: CurrentUser, project_id: UUID, run_id: UUID, quiz_set: QuizSet
    ) -> QuizSet:
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, project_id):
                raise ValueError("project is not owned by the current user")
            run = connection.execute(
                text(
                    """
                    select id from ask_runs
                    where id = :run_id and project_id = :project_id and user_id = :user_id
                    """
                ),
                {"run_id": run_id, "project_id": project_id, "user_id": user.id},
            ).one_or_none()
            if run is None:
                raise ValueError("run is not owned by the current user")
            connection.execute(
                text(
                    """
                    insert into quiz_sets (
                      id, user_id, project_id, ask_run_id, title, sources_summary
                    ) values (
                      :id, :user_id, :project_id, :run_id, :title, cast(:sources as jsonb)
                    )
                    """
                ),
                {
                    "id": quiz_set.id,
                    "user_id": user.id,
                    "project_id": project_id,
                    "run_id": run_id,
                    "title": "Generated evidence quiz",
                    "sources": _json(quiz_set.sources.model_dump(mode="json")),
                },
            )
            for question in quiz_set.questions:
                connection.execute(
                    text(
                        """
                        insert into quiz_questions (
                          id, quiz_set_id, type, question, options, answer, explanation,
                          difficulty, source_citations
                        ) values (
                          :id, :quiz_set_id, :type, :question, cast(:options as jsonb),
                          :answer, :explanation, :difficulty, cast(:citations as jsonb)
                        )
                        """
                    ),
                    {
                        "id": question.id,
                        "quiz_set_id": quiz_set.id,
                        "type": question.type,
                        "question": question.question,
                        "options": _json(question.options),
                        "answer": question.answer,
                        "explanation": question.explanation,
                        "difficulty": _enum_value(question.difficulty),
                        "citations": _json(
                            [citation.model_dump(mode="json") for citation in question.source_citations]
                        ),
                    },
                )
        return quiz_set

    def list_quiz_sets(
        self, user: CurrentUser, project_id: UUID
    ) -> list[QuizSet] | None:
        if self.get_project(user, project_id) is None:
            return None
        with self._transaction(user) as connection:
            sets = list(
                connection.execute(
                    text(
                        """
                        select id, sources_summary
                        from quiz_sets
                        where user_id = :user_id and project_id = :project_id
                        order by created_at desc, id
                        """
                    ),
                    {"user_id": user.id, "project_id": project_id},
                ).mappings()
            )
            result: list[QuizSet] = []
            for quiz_row in sets:
                questions = connection.execute(
                    text(
                        """
                        select qq.id, qq.type, qq.question, qq.options, qq.answer,
                               qq.explanation, qq.difficulty, qq.source_citations
                        from quiz_questions qq
                        join quiz_sets qs on qs.id = qq.quiz_set_id
                        where qq.quiz_set_id = :quiz_set_id and qs.user_id = :user_id
                        order by qq.created_at, qq.id
                        """
                    ),
                    {"quiz_set_id": quiz_row["id"], "user_id": user.id},
                ).mappings()
                parsed_questions = [
                    QuizQuestion(
                        id=row["id"],
                        type=row["type"],
                        question=row["question"],
                        options=row["options"],
                        answer=row["answer"],
                        explanation=row["explanation"],
                        difficulty=row["difficulty"],
                        source_citations=[
                            Citation.model_validate(item) for item in row["source_citations"]
                        ],
                    )
                    for row in questions
                ]
                result.append(
                    QuizSet(
                        id=quiz_row["id"],
                        sources=SourceSummary.model_validate(quiz_row["sources_summary"]),
                        questions=parsed_questions,
                    )
                )
            return result

    def ensure_conversation(
        self,
        user: CurrentUser,
        project_id: UUID,
        conversation_id: UUID | None,
        first_message: str,
    ) -> ConversationSummary | None:
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, project_id):
                return None
            if conversation_id is not None:
                row = connection.execute(
                    text(
                        """
                        select id, project_id, title, created_at, updated_at
                        from conversations
                        where id=:id and project_id=:project_id and user_id=:user_id
                          and deleted_at is null
                          and exists (
                            select 1 from projects p
                            where p.id=conversations.project_id
                              and p.user_id=:user_id and p.status='active'
                              and p.deleted_at is null
                          )
                        """
                    ),
                    {
                        "id": conversation_id,
                        "project_id": project_id,
                        "user_id": user.id,
                    },
                ).mappings().one_or_none()
            else:
                row = connection.execute(
                    text(
                        """
                        insert into conversations (id,user_id,project_id,title)
                        select :id,:user_id,p.id,:title
                        from projects p
                        where p.id=:project_id and p.user_id=:user_id
                          and p.status='active' and p.deleted_at is null
                        returning id,project_id,title,created_at,updated_at
                        """
                    ),
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "user_id": user.id,
                        "title": (" ".join(first_message.split())[:120] or "New conversation"),
                    },
                ).mappings().one_or_none()
        return ConversationSummary.model_validate(row) if row else None

    def list_conversations(
        self, user: CurrentUser, project_id: UUID
    ) -> list[ConversationSummary] | None:
        with self._transaction(user) as connection:
            project = connection.execute(
                text(
                    """
                    select 1 from projects
                    where id=:project_id and user_id=:user_id
                      and status='active' and deleted_at is null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).one_or_none()
            if project is None:
                return None
            rows = connection.execute(
                text(
                    """
                    select id,project_id,title,created_at,updated_at
                    from conversations
                    where project_id=:project_id and user_id=:user_id and deleted_at is null
                    order by updated_at desc limit 100
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings()
            return [ConversationSummary.model_validate(row) for row in rows]

    def conversation_messages(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[ConversationMessage] | None:
        with self._transaction(user) as connection:
            owned = connection.execute(
                text(
                    """
                    select 1 from conversations
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    """
                ),
                {"id": conversation_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = list(
                connection.execute(
                    text(
                        """
                        select id,conversation_id,role,content,ask_run_id,created_at
                        from messages
                        where conversation_id=:id and user_id=:user_id
                          and role in ('user','assistant')
                        order by created_at,
                                 case role when 'user' then 0 when 'assistant' then 1 else 2 end,
                                 id
                        """
                    ),
                    {"id": conversation_id, "user_id": user.id},
                ).mappings()
            )
            result: list[ConversationMessage] = []
            for row in rows:
                citations = []
                if row["ask_run_id"] is not None:
                    citation_rows = connection.execute(
                        text(
                            """
                            select id,source_type,document_id,chunk_id,page_no,slide_no,
                                   url,quote,claim_id
                            from citations
                            where ask_run_id=:run_id
                            order by created_at,id
                            """
                        ),
                        {"run_id": row["ask_run_id"]},
                    ).mappings()
                    citations = [Citation.model_validate(item) for item in citation_rows]
                result.append(
                    ConversationMessage(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        citations=citations,
                        created_at=row["created_at"],
                    )
                )
            return result

    def rename_conversation(
        self, user: CurrentUser, conversation_id: UUID, title: str
    ) -> ConversationSummary | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update conversations
                    set title=:title,updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    returning id,project_id,title,created_at,updated_at
                    """
                ),
                {"id": conversation_id, "user_id": user.id, "title": title.strip()},
            ).mappings().one_or_none()
        return ConversationSummary.model_validate(row) if row else None

    def delete_conversation(self, user: CurrentUser, conversation_id: UUID) -> bool:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update conversations
                    set deleted_at=now(),updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    returning id
                    """
                ),
                {"id": conversation_id, "user_id": user.id},
            ).one_or_none()
        return row is not None


    def get_runtime_rerank_config(self) -> RuntimeRerankConfig:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    select provider,version,updated_at,updated_by
                    from runtime_ai_config where config_key='rerank'
                    """
                )
            ).mappings().one()
        return RuntimeRerankConfig.model_validate(row)

    def update_runtime_rerank_config(
        self, user: CurrentUser, provider: str, expected_version: int
    ) -> RuntimeRerankConfig | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update runtime_ai_config
                    set provider=:provider,version=version+1,updated_at=now(),updated_by=:user_id
                    where config_key='rerank' and version=:expected_version
                    returning provider,version,updated_at,updated_by
                    """
                ),
                {
                    "provider": provider,
                    "user_id": user.id,
                    "expected_version": expected_version,
                },
            ).mappings().one_or_none()
        return RuntimeRerankConfig.model_validate(row) if row else None

    def conversation_summary(
        self, user: CurrentUser, conversation_id: UUID
    ) -> tuple[str | None, int] | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select summary_text,summary_message_count
                    from conversations
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    """
                ),
                {"id": conversation_id, "user_id": user.id},
            ).mappings().one_or_none()
        if row is None:
            return None
        return row["summary_text"], int(row["summary_message_count"])

    def update_conversation_summary(
        self,
        user: CurrentUser,
        conversation_id: UUID,
        summary: str,
        message_count: int,
    ) -> bool:
        from researchmate_api.services.retrieval import estimate_tokens

        with self._transaction(user) as connection:
            updated = connection.execute(
                text(
                    """
                    update conversations
                    set summary_text=:summary,
                        summary_token_count=:tokens,
                        summary_message_count=:message_count,
                        summary_updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    """
                ),
                {
                    "summary": summary,
                    "tokens": estimate_tokens(summary),
                    "message_count": message_count,
                    "id": conversation_id,
                    "user_id": user.id,
                },
            )
        return bool(updated.rowcount)

    def increment_usage(self, user: CurrentUser, kind: str, limit: int) -> bool:
        with self._transaction(user) as connection:
            count = connection.execute(
                text(
                    """
                    insert into api_usage (id, user_id, usage_date, kind, count)
                    select :id, :user_id, current_date, :kind, 1
                    where exists (select 1 from profiles where id = :user_id)
                    on conflict (user_id, usage_date, kind) do update
                    set count = api_usage.count + 1, updated_at = now()
                    where api_usage.user_id = :user_id
                    returning count
                    """
                ),
                {"id": uuid4(), "user_id": user.id, "kind": kind},
            ).scalar_one()
        return int(count) <= limit

    def project_chunks(
        self, user: CurrentUser, project_id: UUID
    ) -> list[ChunkEntry] | None:
        if self.get_project(user, project_id) is None:
            return None
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, source_type, source_title,
                           text, page_no, slide_no, url, created_at
                    from chunks
                    where user_id = :user_id and project_id = :project_id
                    order by created_at, id
                    """
                ),
                {"user_id": user.id, "project_id": project_id},
            ).mappings()
            return [ChunkEntry(**dict(row)) for row in rows]

    def get_chunks_by_ids(
        self, user: CurrentUser, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry] | None:
        if self.get_project(user, project_id) is None:
            return None
        if not chunk_ids:
            return []
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, source_type, source_title,
                           text, page_no, slide_no, url, created_at
                    from chunks
                    where user_id = :user_id and project_id = :project_id
                      and id = any(:chunk_ids) and source_type = 'local_doc'
                    """
                ),
                {"user_id": user.id, "project_id": project_id, "chunk_ids": chunk_ids},
            ).mappings()
            by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    def _enqueue_project_deletion(
        self,
        connection: Connection,
        *,
        user_id: UUID,
        project_id: UUID,
        job_id: UUID,
        delivery_id: UUID,
    ) -> None:
        """Persist one independently deduplicated delivery for a project-deletion job."""
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type, aggregate_id, event_type, payload, idempotency_key
                )
                select
                  'project', :project_id, 'project.delete.requested',
                  cast(:payload as jsonb), :idempotency_key
                where not exists (
                  select 1 from outbox_events pending
                  where pending.event_type = 'project.delete.requested'
                    and pending.payload ->> 'job_id' = :job_id
                    and pending.status in ('pending', 'publishing')
                )
                  and not exists (
                    select 1 from outbox_events recent
                    where recent.event_type = 'project.delete.requested'
                      and recent.payload ->> 'job_id' = :job_id
                      and recent.created_at > now() - interval '30 seconds'
                  )
                  and (
                    select count(*) from outbox_events prior
                    where prior.event_type = 'project.delete.requested'
                      and prior.payload ->> 'job_id' = :job_id
                  ) < 5
                on conflict (idempotency_key) do nothing
                """
            ),
            {
                "project_id": project_id,
                "payload": _json(
                    {
                        "job_id": str(job_id),
                        "user_id": str(user_id),
                        "project_id": str(project_id),
                    }
                ),
                "job_id": str(job_id),
                "idempotency_key": f"project:{project_id}:delete:{job_id}:{delivery_id}",
            },
        )

    def _enqueue_document_event(
        self,
        connection: Connection,
        *,
        event_type: str,
        document_id: UUID,
        user_id: UUID,
        project_id: UUID,
        job_id: UUID,
        delivery_id: UUID,
    ) -> None:
        """Persist one independently deduplicated ingestion or deletion delivery."""
        action = "ingest" if event_type == "document.ingest.requested" else "delete"
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type, aggregate_id, event_type, payload, idempotency_key
                )
                select
                  'document', :document_id, :event_type,
                  cast(:payload as jsonb), :idempotency_key
                where not exists (
                  select 1 from outbox_events pending
                  where pending.event_type = :event_type
                    and pending.payload ->> 'job_id' = :job_id
                    and pending.status in ('pending', 'publishing')
                )
                  and not exists (
                    select 1 from outbox_events recent
                    where recent.event_type = :event_type
                      and recent.payload ->> 'job_id' = :job_id
                      and recent.created_at > now() - interval '30 seconds'
                  )
                  and (
                    select count(*) from outbox_events prior
                    where prior.event_type = :event_type
                      and prior.payload ->> 'job_id' = :job_id
                  ) < 5
                on conflict (idempotency_key) do nothing
                """
            ),
            {
                "document_id": document_id,
                "event_type": event_type,
                "job_id": str(job_id),
                "payload": _json(
                    {
                        "job_id": str(job_id),
                        "user_id": str(user_id),
                        "project_id": str(project_id),
                        "document_id": str(document_id),
                    }
                ),
                "idempotency_key": (
                    f"document:{document_id}:{action}:{job_id}:{delivery_id}"
                ),
            },
        )

    @staticmethod
    def _lock_active_project(
        connection: Connection, user_id: UUID, project_id: UUID
    ) -> bool:
        """Serialize project-scoped writes against the active-to-deleting transition."""
        row = connection.execute(
            text(
                """
                select 1 from projects
                where id = :project_id and user_id = :user_id
                  and status = 'active' and deleted_at is null
                for update
                """
            ),
            {"project_id": project_id, "user_id": user_id},
        ).one_or_none()
        return row is not None

    def _load_citations(
        self, connection: Connection, user_id: UUID, run_id: UUID
    ) -> list[Citation]:
        rows = connection.execute(
            text(
                """
                select c.id, c.source_type, c.document_id, c.chunk_id, c.page_no, c.slide_no,
                       c.url, c.quote, c.claim_id
                from citations c
                join ask_runs ar on ar.id = c.ask_run_id
                where c.ask_run_id = :run_id and ar.user_id = :user_id
                order by c.created_at, c.id
                """
            ),
            {"run_id": run_id, "user_id": user_id},
        ).mappings()
        return [Citation.model_validate(dict(row)) for row in rows]

    def _insert_job(
        self,
        connection: Connection,
        *,
        user: CurrentUser,
        project_id: UUID | None,
        document_id: UUID | None,
        job_type: str,
        status: JobStatus,
        progress: int,
        error_message: str | None = None,
        payload: dict | None = None,
    ) -> JobRecord:
        row = connection.execute(
            text(
                """
                insert into jobs (
                  id, user_id, project_id, document_id, type, status, progress, payload, error_message
                ) values (
                  :id, :user_id, :project_id, :document_id, :type, :status, :progress,
                  cast(:payload as jsonb), :error
                )
                returning id, user_id, project_id, document_id, type, status, progress,
                          error_message, created_at, updated_at
                """
            ),
            {
                "id": uuid4(),
                "user_id": user.id,
                "project_id": project_id,
                "document_id": document_id,
                "type": job_type,
                "status": _enum_value(status),
                "progress": progress,
                "payload": _json(payload or {}),
                "error": error_message,
            },
        ).mappings().one()
        return JobRecord.model_validate(dict(row))
