"""Own in-memory rerank configuration and conversation/project memory."""

# ruff: noqa: F401
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast
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


class MemoryStoreMixin:
    """Own in-memory rerank configuration and conversation/project memory."""

    if TYPE_CHECKING:
        # Provided by InMemoryStoreCore and sibling mixins composed in InMemoryResearchMateStore.
        _lock: RLock
        conversations: dict[UUID, ConversationSummary]
        conversation_items: dict[UUID, list[ConversationMessage]]
        conversation_summaries: dict[UUID, tuple[str, int]]
        runtime_rerank_config: RuntimeRerankConfig

        def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...

    def get_runtime_rerank_config(self) -> RuntimeRerankConfig:
        """Return the active runtime rerank configuration."""
        with self._lock:
            return self.runtime_rerank_config

    def update_runtime_rerank_config(
        self, user: CurrentUser, provider: str, expected_version: int
    ) -> RuntimeRerankConfig | None:
        """Update rerank configuration using optimistic version control."""
        with self._lock:
            current = self.runtime_rerank_config
            if current.version != expected_version:
                return None
            # The protocol/sibling signature keeps `provider: str` for API symmetry; the
            # router validates it against the same Literal before this call, so cast here.
            self.runtime_rerank_config = RuntimeRerankConfig(
                provider=cast(Literal["auto", "qdrant", "nvidia", "deterministic"], provider),
                version=current.version + 1,
                updated_at=datetime.now(UTC),
                updated_by=user.id,
            )
            return self.runtime_rerank_config

    def conversation_summary(
        self, user: CurrentUser, conversation_id: UUID
    ) -> tuple[str | None, int] | None:
        """Return the saved rolling summary for an owned conversation."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return None
            return self.conversation_summaries.get(conversation_id, (None, 0))

    def update_conversation_summary(
        self,
        user: CurrentUser,
        conversation_id: UUID,
        summary: str,
        message_count: int,
    ) -> bool:
        """Replace an owned conversation summary at the expected message count."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return False
            self.conversation_summaries[conversation_id] = (summary, message_count)
            return True

    def project_memory_context(
        self,
        user: CurrentUser,
        project_id: UUID,
        exclude_conversation_id: UUID,
        limit: int = 16,
    ) -> list[ConversationMessage] | None:
        """Return recent conversation memory for an owned project."""
        with self._lock:
            project = self.get_project(user, project_id)
            if project is None:
                return None
            if project.kind != "workspace":
                return []
            other_ids = {
                conversation.id
                for conversation in self.conversations.values()
                if conversation.project_id == project_id
                and conversation.id != exclude_conversation_id
            }
            messages = [
                message
                for conversation_id in other_ids
                for message in self.conversation_items.get(conversation_id, [])
            ]
            for conversation_id in other_ids:
                summary, _ = self.conversation_summaries.get(conversation_id, (None, 0))
                if summary:
                    messages.append(
                        ConversationMessage(
                            id=uuid4(),
                            conversation_id=conversation_id,
                            role="assistant",
                            content=f"Project conversation summary: {summary}",
                            citations=[],
                            created_at=self.conversations[conversation_id].updated_at,
                        )
                    )
            return sorted(messages, key=lambda item: item.created_at)[-limit:]
