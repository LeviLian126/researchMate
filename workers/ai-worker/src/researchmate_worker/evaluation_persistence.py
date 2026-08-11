"""Own SQL transitions, budget reservations, and durable score writes for evaluation runs."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text

from researchmate_worker.evaluation_models import (
    ClaimedEvaluation,
    EvaluationCase,
    EvaluationRuntimeError,
    MetricScore,
    PipelineRuntimeConfig,
)
from researchmate_worker.evaluation_summary import (
    _metric_aggregates,
    build_regression_summary,
    json_dumps,
)

SUPPORTED_METRICS = {
    "schema_valid",
    "citation_precision",
    "evidence_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "faithfulness",
}


class EvaluationPersistenceMixin:
    """Provide lease-safe database operations to the evaluation runner."""

    if TYPE_CHECKING:
        # Provided by EvaluationRunner, the composing class in evaluation_runner.py.
        from sqlalchemy import Engine

        engine: Engine
        lease_seconds: int
        max_attempts: int
        case_budget_reservation_usd: Decimal

    def _claim(self, run_id: UUID, worker_id: str) -> ClaimedEvaluation | None:
        """Lease one pending evaluation run for a bounded worker attempt."""
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    update evaluation_runs r set status='running',attempts=r.attempts+1,
                      lease_owner=:worker_id,
                      lease_expires_at=now()+make_interval(secs=>:lease_seconds),
                      started_at=coalesce(started_at,now())
                    from pipeline_versions v
                    where r.id=:id and v.id=r.pipeline_version_id and v.status='accepted' and (
                      r.status='pending' or (r.status='running' and r.lease_expires_at<now())
                    ) and r.attempts<:max_attempts
                    returning r.id,r.user_id,r.project_id,r.dataset_id,r.summary,r.attempts,
                      r.budget_limit_usd,r.pipeline_version_id,v.code_sha,v.configuration
                    """
                    ),
                    {
                        "id": run_id,
                        "worker_id": worker_id,
                        "lease_seconds": self.lease_seconds,
                        "max_attempts": self.max_attempts,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        if row["project_id"] is None:
            raise EvaluationRuntimeError("EVALUATION_PROJECT_REQUIRED")
        summary = row["summary"] or {}
        metrics = list(summary.get("metrics", []))
        if not metrics or not set(metrics) <= SUPPORTED_METRICS:
            raise EvaluationRuntimeError("METRIC_UNSUPPORTED")
        return ClaimedEvaluation(
            id=row["id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            dataset_id=row["dataset_id"],
            metrics=metrics,
            max_parallelism=max(1, min(20, int(summary.get("max_parallelism", 4)))),
            attempts=row["attempts"],
            budget_limit_usd=(
                Decimal(row["budget_limit_usd"]) if row["budget_limit_usd"] is not None else None
            ),
            pipeline_version_id=row["pipeline_version_id"],
            pipeline_code_sha=row["code_sha"],
            pipeline=PipelineRuntimeConfig.model_validate(row["configuration"]),
        )

    def _load_cases(self, run_id: UUID) -> list[EvaluationCase]:
        """Load the frozen cases attached to an evaluation run."""
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select c.id,c.case_key,c.input,c.expected_output,c.expected_evidence
                    from evaluation_cases c join evaluation_runs r on r.dataset_id=c.dataset_id
                    where r.id=:id order by c.case_key
                    """
                    ),
                    {"id": run_id},
                )
                .mappings()
                .all()
            )
        return [EvaluationCase(**dict(row)) for row in rows]

    def _completed_case_ids(self, run_id: UUID, metrics: list[str]) -> set[UUID]:
        """Identify cases whose requested metrics are already durable."""
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select case_id from evaluation_scores
                    where evaluation_run_id=:run_id and metric_name=any(:metrics)
                    group by case_id
                    having count(distinct metric_name)=:metric_count
                      and bool_and(passed is not null)
                    """
                    ),
                    {"run_id": run_id, "metrics": metrics, "metric_count": len(metrics)},
                )
                .scalars()
                .all()
            )
        return set(rows)

    def _reserve_case_budget(self, run_id: UUID, worker_id: str) -> bool:
        """Atomically reserve the next case budget without crossing the cap."""
        with self.engine.begin() as connection:
            reserved = connection.execute(
                text(
                    """
                    update evaluation_runs
                    set budget_reserved_usd=budget_reserved_usd+:amount
                    where id=:id and status='running' and lease_owner=:worker_id
                      and lease_expires_at>now()
                      and (
                        budget_limit_usd is null
                        or budget_reserved_usd+:amount<=budget_limit_usd
                      )
                    returning budget_reserved_usd
                    """
                ),
                {
                    "id": run_id,
                    "worker_id": worker_id,
                    "amount": self.case_budget_reservation_usd,
                },
            ).one_or_none()
        return reserved is not None

    def _save_scores(
        self,
        run_id: UUID,
        case_id: UUID,
        scores: list[MetricScore],
        *,
        worker_id: str,
    ) -> None:
        """Persist one case result and its metric scores as a single unit."""
        with self.engine.begin() as connection:
            owns_lease = connection.execute(
                text(
                    """
                    select 1 from evaluation_runs
                    where id=:id and status='running' and lease_owner=:worker_id
                      and lease_expires_at>now()
                    """
                ),
                {"id": run_id, "worker_id": worker_id},
            ).one_or_none()
            if owns_lease is None:
                raise EvaluationRuntimeError("EVALUATION_LEASE_LOST", retryable=True)
            if all(score.name != "case_execution" for score in scores):
                connection.execute(
                    text(
                        """
                        delete from evaluation_scores
                        where evaluation_run_id=:run_id and case_id=:case_id
                          and metric_name='case_execution'
                        """
                    ),
                    {"run_id": run_id, "case_id": case_id},
                )
            for score in scores:
                connection.execute(
                    text(
                        """
                        insert into evaluation_scores (
                          evaluation_run_id,case_id,metric_name,metric_version,value,passed,
                          details,judge_model
                        ) values (
                          :run_id,:case_id,:name,:version,:value,:passed,cast(:details as jsonb),
                          :judge_model
                        ) on conflict (evaluation_run_id,case_id,metric_name,metric_version)
                        do update set value=excluded.value,passed=excluded.passed,
                          details=excluded.details,judge_model=excluded.judge_model
                        """
                    ),
                    {
                        "run_id": run_id,
                        "case_id": case_id,
                        "name": score.name,
                        "version": score.version,
                        "value": score.value,
                        "passed": score.passed,
                        "details": json_dumps(score.details),
                        "judge_model": score.judge_model,
                    },
                )

    def _complete(
        self,
        run: ClaimedEvaluation,
        worker_id: str,
        *,
        total: int,
        failures: int,
    ) -> str:
        """Finalize evaluation aggregates and release the worker lease."""
        with self.engine.begin() as connection:
            current = _metric_aggregates(connection, run.id)
            baseline_id = connection.execute(
                text(
                    """
                    select id from evaluation_runs
                    where dataset_id=:dataset_id and id<>:id and status='succeeded'
                    order by completed_at desc nulls last,created_at desc limit 1
                    """
                ),
                {"dataset_id": run.dataset_id, "id": run.id},
            ).scalar_one_or_none()
            baseline = _metric_aggregates(connection, baseline_id) if baseline_id else {}
            budget_reserved = connection.execute(
                text("select budget_reserved_usd from evaluation_runs where id=:id"),
                {"id": run.id},
            ).scalar_one()
            result = build_regression_summary(
                current,
                baseline,
                total_cases=total,
                execution_failures=failures,
                baseline_run_id=baseline_id,
                budget_limit_usd=run.budget_limit_usd,
                budget_reserved_usd=Decimal(budget_reserved),
                requested_metrics=run.metrics,
            )
            result["pipeline"] = run.pipeline.model_dump(mode="json")
            result["pipeline_code_sha"] = run.pipeline_code_sha
            if baseline_id is not None:
                baseline_config = connection.execute(
                    text(
                        """
                        select v.configuration from evaluation_runs r
                        join pipeline_versions v on v.id=r.pipeline_version_id
                        where r.id=:id
                        """
                    ),
                    {"id": baseline_id},
                ).scalar_one_or_none()
                result["baseline_pipeline"] = baseline_config
            status = "failed" if failures else "succeeded"
            updated = connection.execute(
                text(
                    """
                    update evaluation_runs set status=:status,completed_at=now(),
                      lease_owner=null,lease_expires_at=null,
                      last_error_code=:error_code,
                      summary=coalesce(summary,'{}'::jsonb) || cast(:result as jsonb)
                    where id=:id and lease_owner=:worker_id and status='running'
                      and lease_expires_at>now()
                    """
                ),
                {
                    "id": run.id,
                    "worker_id": worker_id,
                    "status": status,
                    "error_code": "EVALUATION_CASE_FAILURE" if failures else None,
                    "result": json_dumps(result),
                },
            )
            if not updated.rowcount:
                raise EvaluationRuntimeError("EVALUATION_LEASE_LOST", retryable=True)
        return status

    def _release_for_retry(self, run_id: UUID, worker_id: str, code: str) -> None:
        """Return a retryable evaluation to pending with a safe error code."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update evaluation_runs set status='pending',lease_owner=null,
                      lease_expires_at=null,last_error_code=:code,
                      summary=coalesce(summary,'{}'::jsonb) || cast(:retry as jsonb)
                    where id=:id and lease_owner=:worker_id and status='running'
                    """
                ),
                {
                    "id": run_id,
                    "worker_id": worker_id,
                    "code": code,
                    "retry": json_dumps({"last_retry_error": code}),
                },
            )

    def _terminal_failure(self, run_id: UUID, worker_id: str, code: str) -> None:
        """Mark an exhausted evaluation attempt as a terminal failure."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update evaluation_runs set status='failed',completed_at=now(),
                      lease_owner=null,lease_expires_at=null,last_error_code=:code,
                      summary=coalesce(summary,'{}'::jsonb) || cast(:failure as jsonb)
                    where id=:id and lease_owner=:worker_id and status='running'
                    """
                ),
                {
                    "id": run_id,
                    "worker_id": worker_id,
                    "code": code,
                    "failure": json_dumps({"complete": True, "error_code": code}),
                },
            )
