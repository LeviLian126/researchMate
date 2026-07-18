from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection


SCENARIO_BOUNDARIES = {
    "llm_timeout": "chat_provider_timeout_boundary",
    "qdrant_unavailable": "vector_projection_unavailable_boundary",
    "worker_interrupt": "lease_recovery_boundary",
    "r2_failure": "object_storage_failure_boundary",
}


@dataclass(frozen=True)
class ClaimedFaultExercise:
    id: UUID
    scenario: str
    target_run_id: UUID | None
    attempts: int


class FaultSimulationService:
    """Records a bounded failure/recovery exercise without mutating any provider.

    This intentionally validates control-plane wiring and audit persistence only. It
    never delays a worker, changes a workflow run, or calls an external service.
    """

    def __init__(self, engine: Engine, *, lease_seconds: int = 120, max_attempts: int = 3) -> None:
        self.engine = engine
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def run(self, exercise_id: UUID, *, worker_id: str) -> str:
        # The simulation has no remote side effect, so claim, snapshot, and completion
        # can be one short transaction. A database failure rolls the claim back and the
        # task remains safely replayable.
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    update fault_exercises set status='running',attempts=attempts+1,
                      lease_owner=:worker_id,
                      lease_expires_at=now()+make_interval(secs=>:lease_seconds),
                      started_at=coalesce(started_at,now()),last_error_code=null
                    where id=:id and (
                      status='pending' or (status='running' and lease_expires_at<now())
                    ) and attempts<:max_attempts
                    returning id,scenario,target_run_id,attempts
                    """
                ),
                {
                    "id": exercise_id,
                    "worker_id": worker_id,
                    "lease_seconds": self.lease_seconds,
                    "max_attempts": self.max_attempts,
                },
            ).mappings().one_or_none()
            if row is None:
                return "not_claimed"
            exercise = ClaimedFaultExercise(**dict(row))
            boundary = SCENARIO_BOUNDARIES.get(exercise.scenario)
            if boundary is None:
                self._finish(
                    connection,
                    exercise.id,
                    worker_id,
                    status="failed",
                    result={"simulation_only": True, "external_calls": 0},
                    error_code="FAULT_SCENARIO_UNSUPPORTED",
                )
                return "failed"
            target_snapshot = self._target_snapshot(connection, exercise.target_run_id)
            self._finish(
                connection,
                exercise.id,
                worker_id,
                status="succeeded",
                result={
                    "simulation_only": True,
                    "external_calls": 0,
                    "injected_boundary": boundary,
                    "simulated_transition": "failure_observed_then_recovered",
                    "recovery_state": "runtime_unchanged",
                    "target_snapshot": target_snapshot,
                },
            )
            return "succeeded"

    @staticmethod
    def _target_snapshot(
        connection: Connection, target_run_id: UUID | None
    ) -> dict[str, Any] | None:
        if target_run_id is None:
            return None
        row = connection.execute(
            text(
                """
                select id,status,error_code from workflow_runs where id=:id
                """
            ),
            {"id": target_run_id},
        ).mappings().one_or_none()
        if row is None:
            return {"run_id": str(target_run_id), "status": "not_found"}
        return {
            "run_id": str(row["id"]),
            "status": row["status"],
            "error_code": row["error_code"],
        }

    @staticmethod
    def _finish(
        connection: Connection,
        exercise_id: UUID,
        worker_id: str,
        *,
        status: str,
        result: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        connection.execute(
            text(
                """
                update fault_exercises set status=:status,safe_result=cast(:result as jsonb),
                  last_error_code=:error_code,completed_at=now(),lease_owner=null,
                  lease_expires_at=null
                where id=:id and lease_owner=:worker_id and status='running'
                """
            ),
            {
                "id": exercise_id,
                "worker_id": worker_id,
                "status": status,
                "result": _json(result),
                "error_code": error_code,
            },
        )


def _json(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
