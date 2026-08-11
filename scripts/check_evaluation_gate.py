"""Fail a controlled release gate when a durable evaluation run is incomplete or regressed."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

DEFAULT_THRESHOLDS = {
    "evidence_recall": 0.80,
    "retrieval_mrr": 0.50,
    "retrieval_ndcg": 0.80,
}
# Any is intentional at this raw HTTP JSON boundary and is narrowed before every operation.
JsonObject = dict[str, Any]


def evaluate_gate(
    payload: JsonObject,
    thresholds: dict[str, float],
    expected_code_sha: str | None = None,
) -> tuple[bool, list[str]]:
    """Evaluate release policy from the API's safe aggregate response."""
    reasons: list[str] = []
    if payload.get("status") != "succeeded":
        reasons.append(f"run_status={payload.get('status', 'missing')}")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return False, [*reasons, "summary_missing"]
    if summary.get("complete") is not True:
        reasons.append("evaluation_incomplete")
    if summary.get("execution_succeeded") is not True:
        reasons.append("case_execution_failed")
    if summary.get("quality_passed") is not True:
        reasons.append("evaluation_quality_failed")
    if summary.get("regression_detected") is True:
        reasons.append("baseline_regression_detected")
    if expected_code_sha is not None and summary.get("pipeline_code_sha") != expected_code_sha:
        reasons.append("pipeline_code_sha_mismatch")
    metrics = summary.get("metric_summary")
    metric_summary = metrics if isinstance(metrics, dict) else {}
    for metric, minimum in thresholds.items():
        aggregate = metric_summary.get(metric)
        mean = aggregate.get("mean_value") if isinstance(aggregate, dict) else None
        if not isinstance(mean, int | float):
            reasons.append(f"{metric}=missing")
        elif float(mean) < minimum:
            reasons.append(f"{metric}={float(mean):.6f}<minimum={minimum:.6f}")
    return not reasons, reasons


def _parse_threshold(value: str) -> tuple[str, float]:
    """Parse one metric=value policy input with a normalized zero-to-one boundary."""
    name, separator, raw = value.partition("=")
    if not separator or not name.strip():
        raise argparse.ArgumentTypeError("threshold must use metric=value")
    try:
        minimum = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("threshold value must be numeric") from exc
    if not 0 <= minimum <= 1:
        raise argparse.ArgumentTypeError("threshold value must be between 0 and 1")
    return name.strip(), minimum


def _fetch_run(api_base: str, run_id: UUID, token: str) -> JsonObject:
    """Fetch one evaluation aggregate without logging the bearer credential."""
    parsed = urlparse(api_base)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("api base must use HTTPS outside localhost")
    url = f"{api_base.rstrip('/')}/api/v1/evaluation-runs/{run_id}"
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - URL is validated above.
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"evaluation API request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("evaluation API returned a non-object payload")
    return payload


def main() -> int:
    """Fetch, evaluate, and persist a safe release-gate artifact."""
    parser = argparse.ArgumentParser(description="Check a ResearchMate evaluation release gate")
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation-gate.json"))
    parser.add_argument("--threshold", action="append", type=_parse_threshold, default=[])
    args = parser.parse_args()
    thresholds = dict(args.threshold) if args.threshold else DEFAULT_THRESHOLDS
    payload: JsonObject = {}
    try:
        run_id = UUID(args.run_id)
    except ValueError:
        run_id = None
    token = os.getenv("RESEARCHMATE_EVAL_TOKEN", "").strip()
    if run_id is None:
        passed, reasons = False, ["gate_error=invalid_run_id"]
    elif not token:
        passed, reasons = False, ["gate_error=missing_token"]
    else:
        try:
            payload = _fetch_run(args.api_base, run_id, token)
            passed, reasons = evaluate_gate(
                payload,
                thresholds,
                expected_code_sha=args.expected_code_sha,
            )
        except RuntimeError as exc:
            passed, reasons = False, [f"gate_error={type(exc).__name__}"]
    artifact = {
        "evaluation_run_id": str(run_id) if run_id is not None else None,
        "expected_code_sha": args.expected_code_sha,
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "thresholds": thresholds,
        "passed": passed,
        "reasons": reasons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": passed, "reasons": reasons}, separators=(",", ":")))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
