"""Privileged reliability and fault-exercise persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    FaultScenarioAccepted,
    FaultScenarioCreate,
    FaultScenarioRecord,
    ReliabilityResponse,
)
from researchmate_api.services.evidence_store import EvidenceStoreError, evidence_fingerprint


class PostgresEvidenceOperationsMixin:
    """Privileged reliability and fault-exercise persistence operations."""

    def reliability(self, user: CurrentUser, window_hours: int) -> ReliabilityResponse:
        """Aggregate the bounded reliability window for a privileged operator."""
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        with self._transaction(user) as connection:
            aggregate = (
                connection.execute(
                    text(
                        """
                    select count(distinct r.id) as run_count,
                      count(distinct r.id) filter (where r.status = 'succeeded') as succeeded,
                      count(distinct r.id) filter (where r.status = 'failed') as failed,
                      count(*) filter (where e.event_type = 'retry_scheduled') as retries,
                      percentile_cont(0.5) within group (order by e.latency_ms)
                        filter (where e.latency_ms is not null) as p50,
                      percentile_cont(0.95) within group (order by e.latency_ms)
                        filter (where e.latency_ms is not null) as p95,
                      coalesce(sum(e.input_tokens),0) as input_tokens,
                      coalesce(sum(e.output_tokens),0) as output_tokens,
                      coalesce(sum(e.cost_usd),0) as cost_usd
                    from workflow_runs r left join run_events e on e.run_id = r.id
                    where r.created_at >= now() - make_interval(hours => :hours)
                    """
                    ),
                    {"hours": window_hours},
                )
                .mappings()
                .one()
            )
            trace_ids = (
                connection.execute(
                    text(
                        """
                    select id from workflow_runs
                    where created_at >= now() - make_interval(hours => :hours)
                    order by created_at desc limit 10
                    """
                    ),
                    {"hours": window_hours},
                )
                .scalars()
                .all()
            )
        terminal = int(aggregate["succeeded"]) + int(aggregate["failed"])
        denominator = max(1, terminal)
        return ReliabilityResponse(
            window_hours=window_hours,
            run_count=int(aggregate["run_count"]),
            success_rate=int(aggregate["succeeded"]) / denominator,
            error_rate=int(aggregate["failed"]) / denominator,
            retry_count=int(aggregate["retries"]),
            p50_latency_ms=int(aggregate["p50"]) if aggregate["p50"] is not None else None,
            p95_latency_ms=int(aggregate["p95"]) if aggregate["p95"] is not None else None,
            input_tokens=int(aggregate["input_tokens"]),
            output_tokens=int(aggregate["output_tokens"]),
            cost_usd=Decimal(aggregate["cost_usd"]),
            sample_trace_ids=list(trace_ids),
        )

    def create_fault_scenario(
        self, user: CurrentUser, payload: FaultScenarioCreate, idempotency_key: str
    ) -> FaultScenarioAccepted:
        """Schedule an idempotent, privileged fault exercise without external mutation."""
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        request_hash = evidence_fingerprint(payload)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=payload.duration_seconds)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = (
                connection.execute(
                    text(
                        """
                    select id,target_run_id,expires_at,request_hash from fault_exercises
                    where requested_by=:user_id and idempotency_key=:key for update
                    """
                    ),
                    {"user_id": user.id, "key": idempotency_key},
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return FaultScenarioAccepted(
                    exercise_id=existing["id"],
                    target_run_id=existing["target_run_id"],
                    expected_recovery_state="simulation_completed_without_external_mutation",
                    status_url=f"/api/v1/dev/fault-scenarios/{existing['id']}",
                    expires_at=existing["expires_at"],
                )
            if payload.target_run_id is not None:
                target_exists = connection.execute(
                    text("select 1 from workflow_runs where id=:id"),
                    {"id": payload.target_run_id},
                ).one_or_none()
                if target_exists is None:
                    raise EvidenceStoreError("RUN_NOT_FOUND", status_code=404)
            exercise_id = uuid4()
            connection.execute(
                text(
                    """
                    insert into fault_exercises (
                      id,requested_by,target_run_id,scenario,duration_seconds,status,
                      request_hash,idempotency_key,expires_at
                    ) values (
                      :id,:user_id,:target_run_id,:scenario,:duration_seconds,'pending',
                      :request_hash,:key,:expires_at
                    )
                    """
                ),
                {
                    "id": exercise_id,
                    "user_id": user.id,
                    "target_run_id": payload.target_run_id,
                    "scenario": payload.scenario,
                    "duration_seconds": payload.duration_seconds,
                    "request_hash": request_hash,
                    "key": idempotency_key,
                    "expires_at": expires_at,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="fault_exercise",
                aggregate_id=exercise_id,
                event_type="fault.exercise.requested",
                payload={
                    **payload.model_dump(mode="json"),
                    "exercise_id": str(exercise_id),
                    "requested_by": str(user.id),
                    "expires_at": expires_at.isoformat(),
                },
                idempotency_key=f"fault:{user.id}:{idempotency_key}",
            )
        return FaultScenarioAccepted(
            exercise_id=exercise_id,
            target_run_id=payload.target_run_id,
            expected_recovery_state="simulation_completed_without_external_mutation",
            status_url=f"/api/v1/dev/fault-scenarios/{exercise_id}",
            expires_at=expires_at,
        )

    def get_fault_scenario(
        self, user: CurrentUser, exercise_id: UUID
    ) -> FaultScenarioRecord | None:
        """Read a fault exercise owned by the privileged requesting operator."""
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id,scenario,target_run_id,status,attempts,expires_at,safe_result,
                      last_error_code,created_at,started_at,completed_at
                    from fault_exercises where id=:id and requested_by=:user_id
                    """
                    ),
                    {"id": exercise_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return FaultScenarioRecord(
            exercise_id=row["id"],
            scenario=row["scenario"],
            target_run_id=row["target_run_id"],
            status=row["status"],
            attempts=row["attempts"],
            expires_at=row["expires_at"],
            safe_result=row["safe_result"],
            error_code=row["last_error_code"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
