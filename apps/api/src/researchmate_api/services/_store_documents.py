"""Own in-memory upload, document, and ingestion job state."""

# ruff: noqa: F401
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, Protocol
from uuid import UUID, uuid4

from researchmate_api.schemas.common import (
    Citation,
    CurrentUser,
    DocumentStatus,
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
from researchmate_api.schemas.quiz import QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.services._store_models import (
    ChunkEntry,
    IdempotencyDecision,
    UploadReservation,
)
from researchmate_api.services._store_text import chunk_text


class DocumentStoreMixin:
    """Own in-memory upload, document, and ingestion job state."""

    if TYPE_CHECKING:
        # Provided by InMemoryStoreCore and sibling mixins composed in InMemoryResearchMateStore.
        _lock: RLock
        documents: dict[UUID, DocumentRecord]
        uploads: dict[UUID, UploadReservation]
        chunks: dict[UUID, ChunkEntry]
        jobs: dict[UUID, JobRecord]
        conversations: dict[UUID, ConversationSummary]

        def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...
        def _create_job_locked(
            self,
            user: CurrentUser,
            project_id: UUID | None,
            document_id: UUID | None,
            job_type: str,
            status: JobStatus,
            progress: int,
            error_message: str | None = None,
        ) -> JobRecord: ...

    def create_upload_url(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> UploadUrlResponse | None:
        """Reserve an owned document and return its upload destination."""
        with self._lock:
            project = self.get_project(user, payload.project_id)
            if project is None or project.status != "active":
                return None
            if project.kind == "personal":
                if payload.conversation_id is None:
                    return None
                conversation = self.conversations.get(payload.conversation_id)
                if (
                    conversation is None
                    or conversation.project_id != project.id
                    or self.get_project(user, conversation.project_id) is None
                ):
                    return None
            elif payload.conversation_id is not None:
                return None
            now = datetime.now(UTC)
            document_id = uuid4()
            r2_object_key = f"users/{user.id}/projects/{payload.project_id}/documents/{document_id}/{payload.filename}"
            document = DocumentRecord(
                id=document_id,
                user_id=user.id,
                project_id=payload.project_id,
                conversation_id=payload.conversation_id,
                filename=payload.filename,
                file_type=payload.file_type,
                mime_type=payload.mime_type,
                size_bytes=payload.size_bytes,
                status=DocumentStatus.UPLOADED,
                error_message=None,
                expires_at=now + timedelta(days=7),
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            self.documents[document_id] = document
            self.uploads[document_id] = UploadReservation(document_id, r2_object_key, payload, now)
            return UploadUrlResponse(
                document_id=document_id,
                upload_url=f"http://localhost:8000/api/v1/dev/upload/{document_id}",
                r2_object_key=r2_object_key,
                expires_in_seconds=600,
            )

    def create_document(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> DocumentRecord | None:
        """Resolve the latest matching uploaded document reservation."""
        with self._lock:
            project = self.get_project(user, payload.project_id)
            if project is None or project.status != "active":
                return None
            for reservation in self.uploads.values():
                if (
                    reservation.request.project_id == payload.project_id
                    and reservation.request.conversation_id == payload.conversation_id
                    and reservation.request.filename == payload.filename
                    and reservation.request.size_bytes == payload.size_bytes
                ):
                    document = self.documents.get(reservation.document_id)
                    if document and document.user_id == user.id:
                        return document
            response = self.create_upload_url(user, payload)
            return None if response is None else self.documents[response.document_id]

    def list_project_documents(
        self, user: CurrentUser, project_id: UUID
    ) -> list[DocumentRecord] | None:
        """List visible documents belonging to an owned project."""
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            return [
                document
                for document in self.documents.values()
                if document.project_id == project_id
                and document.user_id == user.id
                and document.deleted_at is None
            ]

    def list_conversation_documents(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[DocumentRecord] | None:
        """List visible attachments belonging to an owned conversation."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return None
            return [
                document
                for document in self.documents.values()
                if document.user_id == user.id
                and document.conversation_id == conversation_id
                and document.deleted_at is None
            ]

    def get_document(self, user: CurrentUser, document_id: UUID) -> DocumentRecord | None:
        """Return one visible document owned by the caller."""
        with self._lock:
            document = self.documents.get(document_id)
            if document is None or document.user_id != user.id or document.deleted_at is not None:
                return None
            return document

    def complete_document(
        self,
        user: CurrentUser,
        document_id: UUID,
        extracted_text: str | None,
        checksum_sha256: str | None = None,
    ) -> JobRecord | None:
        """Complete local ingestion and materialize retrievable chunks."""
        with self._lock:
            document = self.get_document(user, document_id)
            if document is None:
                return None
            project = self.get_project(user, document.project_id)
            if project is None or project.status != "active":
                return None
            now = datetime.now(UTC)
            status = (
                DocumentStatus.READY
                if extracted_text and extracted_text.strip()
                else DocumentStatus.FAILED
            )
            error_message = (
                None if status == DocumentStatus.READY else "No extractable text was provided."
            )
            self.documents[document_id] = document.model_copy(
                update={"status": status, "error_message": error_message, "updated_at": now}
            )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.document_id == document_id:
                    del self.chunks[chunk_id]
            if extracted_text and extracted_text.strip():
                for index, text in enumerate(chunk_text(extracted_text), start=1):
                    chunk_id = uuid4()
                    self.chunks[chunk_id] = ChunkEntry(
                        id=chunk_id,
                        user_id=user.id,
                        project_id=document.project_id,
                        document_id=document.id,
                        source_type=SourceType.LOCAL_DOC,
                        source_title=document.filename,
                        text=text,
                        page_no=index,
                    )
            return self._create_job_locked(
                user=user,
                project_id=document.project_id,
                document_id=document.id,
                job_type="parse_and_index_document",
                status=JobStatus.SUCCEEDED if status == DocumentStatus.READY else JobStatus.FAILED,
                progress=100,
                error_message=error_message,
            )

    def delete_document(self, user: CurrentUser, document_id: UUID) -> JobRecord | None:
        """Delete an owned document and its process-local dependent state."""
        with self._lock:
            document = self.get_document(user, document_id)
            if document is None:
                return None
            project = self.get_project(user, document.project_id)
            if project is None or project.status != "active":
                return None
            now = datetime.now(UTC)
            self.documents[document_id] = document.model_copy(
                update={"status": DocumentStatus.DELETED, "deleted_at": now, "updated_at": now}
            )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.document_id == document_id:
                    del self.chunks[chunk_id]
            return self._create_job_locked(
                user=user,
                project_id=document.project_id,
                document_id=document.id,
                job_type="delete_document",
                status=JobStatus.SUCCEEDED,
                progress=100,
            )

    def get_job(self, user: CurrentUser, job_id: UUID) -> JobRecord | None:
        """Return one background job visible to the caller."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.user_id != user.id:
                return None
            return job
