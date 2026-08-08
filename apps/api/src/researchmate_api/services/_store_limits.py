"""Own in-memory usage limits and API idempotency reservations."""

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


class LimitStoreMixin:
    """Own in-memory usage limits and API idempotency reservations."""

    if TYPE_CHECKING:
        # Provided by InMemoryStoreCore composed in InMemoryResearchMateStore.
        _lock: RLock
        # Opaque idempotency record payloads stored at the API boundary.
        api_usage: dict[tuple[UUID, str, str], int]
        idempotency_records: dict[tuple[UUID, str, str], dict[str, Any]]

    def increment_usage(self, user: CurrentUser, kind: str, limit: int) -> bool:
        """Accept and count an execution attempt only while quota remains."""
        with self._lock:
            today = datetime.now(UTC).date().isoformat()
            key = (user.id, today, kind)
            current = self.api_usage.get(key, 0)
            if current >= limit:
                return False
            self.api_usage[key] = current + 1
            return True

    def begin_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> IdempotencyDecision:
        """Atomically reserve a key or return its existing replay decision."""
        with self._lock:
            record_key = (user.id, operation, key)
            record = self.idempotency_records.get(record_key)
            if record is None:
                self.idempotency_records[record_key] = {
                    "request_hash": request_hash,
                    "state": "pending",
                    "response": None,
                }
                return IdempotencyDecision("execute")
            if record["request_hash"] != request_hash:
                return IdempotencyDecision("mismatch")
            if record["state"] == "succeeded":
                return IdempotencyDecision("replay", record["response"])
            return IdempotencyDecision("in_progress")

    def complete_idempotent_operation(
        self,
        user: CurrentUser,
        operation: str,
        key: str,
        response: dict[str, Any],
    ) -> None:
        """Save a successful response only for the matching pending reservation."""
        with self._lock:
            record = self.idempotency_records.get((user.id, operation, key))
            if record is None or record["state"] != "pending":
                raise ValueError("idempotency reservation is not pending")
            record.update(state="succeeded", response=response)

    def abandon_idempotent_operation(
        self, user: CurrentUser, operation: str, key: str, request_hash: str
    ) -> None:
        """Remove only the caller's matching pending reservation after failure."""
        with self._lock:
            record_key = (user.id, operation, key)
            record = self.idempotency_records.get(record_key)
            if (
                record is not None
                and record["state"] == "pending"
                and record["request_hash"] == request_hash
            ):
                del self.idempotency_records[record_key]
