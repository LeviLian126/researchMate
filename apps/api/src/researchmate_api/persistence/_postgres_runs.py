"""Own persisted run sources and developer execution traces."""

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


class RunPersistenceMixin:
    """Own persisted run sources and developer execution traces."""

    def get_run_sources(
        self, user: CurrentUser, run_id: UUID
    ) -> RunSourcesResponse | None:
        """Return the citation panel for an authorized run."""
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
        """Return a developer trace when the caller is authorized."""
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
        """Persist one execution run, its sources, trace, and optional conversation messages."""
        run_id, trace_id = uuid4(), uuid4()
        passed = bool(validation_result.get("passed", False))
        total_latency_ms = int((runtime_metadata or {}).get("total_latency_ms", 0))
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
            latency_ms=total_latency_ms,
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
                           'succeeded', :validation_status, :latency_ms, cast(:token_usage as jsonb)
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
                    "latency_ms": total_latency_ms,
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
