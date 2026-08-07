"""Aggregate evaluation metrics into a stable regression summary payload."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from researchmate_worker.evaluation_models import EvaluationRuntimeError

SUPPORTED_METRICS = {"schema_valid", "citation_precision", "evidence_recall", "faithfulness"}


def _safe_evaluation_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, EvaluationRuntimeError):
        return exc.code, exc.retryable
    code = getattr(exc, "code", None)
    # Use explicit retryable attribute; default to non-retryable rather than
    # string-matching exception class names which silently misclassifies errors.
    retryable = bool(getattr(exc, "retryable", False))
    safe_code = (
        code
        if isinstance(code, str) and code
        else ("EVALUATION_PROVIDER_TEMPORARY" if retryable else "EVALUATION_CASE_FAILED")
    )
    return safe_code[:120], retryable


def _metric_aggregates(connection: Any, run_id: UUID) -> dict[str, dict[str, float | int]]:
    rows = (
        connection.execute(
            text(
                """
            select metric_name,count(*) as score_count,
              avg(value) filter (where value is not null) as mean_value,
              count(*) filter (where passed=true) as passed_count,
              count(*) filter (where passed=false) as failed_count
            from evaluation_scores
            where evaluation_run_id=:id and metric_name<>'case_execution'
            group by metric_name order by metric_name
            """
            ),
            {"id": run_id},
        )
        .mappings()
        .all()
    )
    return {
        row["metric_name"]: {
            "score_count": int(row["score_count"]),
            "mean_value": float(row["mean_value"]) if row["mean_value"] is not None else 0.0,
            "pass_rate": (
                int(row["passed_count"])
                / max(1, int(row["passed_count"]) + int(row["failed_count"]))
            ),
            "failed_count": int(row["failed_count"]),
        }
        for row in rows
    }


def build_regression_summary(
    current: dict[str, dict[str, float | int]],
    baseline: dict[str, dict[str, float | int]],
    *,
    total_cases: int,
    execution_failures: int,
    baseline_run_id: UUID | None,
    budget_limit_usd: Decimal | None,
    budget_reserved_usd: Decimal,
) -> dict[str, Any]:
    """Compare current metrics with a baseline and summarize release regression risk."""
    comparisons: dict[str, dict[str, float]] = {}
    regressed_metrics: list[str] = []
    for metric, values in current.items():
        prior = baseline.get(metric)
        if prior is None:
            continue
        mean_delta = float(values["mean_value"]) - float(prior["mean_value"])
        pass_rate_delta = float(values["pass_rate"]) - float(prior["pass_rate"])
        comparisons[metric] = {
            "mean_delta": round(mean_delta, 6),
            "pass_rate_delta": round(pass_rate_delta, 6),
        }
        if mean_delta < -0.02 or pass_rate_delta < -0.05:
            regressed_metrics.append(metric)
    quality_failures = sum(int(values["failed_count"]) for values in current.values())
    return {
        "completed_cases": total_cases - execution_failures,
        "failed_cases": execution_failures,
        "complete": True,
        "execution_succeeded": execution_failures == 0,
        "quality_passed": quality_failures == 0 and execution_failures == 0,
        "metric_summary": current,
        "baseline_run_id": str(baseline_run_id) if baseline_run_id else None,
        "baseline_comparison": comparisons,
        "regression_detected": bool(regressed_metrics),
        "regressed_metrics": sorted(regressed_metrics),
        "budget_limit_usd": str(budget_limit_usd) if budget_limit_usd is not None else None,
        "budget_reserved_usd": str(budget_reserved_usd),
    }


def json_dumps(value: object) -> str:
    """Serialize metric details in the compact form expected by SQL writes."""
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
