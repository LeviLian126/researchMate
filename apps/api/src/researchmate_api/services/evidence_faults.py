"""Provide shared fault-simulation persistence helpers for evidence repositories."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    FaultScenarioAccepted,
    FaultScenarioCreate,
    FaultScenarioRecord,
)


class EvidenceStoreError(RuntimeError):
    """Expose a stable evidence-store error code and HTTP mapping."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        """Capture the public error code and its intended HTTP status."""
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def evidence_fingerprint(payload: object) -> str:
    """Hash a normalized payload for deterministic idempotency comparisons."""
    value: Any = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


class FaultScenarioStoreMixin:
    """Add owner-scoped, idempotent local fault-simulation records to a repository."""

    def create_fault_scenario(
        self, user: CurrentUser, payload: FaultScenarioCreate, idempotency_key: str
    ) -> FaultScenarioAccepted:
        """Create or replay a bounded local fault simulation record."""
        fingerprint = evidence_fingerprint(payload)
        key = (user.id, idempotency_key)
        now = datetime.now(UTC)
        with self.lock:
            existing = self.idempotency.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return existing[1]  # type: ignore[return-value]
            exercise_id = uuid4()
            expires_at = now + timedelta(seconds=payload.duration_seconds)
            accepted = FaultScenarioAccepted(
                exercise_id=exercise_id,
                target_run_id=payload.target_run_id,
                expected_recovery_state="simulation_completed_without_external_mutation",
                status_url=f"/api/v1/dev/fault-scenarios/{exercise_id}",
                expires_at=expires_at,
            )
            self.faults[exercise_id] = (
                user.id,
                FaultScenarioRecord(
                    exercise_id=exercise_id,
                    scenario=payload.scenario,
                    target_run_id=payload.target_run_id,
                    status="pending",
                    attempts=0,
                    expires_at=expires_at,
                    created_at=now,
                ),
            )
            self.idempotency[key] = (fingerprint, accepted)
            return accepted

    def get_fault_scenario(
        self, user: CurrentUser, exercise_id: UUID
    ) -> FaultScenarioRecord | None:
        """Return a defensive copy of a caller-owned fault exercise."""
        with self.lock:
            value = self.faults.get(exercise_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None
