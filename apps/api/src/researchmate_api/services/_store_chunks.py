"""Own in-memory authorized chunk retrieval."""

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


class ChunkStoreMixin:
    """Own in-memory authorized chunk retrieval."""

    if TYPE_CHECKING:
        # Provided by InMemoryStoreCore and sibling mixins composed in InMemoryResearchMateStore.
        _lock: RLock
        chunks: dict[UUID, ChunkEntry]
        documents: dict[UUID, DocumentRecord]
        conversations: dict[UUID, ConversationSummary]

        def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...
        def list_conversation_documents(
            self, user: CurrentUser, conversation_id: UUID
        ) -> list[DocumentRecord] | None: ...

    def project_chunks(self, user: CurrentUser, project_id: UUID) -> list[ChunkEntry] | None:
        """Return retrievable chunks from ready sources in an owned project."""
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            return [
                chunk
                for chunk in self.chunks.values()
                if chunk.user_id == user.id
                and chunk.project_id == project_id
                and (
                    chunk.source_type != SourceType.LOCAL_DOC
                    or (
                        chunk.document_id in self.documents
                        and self.documents[chunk.document_id].status == DocumentStatus.READY
                        and self.documents[chunk.document_id].deleted_at is None
                    )
                )
            ]

    def conversation_chunks(
        self, user: CurrentUser, project_id: UUID, conversation_id: UUID
    ) -> list[ChunkEntry] | None:
        """Return retrievable ready-document chunks for an owned conversation."""
        documents = self.list_conversation_documents(user, conversation_id)
        conversation = self.conversations.get(conversation_id)
        if documents is None or conversation is None or conversation.project_id != project_id:
            return None
        document_ids = {document.id for document in documents}
        return [
            chunk
            for chunk in self.project_chunks(user, project_id) or []
            if chunk.document_id in document_ids
        ]

    def get_chunks_by_ids(
        self, user: CurrentUser, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry] | None:
        """Return requested visible chunks while preserving caller order."""
        chunks = self.project_chunks(user, project_id)
        if chunks is None:
            return None
        by_id = {chunk.id: chunk for chunk in chunks}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]
