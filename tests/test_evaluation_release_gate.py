"""Verify the release gate rejects incomplete, regressed, and weak evaluation runs."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from scripts.check_evaluation_gate import evaluate_gate, main


def _payload() -> dict:
    return {
        "status": "succeeded",
        "summary": {
            "complete": True,
            "execution_succeeded": True,
            "quality_passed": True,
            "regression_detected": False,
            "pipeline_code_sha": "candidate-sha",
            "metric_summary": {
                "evidence_recall": {"mean_value": 0.90},
                "retrieval_mrr": {"mean_value": 0.75},
                "retrieval_ndcg": {"mean_value": 0.85},
            },
        },
    }


def test_release_gate_passes_complete_non_regressed_metrics() -> None:
    """Accept a successful run only when every required metric clears its threshold."""
    passed, reasons = evaluate_gate(
        _payload(),
        {"evidence_recall": 0.8, "retrieval_mrr": 0.5, "retrieval_ndcg": 0.8},
    )

    assert passed is True
    assert reasons == []


def test_release_gate_reports_regression_and_missing_metric() -> None:
    """Return actionable stable reasons for every release-blocking condition."""
    payload = _payload()
    payload["summary"]["regression_detected"] = True
    del payload["summary"]["metric_summary"]["retrieval_mrr"]

    passed, reasons = evaluate_gate(
        payload,
        {"evidence_recall": 0.8, "retrieval_mrr": 0.5},
    )

    assert passed is False
    assert reasons == ["baseline_regression_detected", "retrieval_mrr=missing"]


def test_release_gate_rejects_a_stale_pipeline_commit() -> None:
    """Bind the durable result to the release commit supplied by trusted CI context."""
    passed, reasons = evaluate_gate(
        _payload(),
        {"evidence_recall": 0.8},
        expected_code_sha="new-release-sha",
    )

    assert passed is False
    assert reasons == ["pipeline_code_sha_mismatch"]


def test_release_gate_preserves_failure_artifact_when_token_is_missing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Keep a safe auditable decision even when the protected credential is unavailable."""
    output = tmp_path / "gate.json"
    monkeypatch.delenv("RESEARCHMATE_EVAL_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_evaluation_gate.py",
            "--api-base",
            "https://researchmate-backend-dev-jkza.onrender.com",
            "--run-id",
            "00000000-0000-0000-0000-000000000001",
            "--output",
            str(output),
        ],
    )

    assert main() == 1
    assert json.loads(output.read_text(encoding="utf-8"))["reasons"] == ["gate_error=missing_token"]


def test_release_gate_preserves_failure_artifact_for_invalid_run_id(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Keep workflow input validation auditable instead of failing before artifact creation."""
    output = tmp_path / "gate.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_evaluation_gate.py",
            "--api-base",
            "https://researchmate-backend-dev-jkza.onrender.com",
            "--run-id",
            "not-a-uuid",
            "--output",
            str(output),
        ],
    )

    assert main() == 1
    assert json.loads(output.read_text(encoding="utf-8"))["reasons"] == [
        "gate_error=invalid_run_id"
    ]
