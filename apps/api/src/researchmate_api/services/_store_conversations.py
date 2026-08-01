"""Own in-memory conversation lifecycle and attachment-aware deletion."""

# ruff: noqa: F401
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Literal, Protocol
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


class ConversationStoreMixin:
    """Own in-memory conversation lifecycle and attachment-aware deletion."""

    def ensure_conversation(
        self,
        user: CurrentUser,
        project_id: UUID,
        conversation_id: UUID | None,
        first_message: str,
    ) -> ConversationSummary | None:
        """Return or create an owned conversation for a query."""
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            if conversation_id is not None:
                conversation = self.conversations.get(conversation_id)
                if conversation is None or conversation.project_id != project_id:
                    return None
                if (
                    conversation.title == "New chat"
                    and not self.conversation_items.get(conversation_id)
                ):
                    conversation = conversation.model_copy(
                        update={
                            "title": " ".join(first_message.split())[:120],
                            "updated_at": datetime.now(UTC),
                        }
                    )
                    self.conversations[conversation_id] = conversation
                return conversation
            now = datetime.now(UTC)
            title = " ".join(first_message.split())[:120] or "New conversation"
            conversation = ConversationSummary(
                id=uuid4(),
                project_id=project_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            self.conversations[conversation.id] = conversation
            self.conversation_items[conversation.id] = []
            return conversation

    def create_conversation(
        self, user: CurrentUser, project_id: UUID, title: str
    ) -> ConversationSummary | None:
        """Create an owned conversation with the requested title."""
        return self.ensure_conversation(user, project_id, None, title)

    def list_conversations(
        self, user: CurrentUser, project_id: UUID
    ) -> list[ConversationSummary] | None:
        """List conversations in an owned project."""
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            return sorted(
                (
                    item
                    for item in self.conversations.values()
                    if item.project_id == project_id
                ),
                key=lambda item: item.updated_at,
                reverse=True,
            )[:100]

    def list_all_conversations(self, user: CurrentUser) -> list[ConversationSummary]:
        """List all conversations visible to the caller."""
        with self._lock:
            return sorted(
                (
                    item
                    for item in self.conversations.values()
                    if self.get_project(user, item.project_id) is not None
                ),
                key=lambda item: item.updated_at,
                reverse=True,
            )[:100]

    def conversation_messages(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[ConversationMessage] | None:
        """Return messages belonging to an owned conversation."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return None
            return list(self.conversation_items.get(conversation_id, []))

    def rename_conversation(
        self, user: CurrentUser, conversation_id: UUID, title: str
    ) -> ConversationSummary | None:
        """Rename an owned conversation."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return None
            updated = conversation.model_copy(
                update={"title": title.strip(), "updated_at": datetime.now(UTC)}
            )
            self.conversations[conversation_id] = updated
            return updated

    def delete_conversation(self, user: CurrentUser, conversation_id: UUID) -> bool:
        """Hide an owned conversation and its memory state."""
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None or self.get_project(user, conversation.project_id) is None:
                return False
            for document in list(self.documents.values()):
                if document.conversation_id == conversation_id and document.user_id == user.id:
                    self.delete_document(user, document.id)
            self.conversations.pop(conversation_id, None)
            self.conversation_items.pop(conversation_id, None)
            self.conversation_summaries.pop(conversation_id, None)
            return True

    def delete_conversation_with_attachments(
        self, user: CurrentUser, conversation_id: UUID
    ) -> bool:
        """Delete attachment intents and the conversation as one recoverable memory unit."""
        with self._lock:
            documents = self.list_conversation_documents(user, conversation_id)
            if documents is None:
                return False
            snapshot = (
                dict(self.documents),
                dict(self.chunks),
                dict(self.jobs),
                dict(self.conversations),
                {key: list(value) for key, value in self.conversation_items.items()},
                dict(self.conversation_summaries),
            )
            try:
                for document in documents:
                    if self.delete_document(user, document.id) is None:
                        raise ValueError("conversation attachment cleanup failed")
                if not self.delete_conversation(user, conversation_id):
                    raise ValueError("conversation deletion failed")
            except Exception:
                (
                    self.documents,
                    self.chunks,
                    self.jobs,
                    self.conversations,
                    self.conversation_items,
                    self.conversation_summaries,
                ) = snapshot
                raise
            return True
