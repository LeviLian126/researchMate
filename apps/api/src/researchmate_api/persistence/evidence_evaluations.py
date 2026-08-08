"""Evaluation-run creation and score-projection persistence operations."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from researchmate_api.persistence.evidence_base import _json
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    EvaluationRunAccepted,
    EvaluationRunCreate,
    EvaluationRunRecord,
)
from researchmate_api.services.evidence_store import EvidenceStoreError, evidence_fingerprint

DEFAULT_EVALUATION_BUDGET_USD = Decimal("1.000000")


class PostgresEvidenceEvaluationMixin:
    """Evaluation-run creation and score-projection persistence operations."""

    if TYPE_CHECKING:
        # Provided by PostgresEvidenceRepositoryBase composed in PostgresEvidenceRepository.
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]
        _lock_active_project: Callable[[Connection, UUID, UUID], bool]
        _lock_idempotency: Callable[[Connection, UUID, str], None]
        _append_outbox: Callable[..., None]

    def create_evaluation_run(
        self, user: CurrentUser, payload: EvaluationRunCreate, idempotency_key: str
    ) -> EvaluationRunAccepted:
        """Create an idempotent evaluation run for an authorized frozen dataset."""
        request_hash = evidence_fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = (
                connection.execute(
                    text(
                        """
                    select id, summary, budget_limit_usd from evaluation_runs
                    where user_id = :user_id and idempotency_key = :key for update
                    """
                    ),
                    {"user_id": user.id, "key": idempotency_key},
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                summary = existing["summary"] or {}
                if summary.get("request_hash") != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return EvaluationRunAccepted(
                    evaluation_run_id=existing["id"],
                    case_count=int(summary.get("case_count", 0)),
                    status_url=f"/api/v1/evaluation-runs/{existing['id']}",
                    estimated_budget_boundary=existing["budget_limit_usd"],
                )
            valid = (
                connection.execute(
                    text(
                        """
                    select d.project_id, d.user_id as dataset_user_id,
                      count(c.id) as case_count
                    from evaluation_datasets d
                    left join projects p on p.id = d.project_id
                    join pipeline_versions v on v.id = :pipeline_id and v.status = 'accepted'
                    left join evaluation_cases c on c.dataset_id = d.id
                    where d.id = :dataset_id and d.status = 'frozen'
                      and (
                        d.project_id is null
                        or (p.status = 'active' and p.deleted_at is null)
                      )
                      and (d.user_id = :user_id or :privileged)
                    group by d.project_id, d.user_id
                    """
                    ),
                    {
                        "dataset_id": payload.dataset_id,
                        "pipeline_id": payload.pipeline_version_id,
                        "user_id": user.id,
                        "privileged": user.role in {"developer", "admin"},
                    },
                )
                .mappings()
                .one_or_none()
            )
            if valid is None:
                raise EvidenceStoreError("DATASET_NOT_FROZEN")
            if valid["project_id"] is not None and not self._lock_active_project(
                connection, valid["dataset_user_id"], valid["project_id"]
            ):
                raise EvidenceStoreError("PROJECT_NOT_FOUND", status_code=404)
            run_id = uuid4()
            budget_limit = payload.max_cost_usd or DEFAULT_EVALUATION_BUDGET_USD
            summary = {
                "request_hash": request_hash,
                "case_count": int(valid["case_count"]),
                "metrics": payload.metrics,
                "max_parallelism": payload.max_parallelism,
                "max_cost_usd": str(budget_limit),
                "labels": payload.labels,
            }
            connection.execute(
                text(
                    """
                    insert into evaluation_runs (
                      id,user_id,project_id,dataset_id,pipeline_version_id,status,
                      idempotency_key,summary,budget_limit_usd
                    ) values (
                      :id,:user_id,:project_id,:dataset_id,:pipeline_id,'pending',:key,
                      cast(:summary as jsonb),:budget_limit
                    )
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": valid["project_id"],
                    "dataset_id": payload.dataset_id,
                    "pipeline_id": payload.pipeline_version_id,
                    "key": idempotency_key,
                    "summary": _json(summary),
                    "budget_limit": budget_limit,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="evaluation_run",
                aggregate_id=run_id,
                event_type="evaluation.run.requested",
                payload={"evaluation_run_id": str(run_id), "user_id": str(user.id)},
                idempotency_key=f"evaluation:{run_id}:start:v1",
            )
            return EvaluationRunAccepted(
                evaluation_run_id=run_id,
                case_count=int(valid["case_count"]),
                status_url=f"/api/v1/evaluation-runs/{run_id}",
                estimated_budget_boundary=budget_limit,
            )

    def get_evaluation_run(
        self, user: CurrentUser, evaluation_run_id: UUID
    ) -> EvaluationRunRecord | None:
        """Read an authorized evaluation run, scores, and computed progress."""
        privileged = user.role in {"developer", "admin"}
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id,dataset_id,pipeline_version_id,status,summary,created_at,
                      started_at,completed_at
                    from evaluation_runs
                    where id = :id and (user_id = :user_id or :privileged)
                    """
                    ),
                    {"id": evaluation_run_id, "user_id": user.id, "privileged": privileged},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            scores = (
                connection.execute(
                    text(
                        """
                    select case_id,metric_name,metric_version,value,passed,details,judge_model
                    from evaluation_scores where evaluation_run_id = :id
                    order by case_id,metric_name,metric_version
                    """
                    ),
                    {"id": evaluation_run_id},
                )
                .mappings()
                .all()
            )
            total_cases = connection.execute(
                text("select count(*) from evaluation_cases where dataset_id = :id"),
                {"id": row["dataset_id"]},
            ).scalar_one()
            scored_cases = connection.execute(
                text(
                    "select count(distinct case_id) from evaluation_scores where evaluation_run_id = :id"
                ),
                {"id": evaluation_run_id},
            ).scalar_one()
        progress = (
            100
            if row["status"] in {"succeeded", "failed", "cancelled"}
            else (int(scored_cases * 100 / total_cases) if total_cases else 0)
        )
        return EvaluationRunRecord(
            evaluation_run_id=row["id"],
            dataset_id=row["dataset_id"],
            pipeline_version_id=row["pipeline_version_id"],
            status=row["status"],
            progress=progress,
            summary=row["summary"],
            scores=[dict(score) for score in scores],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
