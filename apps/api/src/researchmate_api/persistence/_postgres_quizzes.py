"""Own Quiz aggregate persistence and atomic Quiz run recording."""

# ruff: noqa: F401
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from researchmate_api.persistence._postgres_core import _enum_value, _json, _safe_filename
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
from researchmate_api.services.store import ChunkEntry, IdempotencyDecision

UploadUrlFactory = Callable[[UUID, str, UploadUrlRequest], str]
ObjectMetadataReader = Callable[[str], StoredObjectMetadata]


class QuizPersistenceMixin:
    """Own Quiz aggregate persistence and atomic Quiz run recording."""

    def save_quiz_set(
        self, user: CurrentUser, project_id: UUID, run_id: UUID, quiz_set: QuizSet
    ) -> QuizSet:
        """Persist a Quiz aggregate and associate it with its source run."""
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
        """Persist the trace/run and Quiz aggregate in one database transaction."""
        with self._transaction(user):
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

    def list_quiz_sets(
        self, user: CurrentUser, project_id: UUID
    ) -> list[QuizSet] | None:
        """List Quiz aggregates belonging to an owned project."""
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
