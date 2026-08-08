"""Owner-scoped workflow-run and human-review persistence operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from researchmate_api.persistence.evidence_base import _json, _progress
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    HumanDecisionAccepted,
    HumanDecisionCreate,
    ResearchRunAccepted,
    ResearchRunCreate,
    RunEventRecord,
    WorkflowRunRecord,
)
from researchmate_api.services.evidence_store import EvidenceStoreError, evidence_fingerprint


class PostgresEvidenceRunMixin:
    """Owner-scoped workflow-run and human-review persistence operations."""

    if TYPE_CHECKING:
        # Provided by PostgresEvidenceRepositoryBase composed in PostgresEvidenceRepository.
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]
        _lock_active_project: Callable[[Connection, UUID, UUID], bool]
        _lock_idempotency: Callable[[Connection, UUID, str], None]
        _append_event: Callable[..., None]
        _append_outbox: Callable[..., None]

    def create_research_run(
        self, user: CurrentUser, payload: ResearchRunCreate, idempotency_key: str
    ) -> ResearchRunAccepted:
        """Create one owner-scoped evidence workflow and enqueue it atomically."""
        request_hash = evidence_fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = (
                connection.execute(
                    text(
                        """
                    select id, input, created_at from workflow_runs
                    where user_id = :user_id and idempotency_key = :idempotency_key
                    for update
                    """
                    ),
                    {"user_id": user.id, "idempotency_key": idempotency_key},
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if existing["input"].get("request_hash") != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return self._accepted_run(existing["id"], existing["created_at"])
            if not self._lock_active_project(connection, user.id, payload.project_id):
                raise EvidenceStoreError("PROJECT_NOT_FOUND", status_code=404)
            allowed = connection.execute(
                text(
                    """
                    select 1 from projects p join pipeline_versions v on v.id = :pipeline_id
                    where p.id = :project_id and p.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                      and v.status = 'accepted'
                    """
                ),
                {
                    "project_id": payload.project_id,
                    "user_id": user.id,
                    "pipeline_id": payload.pipeline_version_id,
                },
            ).one_or_none()
            if allowed is None:
                raise EvidenceStoreError("PIPELINE_NOT_ACCEPTED")
            selected_document_ids = list(payload.source_scope.document_ids)
            if selected_document_ids:
                ready_count = connection.execute(
                    text(
                        """
                        select count(*) from documents
                        where id=any(:document_ids) and user_id=:user_id
                          and project_id=:project_id and status='ready' and deleted_at is null
                        """
                    ),
                    {
                        "document_ids": selected_document_ids,
                        "user_id": user.id,
                        "project_id": payload.project_id,
                    },
                ).scalar_one()
                if ready_count != len(selected_document_ids):
                    raise EvidenceStoreError("SOURCE_DOCUMENT_NOT_READY")
            elif not payload.source_scope.allow_web:
                has_ready_document = connection.execute(
                    text(
                        """
                        select 1 from documents
                        where user_id=:user_id and project_id=:project_id
                          and status='ready' and deleted_at is null limit 1
                        """
                    ),
                    {"user_id": user.id, "project_id": payload.project_id},
                ).one_or_none()
                if has_ready_document is None:
                    raise EvidenceStoreError("SOURCE_SCOPE_EMPTY")
            run_id, created_at = uuid4(), datetime.now(UTC)
            run_input = {**payload.model_dump(mode="json"), "request_hash": request_hash}
            connection.execute(
                text(
                    """
                    insert into workflow_runs (
                      id, user_id, project_id, pipeline_version_id, kind, status,
                      idempotency_key, checkpoint_ref, input, budget_limit_usd, created_at
                    ) values (
                      :id, :user_id, :project_id, :pipeline_id, 'evidence_review', 'pending',
                      :idempotency_key, :checkpoint_ref, cast(:input as jsonb), :budget_limit, :created_at
                    )
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": payload.project_id,
                    "pipeline_id": payload.pipeline_version_id,
                    "idempotency_key": idempotency_key,
                    "checkpoint_ref": str(run_id),
                    "input": _json(run_input),
                    "budget_limit": payload.max_cost_usd or Decimal("1.000000"),
                    "created_at": created_at,
                },
            )
            self._append_event(
                connection,
                run_id,
                node_key="workflow",
                event_type="run_status_changed",
                status="pending",
                safe_payload={"status": "pending", "progress": 0},
            )
            self._append_outbox(
                connection,
                aggregate_type="workflow_run",
                aggregate_id=run_id,
                event_type="workflow.run.requested",
                payload={"run_id": str(run_id), "user_id": str(user.id)},
                idempotency_key=f"workflow:{run_id}:start:v1",
            )
            return self._accepted_run(run_id, created_at)

    @staticmethod
    def _accepted_run(run_id: UUID, created_at: datetime) -> ResearchRunAccepted:
        """Map a durable workflow identity to the accepted-run API contract."""
        return ResearchRunAccepted(
            run_id=run_id,
            status_url=f"/api/v1/runs/{run_id}",
            events_url=f"/api/v1/runs/{run_id}/events",
            created_at=created_at,
        )

    def get_run(self, user: CurrentUser, run_id: UUID) -> WorkflowRunRecord | None:
        """Read one owner-scoped workflow with its latest safe progress event."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select r.id, r.project_id, r.pipeline_version_id, r.kind, r.status,
                      r.output, r.error_code, r.created_at, r.started_at, r.completed_at,
                      e.node_key as current_node, e.safe_payload
                    from workflow_runs r
                    left join lateral (
                      select node_key, safe_payload from run_events
                      where run_id = r.id order by sequence desc limit 1
                    ) e on true
                    where r.id = :run_id and r.user_id = :user_id
                    """
                    ),
                    {"run_id": run_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return WorkflowRunRecord(
            run_id=row["id"],
            project_id=row["project_id"],
            pipeline_version_id=row["pipeline_version_id"],
            kind=row["kind"],
            status=row["status"],
            progress=_progress(row["status"], row["safe_payload"]),
            current_node=row["current_node"],
            review_required=row["status"] == "waiting_human",
            output=row["output"],
            error_code=row["error_code"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def list_run_events(
        self, user: CurrentUser, run_id: UUID, after_sequence: int
    ) -> list[RunEventRecord] | None:
        """List a bounded, ordered event page after an owned workflow cursor."""
        with self._transaction(user) as connection:
            owned = connection.execute(
                text("select 1 from workflow_runs where id = :id and user_id = :user_id"),
                {"id": run_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = (
                connection.execute(
                    text(
                        """
                    select id as event_id, sequence, node_key, event_type, attempt, status,
                      safe_payload, latency_ms, created_at
                    from run_events where run_id = :run_id and sequence > :after_sequence
                    order by sequence limit 500
                    """
                    ),
                    {"run_id": run_id, "after_sequence": after_sequence},
                )
                .mappings()
                .all()
            )
        return [RunEventRecord.model_validate(dict(row)) for row in rows]

    def create_decision(
        self,
        user: CurrentUser,
        run_id: UUID,
        payload: HumanDecisionCreate,
        idempotency_key: str,
    ) -> HumanDecisionAccepted | None:
        """Resolve one human-review interrupt and enqueue resume in one transaction."""
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            run = (
                connection.execute(
                    text(
                        """
                    select wr.id, wr.status from workflow_runs wr
                    join projects p on p.id = wr.project_id and p.user_id = wr.user_id
                    where wr.id = :id and wr.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    for update of wr, p
                    """
                    ),
                    {"id": run_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if run is None:
                return None
            existing = (
                connection.execute(
                    text(
                        """
                    select id, decision, final_payload from human_decisions
                    where run_id = :run_id and interrupt_key = :interrupt_key
                    """
                    ),
                    {"run_id": run_id, "interrupt_key": payload.interrupt_key},
                )
                .mappings()
                .one_or_none()
            )
            final_payload = payload.edited_payload if payload.decision == "edit" else None
            if existing is not None:
                if (
                    existing["decision"] != payload.decision
                    or existing["final_payload"] != final_payload
                ):
                    raise EvidenceStoreError("INTERRUPT_ALREADY_RESOLVED")
                return self._accepted_decision(existing["id"], run_id)
            if run["status"] != "waiting_human":
                raise EvidenceStoreError("RUN_NOT_WAITING")
            proposed = (
                connection.execute(
                    text(
                        """
                    select id, safe_payload from run_events
                    where run_id = :run_id and event_type = 'human_requested'
                      and safe_payload ->> 'interrupt_key' = :interrupt_key
                    order by sequence desc limit 1
                    """
                    ),
                    {"run_id": run_id, "interrupt_key": payload.interrupt_key},
                )
                .mappings()
                .one_or_none()
            )
            if proposed is None:
                raise EvidenceStoreError("INTERRUPT_NOT_FOUND")
            decision_id = uuid4()
            connection.execute(
                text(
                    """
                    insert into human_decisions (
                      id, run_id, event_id, user_id, interrupt_key, decision,
                      proposed_payload, final_payload, reason
                    ) values (
                      :id, :run_id, :event_id, :user_id, :interrupt_key, :decision,
                      cast(:proposed as jsonb), cast(:final as jsonb), :reason
                    )
                    """
                ),
                {
                    "id": decision_id,
                    "run_id": run_id,
                    "event_id": proposed["id"],
                    "user_id": user.id,
                    "interrupt_key": payload.interrupt_key,
                    "decision": payload.decision,
                    "proposed": _json(proposed["safe_payload"]),
                    "final": _json(final_payload) if final_payload is not None else None,
                    "reason": payload.reason,
                },
            )
            connection.execute(
                text("update workflow_runs set status = 'pending' where id = :id"),
                {"id": run_id},
            )
            self._append_event(
                connection,
                run_id,
                node_key="human_review",
                event_type="human_resolved",
                status="succeeded",
                safe_payload={
                    "interrupt_key": payload.interrupt_key,
                    "decision": payload.decision,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="workflow_run",
                aggregate_id=run_id,
                event_type="workflow.resume.requested",
                payload={
                    "run_id": str(run_id),
                    "user_id": str(user.id),
                    "decision_id": str(decision_id),
                },
                idempotency_key=f"workflow:{run_id}:decision:{idempotency_key}",
            )
            return self._accepted_decision(decision_id, run_id)

    @staticmethod
    def _accepted_decision(decision_id: UUID, run_id: UUID) -> HumanDecisionAccepted:
        """Map a durable human decision to the accepted-decision API contract."""
        return HumanDecisionAccepted(
            decision_id=decision_id,
            run_id=run_id,
            resume_status_url=f"/api/v1/runs/{run_id}",
        )
