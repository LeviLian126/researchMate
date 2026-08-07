"""Prepare Ask conversation scope without creating empty conversations on failure."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from researchmate_api.schemas.ask import AskRequest
from researchmate_api.schemas.common import CurrentUser, DocumentStatus
from researchmate_api.schemas.conversation import ConversationSummary
from researchmate_api.schemas.document import DocumentRecord
from researchmate_api.schemas.project import ProjectRecord
from researchmate_api.services.query_context import (
    ContextOutcome,
    ConversationContextBuilder,
    build_project_memory,
)
from researchmate_api.services.query_errors import raise_grounded_error
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository


@dataclass(frozen=True)
class ConversationPreparation:
    """Carry validated scope, evidence, and bounded history into Ask execution."""

    project: ProjectRecord
    conversation: ConversationSummary | None
    documents: list[DocumentRecord]
    chunks: list[ChunkEntry]
    context: ContextOutcome


class QueryConversationCoordinator:
    """Validate conversation scope while deferring creation until generation succeeds."""

    def __init__(
        self,
        repository: ResearchMateRepository,
        context_builder: ConversationContextBuilder,
    ) -> None:
        """Bind persistence and context-compaction collaborators."""
        self.repository = repository
        self.context_builder = context_builder

    def prepare(self, user: CurrentUser, payload: AskRequest) -> ConversationPreparation:
        """Load accessible evidence and context without creating a new conversation."""
        project = self.repository.get_project(user, payload.project_id)
        if project is None or project.status != "active":
            raise_grounded_error("PROJECT_NOT_FOUND", "Project was not found.", 404)

        conversation = self._existing_conversation(user, payload)
        if project.kind == "workspace":
            documents = self.repository.list_project_documents(user, payload.project_id) or []
            chunks = self.repository.project_chunks(user, payload.project_id)
        elif conversation is None:
            documents, chunks = [], []
        else:
            documents = self.repository.list_conversation_documents(user, conversation.id) or []
            chunks = self.repository.conversation_chunks(user, payload.project_id, conversation.id)
        if chunks is None:
            raise_grounded_error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        self._reject_processing_documents(documents, chunks)

        context = self._build_context(user, payload, project, conversation)
        return ConversationPreparation(project, conversation, documents, chunks, context)

    def ensure_for_commit(
        self,
        user: CurrentUser,
        payload: AskRequest,
        conversation: ConversationSummary | None,
    ) -> ConversationSummary:
        """Create a new conversation only after answer generation has succeeded."""
        if conversation is not None:
            return conversation
        created = self.repository.ensure_conversation(
            user, payload.project_id, None, payload.message
        )
        if created is None:
            raise_grounded_error("CONVERSATION_NOT_FOUND", "Conversation was not found.", 404)
        return created

    def _existing_conversation(
        self, user: CurrentUser, payload: AskRequest
    ) -> ConversationSummary | None:
        """Validate a supplied conversation identifier without creating a replacement."""
        if payload.conversation_id is None:
            return None
        conversation = self.repository.ensure_conversation(
            user, payload.project_id, payload.conversation_id, payload.message
        )
        if conversation is None:
            raise_grounded_error("CONVERSATION_NOT_FOUND", "Conversation was not found.", 404)
        return conversation

    def _build_context(
        self,
        user: CurrentUser,
        payload: AskRequest,
        project: ProjectRecord,
        conversation: ConversationSummary | None,
    ) -> ContextOutcome:
        """Build bounded current-conversation and untrusted cross-conversation memory."""
        if conversation is None:
            context = ContextOutcome([])
        else:
            context = self.context_builder.build(
                user,
                conversation.id,
                self.repository.conversation_messages(user, conversation.id) or [],
            )
        if project.kind != "workspace":
            return context
        excluded_id = conversation.id if conversation is not None else UUID(int=0)
        memory = self.repository.project_memory_context(user, payload.project_id, excluded_id) or []
        return ContextOutcome(
            [*build_project_memory(memory), *context.messages],
            degraded=context.degraded,
            reason=context.reason,
        )

    @staticmethod
    def _reject_processing_documents(
        documents: list[DocumentRecord], chunks: list[ChunkEntry]
    ) -> None:
        """Prevent premature queries while every uploaded document is still processing."""
        processing = {
            DocumentStatus.UPLOADED,
            DocumentStatus.PARSING,
            DocumentStatus.PARSED,
            DocumentStatus.INDEXING,
        }
        if documents and not chunks and any(item.status in processing for item in documents):
            raise_grounded_error(
                "DOCUMENT_PROCESSING",
                "Uploaded documents are still being processed.",
                409,
            )
