"""Own in-memory run traces and Quiz aggregate state."""

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
from researchmate_api.schemas.feedback import (
    FeedbackEvidence,
    FeedbackRating,
    FeedbackSourceContext,
    feedback_source_type,
)
from researchmate_api.schemas.job import JobRecord
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.schemas.quiz import QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.schemas.trace import DeveloperTrace, ToolCallTrace
from researchmate_api.services._store_models import (
    ChunkEntry,
    IdempotencyDecision,
    UploadReservation,
)


class RunStoreMixin:
    """Own in-memory run traces and Quiz aggregate state."""

    if TYPE_CHECKING:
        # Provided by InMemoryStoreCore and sibling mixins composed in InMemoryResearchMateStore.
        _lock: RLock
        conversations: dict[UUID, ConversationSummary]
        conversation_items: dict[UUID, list[ConversationMessage]]

        def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...

    def get_run_sources(self, user: CurrentUser, run_id: UUID) -> RunSourcesResponse | None:
        """Return the citation panel for an authorized run."""
        with self._lock:
            response = self.run_sources.get(run_id)
            if response is None:
                return None
            trace = next(
                (item for item in self.traces.values() if item.run_id == run_id),
                None,
            )
            if trace is None or trace.user_id != user.id:
                return None
            return response

    def get_trace(self, user: CurrentUser, trace_id: UUID) -> DeveloperTrace | None:
        """Return a developer trace when the caller is authorized."""
        with self._lock:
            trace = self.traces.get(trace_id)
            if trace is None:
                return None
            if user.role in {"developer", "admin"} or trace.user_id == user.id:
                return trace
            return None

    def feedback_source_context(
        self, user: CurrentUser, run_id: UUID
    ) -> FeedbackSourceContext | None:
        """Return trusted Ask snapshots for owner-scoped local feedback persistence."""
        with self._lock:
            trace = next((item for item in self.traces.values() if item.run_id == run_id), None)
            sources = self.run_sources.get(run_id)
            if trace is None or sources is None or trace.user_id != user.id:
                return None
            conversation_id = next(
                (
                    conversation_id
                    for conversation_id, messages in self.conversation_items.items()
                    if any(message.ask_run_id == run_id for message in messages)
                ),
                None,
            )
            if conversation_id is None:
                return None
            assistant = next(
                (
                    message
                    for message in self.conversation_items[conversation_id]
                    if message.ask_run_id == run_id and message.role == "assistant"
                ),
                None,
            )
            user_messages = (
                [
                    message
                    for message in self.conversation_items[conversation_id]
                    if message.role == "user" and message.created_at <= assistant.created_at
                ]
                if assistant is not None
                else []
            )
            if assistant is None or not user_messages:
                return None
            return FeedbackSourceContext(
                ask_run_id=run_id,
                user_id=user.id,
                project_id=trace.project_id,
                conversation_id=conversation_id,
                question=user_messages[-1].content,
                answer=assistant.content,
                citation_chunk_ids=[
                    citation.chunk_id
                    for citation in sources.citations
                    if citation.chunk_id is not None
                ],
                retrieved_chunk_ids=[
                    UUID(str(item["chunk_id"]))
                    for item in trace.retrieved_chunks
                    if item.get("chunk_id")
                ],
                retrieved_evidence=[
                    FeedbackEvidence(
                        chunk_id=UUID(str(item["chunk_id"])),
                        source_type=feedback_source_type(
                            item.get("source_type"), item.get("document_id")
                        ),
                        source_title=(
                            str(item["source_title"]) if item.get("source_title") else None
                        ),
                        page_no=(int(item["page_no"]) if item.get("page_no") else None),
                        excerpt=(
                            str(item["score_context"])[:240] if item.get("score_context") else None
                        ),
                    )
                    for item in trace.retrieved_chunks
                    if item.get("chunk_id")
                ],
            )

    def set_feedback_rating(self, user: CurrentUser, run_id: UUID, rating: FeedbackRating) -> bool:
        """Reflect persisted local feedback in reloaded conversation messages."""
        with self._lock:
            context = self.feedback_source_context(user, run_id)
            if context is None:
                return False
            messages = self.conversation_items[context.conversation_id]
            self.conversation_items[context.conversation_id] = [
                message.model_copy(update={"feedback_rating": rating})
                if message.ask_run_id == run_id
                else message
                for message in messages
            ]
            return True

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
        """Persist one execution run, its sources, trace, and optional messages."""
        with self._lock:
            run_id = uuid4()
            trace_id = uuid4()
            total_latency_ms = int((runtime_metadata or {}).get("total_latency_ms", 0))
            summary = SourceSummary(
                local_chunks=sum(
                    1 for citation in citations if citation.source_type == SourceType.LOCAL_DOC
                ),
                web_pages=sum(
                    1 for citation in citations if citation.source_type == SourceType.WEB_PAGE
                ),
            )
            self.run_sources[run_id] = RunSourcesResponse(
                run_id=run_id,
                summary=summary,
                citations=citations,
            )
            self.traces[trace_id] = DeveloperTrace(
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
                        "source_type": chunk.source_type,
                        "source_title": chunk.source_title,
                        "page_no": chunk.page_no,
                        "score_context": chunk.text[:240],
                    }
                    for chunk in retrieved_chunks
                ],
                tool_calls=tool_calls,
                validation_result=validation_result,
                latency_ms=total_latency_ms,
                token_usage=runtime_metadata,
                errors=[] if validation_result.get("passed", True) else ["validation_failed"],
                created_at=datetime.now(UTC),
            )
            if conversation_id is not None and assistant_answer is not None:
                conversation = self.conversations.get(conversation_id)
                if (
                    conversation is None
                    or conversation.project_id != project_id
                    or self.get_project(user, project_id) is None
                ):
                    raise ValueError("conversation is not owned by the current user")
                now = datetime.now(UTC)
                self.conversation_items.setdefault(conversation_id, []).extend(
                    [
                        ConversationMessage(
                            id=uuid4(),
                            conversation_id=conversation_id,
                            role="user",
                            content=message,
                            citations=[],
                            created_at=now,
                        ),
                        ConversationMessage(
                            id=uuid4(),
                            conversation_id=conversation_id,
                            role="assistant",
                            content=assistant_answer,
                            citations=citations,
                            ask_run_id=run_id,
                            created_at=now,
                        ),
                    ]
                )
                self.conversations[conversation_id] = conversation.model_copy(
                    update={"updated_at": now}
                )
            return run_id, trace_id

    def save_quiz_set(
        self, user: CurrentUser, project_id: UUID, run_id: UUID, quiz_set: QuizSet
    ) -> QuizSet:
        """Persist a Quiz aggregate and associate it with its source run."""
        with self._lock:
            self.quiz_sets[quiz_set.id] = quiz_set
            self.project_quiz_sets.setdefault(project_id, []).insert(0, quiz_set.id)
            return quiz_set

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
    ) -> tuple[UUID, UUID]:
        """Persist the run and Quiz aggregate under one in-memory lock boundary."""
        with self._lock:
            snapshot = (
                dict(self.run_sources),
                dict(self.traces),
                dict(self.quiz_sets),
                {key: list(value) for key, value in self.project_quiz_sets.items()},
            )
            try:
                run_id, trace_id = self.record_run(
                    user,
                    project_id,
                    message,
                    plan,
                    router_reason,
                    retrieved_chunks,
                    citations,
                    tool_calls,
                    validation_result,
                )
                self.save_quiz_set(user, project_id, run_id, quiz_set)
                return run_id, trace_id
            except Exception:
                (
                    self.run_sources,
                    self.traces,
                    self.quiz_sets,
                    self.project_quiz_sets,
                ) = snapshot
                raise

    def list_quiz_sets(self, user: CurrentUser, project_id: UUID) -> list[QuizSet] | None:
        """List Quiz aggregates belonging to an owned project."""
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            ids = self.project_quiz_sets.get(project_id, [])
            return [self.quiz_sets[quiz_id] for quiz_id in ids if quiz_id in self.quiz_sets]
