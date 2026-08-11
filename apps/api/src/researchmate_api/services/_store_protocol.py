"""Define the application-facing ResearchMate persistence protocol."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from researchmate_api.schemas.common import Citation, CurrentUser, ExecutionPlan
from researchmate_api.schemas.conversation import (
    ConversationMessage,
    ConversationSummary,
    RuntimeRerankConfig,
)
from researchmate_api.schemas.document import DocumentRecord, UploadUrlRequest, UploadUrlResponse
from researchmate_api.schemas.feedback import FeedbackRating, FeedbackSourceContext
from researchmate_api.schemas.job import JobRecord
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.schemas.quiz import QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.schemas.trace import DeveloperTrace, ToolCallTrace
from researchmate_api.services._store_models import ChunkEntry, IdempotencyDecision


class ResearchMateRepository(Protocol):
    """Persistence boundary consumed by the current application services."""

    def ensure_user(self, user: CurrentUser) -> CurrentUser: ...

    def create_project(self, user: CurrentUser, payload: ProjectCreate) -> ProjectRecord: ...

    def ensure_personal_project(self, user: CurrentUser) -> ProjectRecord: ...

    def list_projects(self, user: CurrentUser) -> list[ProjectRecord]: ...

    def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...

    def delete_project(self, user: CurrentUser, project_id: UUID) -> JobRecord | None: ...

    def create_upload_url(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> UploadUrlResponse | None: ...

    def create_document(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> DocumentRecord | None: ...

    def list_project_documents(
        self, user: CurrentUser, project_id: UUID
    ) -> list[DocumentRecord] | None: ...

    def list_conversation_documents(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[DocumentRecord] | None: ...

    def get_document(self, user: CurrentUser, document_id: UUID) -> DocumentRecord | None: ...

    def complete_document(
        self,
        user: CurrentUser,
        document_id: UUID,
        extracted_text: str | None,
        checksum_sha256: str | None = None,
    ) -> JobRecord | None: ...

    def delete_document(self, user: CurrentUser, document_id: UUID) -> JobRecord | None: ...

    def get_job(self, user: CurrentUser, job_id: UUID) -> JobRecord | None: ...

    def get_run_sources(self, user: CurrentUser, run_id: UUID) -> RunSourcesResponse | None: ...

    def get_trace(self, user: CurrentUser, trace_id: UUID) -> DeveloperTrace | None: ...

    def feedback_source_context(
        self, user: CurrentUser, run_id: UUID
    ) -> FeedbackSourceContext | None: ...

    def set_feedback_rating(
        self, user: CurrentUser, run_id: UUID, rating: FeedbackRating
    ) -> bool: ...

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
    ) -> tuple[UUID, UUID]: ...

    def save_quiz_set(
        self, user: CurrentUser, project_id: UUID, run_id: UUID, quiz_set: QuizSet
    ) -> QuizSet: ...

    def record_quiz_run(
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
        quiz_set: QuizSet,
    ) -> tuple[UUID, UUID]: ...

    def list_quiz_sets(self, user: CurrentUser, project_id: UUID) -> list[QuizSet] | None: ...

    def increment_usage(self, user: CurrentUser, kind: str, limit: int) -> bool: ...

    def begin_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> IdempotencyDecision: ...

    def complete_idempotent_operation(
        self,
        user: CurrentUser,
        operation: str,
        key: str,
        response: dict[str, Any],
    ) -> None: ...

    def abandon_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> None: ...

    def project_chunks(self, user: CurrentUser, project_id: UUID) -> list[ChunkEntry] | None: ...

    def get_chunks_by_ids(
        self, user: CurrentUser, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry] | None: ...

    def ensure_conversation(
        self,
        user: CurrentUser,
        project_id: UUID,
        conversation_id: UUID | None,
        first_message: str,
    ) -> ConversationSummary | None: ...

    def create_conversation(
        self, user: CurrentUser, project_id: UUID, title: str
    ) -> ConversationSummary | None: ...

    def list_conversations(
        self, user: CurrentUser, project_id: UUID
    ) -> list[ConversationSummary] | None: ...

    def list_all_conversations(self, user: CurrentUser) -> list[ConversationSummary]: ...

    def conversation_messages(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[ConversationMessage] | None: ...

    def rename_conversation(
        self, user: CurrentUser, conversation_id: UUID, title: str
    ) -> ConversationSummary | None: ...

    def delete_conversation(self, user: CurrentUser, conversation_id: UUID) -> bool: ...

    def delete_conversation_with_attachments(
        self, user: CurrentUser, conversation_id: UUID
    ) -> bool: ...

    def get_runtime_rerank_config(self) -> RuntimeRerankConfig: ...

    def update_runtime_rerank_config(
        self, user: CurrentUser, provider: str, expected_version: int
    ) -> RuntimeRerankConfig | None: ...

    def conversation_summary(
        self, user: CurrentUser, conversation_id: UUID
    ) -> tuple[str | None, int] | None: ...

    def update_conversation_summary(
        self,
        user: CurrentUser,
        conversation_id: UUID,
        summary: str,
        message_count: int,
    ) -> bool: ...

    def project_memory_context(
        self,
        user: CurrentUser,
        project_id: UUID,
        exclude_conversation_id: UUID,
        limit: int = 16,
    ) -> list[ConversationMessage] | None: ...

    def conversation_chunks(
        self, user: CurrentUser, project_id: UUID, conversation_id: UUID
    ) -> list[ChunkEntry] | None: ...
