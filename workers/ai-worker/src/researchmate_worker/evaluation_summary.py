"""Aggregate evaluation metrics into a stable regression summary payload."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from researchmate_worker.evaluation_models import EvaluationRuntimeError

SUPPORTED_METRICS = {
    "schema_valid",
    "citation_precision",
    "evidence_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "faithfulness",
}


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


MetricAggregate = dict[str, float | int | None]


def _metric_aggregates(connection: Any, run_id: UUID) -> dict[str, MetricAggregate]:
    rows = (
        connection.execute(
            text(
                """
            select metric_name,count(*) as score_count,
              count(*) filter (where value is not null or passed is not null) as judged_count,
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
            "judged_count": int(row.get("judged_count", row["score_count"])),
            "mean_value": float(row["mean_value"]) if row["mean_value"] is not None else None,
            "pass_rate": (
                int(row["passed_count"])
                / max(1, int(row["passed_count"]) + int(row["failed_count"]))
            ),
            "failed_count": int(row["failed_count"]),
        }
        for row in rows
    }


def build_regression_summary(
    current: dict[str, MetricAggregate],
    baseline: dict[str, MetricAggregate],
    *,
    total_cases: int,
    execution_failures: int,
    baseline_run_id: UUID | None,
    budget_limit_usd: Decimal | None,
    budget_reserved_usd: Decimal,
    requested_metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Compare current metrics with a baseline and summarize release regression risk."""
    comparisons: dict[str, dict[str, float]] = {}
    regressed_metrics: list[str] = []
    for metric, values in current.items():
        prior = baseline.get(metric)
        current_mean = values["mean_value"]
        prior_mean = prior["mean_value"] if prior is not None else None
        current_pass_rate = values["pass_rate"]
        prior_pass_rate = prior["pass_rate"] if prior is not None else None
        if (
            prior is None
            or not isinstance(current_mean, int | float)
            or not isinstance(prior_mean, int | float)
            or not isinstance(current_pass_rate, int | float)
            or not isinstance(prior_pass_rate, int | float)
        ):
            continue
        mean_delta = float(current_mean) - float(prior_mean)
        pass_rate_delta = float(current_pass_rate) - float(prior_pass_rate)
        comparisons[metric] = {
            "mean_delta": round(mean_delta, 6),
            "pass_rate_delta": round(pass_rate_delta, 6),
        }
        if mean_delta < -0.02 or pass_rate_delta < -0.05:
            regressed_metrics.append(metric)
    quality_failures = sum(int(values["failed_count"] or 0) for values in current.values())
    completed_cases = total_cases - execution_failures
    required_metrics = requested_metrics or list(current)
    unscored_counts = {
        metric: max(
            0,
            completed_cases
            - int(
                (current.get(metric) or {}).get(
                    "judged_count",
                    (current.get(metric) or {}).get("score_count", 0),
                )
                or 0
            ),
        )
        for metric in required_metrics
    }
    complete = all(count == 0 for count in unscored_counts.values())
    return {
        "completed_cases": completed_cases,
        "failed_cases": execution_failures,
        "complete": complete,
        "unscored_counts": unscored_counts,
        "execution_succeeded": execution_failures == 0,
        "quality_passed": complete and quality_failures == 0 and execution_failures == 0,
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
