"""Own usage quotas and durable API idempotency reservations."""

# ruff: noqa: F401
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
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


class IdempotencyPersistenceMixin:
    """Own usage quotas and durable API idempotency reservations."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in PostgresResearchMateRepository.
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]

    def increment_usage(self, user: CurrentUser, kind: str, limit: int) -> bool:
        """Accept and count an execution attempt only while quota remains."""
        with self._transaction(user) as connection:
            accepted = connection.execute(
                text(
                    """
                    insert into api_usage (id, user_id, usage_date, kind, count)
                    select :id, :user_id, current_date, :kind, 1
                    where :limit > 0
                      and exists (select 1 from profiles where id = :user_id)
                    on conflict (user_id, usage_date, kind) do update
                    set count = api_usage.count + 1, updated_at = now()
                    where api_usage.user_id = :user_id
                      and api_usage.count < :limit
                    returning count
                    """
                ),
                {"id": uuid4(), "user_id": user.id, "kind": kind, "limit": limit},
            ).one_or_none()
        return accepted is not None

    def begin_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> IdempotencyDecision:
        """Reserve one user/operation/key tuple or return its durable replay state."""
        with self._transaction(user) as connection:
            inserted = connection.execute(
                text(
                    """
                    insert into api_idempotency (
                      user_id, operation, idempotency_key, request_hash, state
                    ) values (
                      :user_id, :operation, :key, :request_hash, 'pending'
                    )
                    on conflict (user_id, operation, idempotency_key) do nothing
                    returning state
                    """
                ),
                {
                    "user_id": user.id,
                    "operation": operation,
                    "key": key,
                    "request_hash": request_hash,
                },
            ).one_or_none()
            if inserted is not None:
                return IdempotencyDecision("execute")
            row = (
                connection.execute(
                    text(
                        """
                    select request_hash, state, response
                    from api_idempotency
                    where user_id=:user_id and operation=:operation
                      and idempotency_key=:key
                    """
                    ),
                    {"user_id": user.id, "operation": operation, "key": key},
                )
                .mappings()
                .one()
            )
        if row["request_hash"] != request_hash:
            return IdempotencyDecision("mismatch")
        if row["state"] == "succeeded":
            response = row["response"]
            if isinstance(response, str):
                response = json.loads(response)
            return IdempotencyDecision("replay", response)
        return IdempotencyDecision("in_progress")

    def complete_idempotent_operation(
        self,
        user: CurrentUser,
        operation: str,
        key: str,
        response: dict,
    ) -> None:
        """Atomically persist a successful response for a pending reservation."""
        with self._transaction(user) as connection:
            updated = connection.execute(
                text(
                    """
                    update api_idempotency
                    set state='succeeded', response=cast(:response as jsonb), updated_at=now()
                    where user_id=:user_id and operation=:operation
                      and idempotency_key=:key and state='pending'
                    """
                ),
                {
                    "user_id": user.id,
                    "operation": operation,
                    "key": key,
                    "response": _json(response),
                },
            )
            if not updated.rowcount:
                raise ValueError("idempotency reservation is not pending")

    def abandon_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> None:
        """Release only a matching pending reservation after a failed execution."""
        with self._transaction(user) as connection:
            connection.execute(
                text(
                    """
                    delete from api_idempotency
                    where user_id=:user_id and operation=:operation
                      and idempotency_key=:key and request_hash=:request_hash
                      and state='pending'
                    """
                ),
                {
                    "user_id": user.id,
                    "operation": operation,
                    "key": key,
                    "request_hash": request_hash,
                },
            )
