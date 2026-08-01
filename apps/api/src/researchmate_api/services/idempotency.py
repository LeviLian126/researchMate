"""Coordinate replay-safe cost-bearing operations through repository-backed decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.services.store import ResearchMateRepository


class IdempotencyError(RuntimeError):
    """Describe key reuse conflicts and concurrent executions."""

    def __init__(self, code: str, message: str) -> None:
        """Record the stable conflict code and safe explanation."""
        super().__init__(message)
        self.code = code
        self.message = message


def request_hash(payload: BaseModel) -> str:
    """Hash the canonical JSON request body for key/body consistency checks."""
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyCoordinator:
    """Start, replay, complete, or abandon one durable idempotent operation."""

    def __init__(
        self,
        repository: ResearchMateRepository,
        user: CurrentUser,
        operation: str,
        key: str | None,
        payload: BaseModel,
    ) -> None:
        """Bind the operation identity and canonical request hash."""
        self.repository = repository
        self.user = user
        self.operation = operation
        self.key = key
        self.payload_hash = request_hash(payload)
        self.started = False

    def begin(self) -> dict[str, Any] | None:
        """Return a saved response or reserve this key for the sole executor."""
        if self.key is None:
            return None
        decision = self.repository.begin_idempotent_operation(
            self.user, self.operation, self.key, self.payload_hash
        )
        if decision.state == "execute":
            self.started = True
            return None
        if decision.state == "replay":
            return decision.response
        if decision.state == "mismatch":
            raise IdempotencyError(
                "IDEMPOTENCY_KEY_REUSED",
                "The Idempotency-Key was already used with a different request body.",
            )
        raise IdempotencyError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "An identical request with this Idempotency-Key is still in progress.",
        )

    def complete(self, response: BaseModel) -> None:
        """Persist the successful response snapshot for future replays."""
        if self.key is None or not self.started:
            return
        self.repository.complete_idempotent_operation(
            self.user,
            self.operation,
            self.key,
            response.model_dump(mode="json"),
        )
        self.started = False

    def abandon(self) -> None:
        """Release a failed reservation so a safe retry can execute again."""
        if self.key is None or not self.started:
            return
        self.repository.abandon_idempotent_operation(
            self.user, self.operation, self.key, self.payload_hash
        )
        self.started = False
