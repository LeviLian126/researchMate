"""Define deletion events, records, and adapter contracts shared by worker services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class DocumentDeletionEvent(BaseModel):
    """Validate identifiers for one durable document-deletion delivery."""

    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID


class ProjectDeletionEvent(BaseModel):
    """Validate identifiers for one durable project-deletion delivery."""

    job_id: UUID
    user_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class DeletionRecord:
    """Carry the claimed document artifacts and ownership scope."""

    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID
    r2_object_key: str
    qdrant_point_ids: list[str]
    attempts: int


@dataclass(frozen=True)
class ProjectDeletionRecord:
    """Carry the claimed project artifacts and ownership scope."""

    job_id: UUID
    user_id: UUID
    project_id: UUID
    r2_object_keys: list[str]
    qdrant_point_ids: list[str]
    attempts: int


class DeletionStore(Protocol):
    """Define lease-safe persistence operations for document deletion."""

    def claim(
        self, event: DocumentDeletionEvent, *, worker_id: str, lease_seconds: int
    ) -> DeletionRecord | None: ...

    def mark_ready(self, record: DeletionRecord, *, worker_id: str) -> None: ...

    def mark_retryable(self, record: DeletionRecord, *, worker_id: str, code: str) -> None: ...

    def mark_failed(self, record: DeletionRecord, *, worker_id: str, code: str) -> None: ...


class ObjectDeletion(Protocol):
    """Define remote object removal without exposing a storage SDK."""

    def delete(self, object_key: str) -> None: ...


class VectorDeletion(Protocol):
    """Define scoped vector removal for documents and projects."""

    def delete_points(self, point_ids: list[str], *, user_id: str, project_id: str) -> None: ...

    def delete_project_points(self, *, user_id: str, project_id: str) -> None: ...


class ProjectDeletionStore(Protocol):
    """Define lease-safe persistence operations for project deletion."""

    def claim(
        self, event: ProjectDeletionEvent, *, worker_id: str, lease_seconds: int
    ) -> ProjectDeletionRecord | None: ...

    def mark_ready(self, record: ProjectDeletionRecord, *, worker_id: str) -> None: ...

    def mark_retryable(
        self, record: ProjectDeletionRecord, *, worker_id: str, code: str
    ) -> None: ...

    def mark_failed(self, record: ProjectDeletionRecord, *, worker_id: str, code: str) -> None: ...
