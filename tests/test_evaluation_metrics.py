"""Verify deterministic evaluation metrics and regression summaries."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from researchmate_worker.evaluation import (
    EvaluationCase,
    PipelineResult,
    build_regression_summary,
    deterministic_scores,
)


def test_deterministic_evaluation_metrics_reconcile_evidence_sets() -> None:
    """Reconcile citation and expected-evidence sets deterministically."""
    case = EvaluationCase(
        id=UUID(int=1),
        case_key="case-1",
        input={"question": "What is supported?"},
        expected_output=None,
        expected_evidence={"chunk_ids": ["a", "b"]},
    )
    result = PipelineResult(
        response="Supported answer",
        contexts=["context"],
        retrieved_chunk_ids=["a", "b", "c"],
        cited_chunk_ids=["a", "c"],
    )

    scores = deterministic_scores(
        [
            "schema_valid",
            "citation_precision",
            "evidence_recall",
            "retrieval_mrr",
            "retrieval_ndcg",
        ],
        case,
        result,
    )
    by_name = {score.name: score for score in scores}

    assert by_name["schema_valid"].passed is True
    assert by_name["citation_precision"].value == 1.0
    assert by_name["evidence_recall"].value == 1.0
    assert by_name["retrieval_mrr"].value == 1.0
    assert by_name["retrieval_mrr"].details["first_relevant_rank"] == 1
    assert by_name["retrieval_ndcg"].value == pytest.approx(1.0)
    assert by_name["retrieval_ndcg"].details["k"] == 3


def test_evidence_recall_exposes_missing_expected_chunks() -> None:
    """Report which expected chunks are absent from retrieved evidence."""
    case = EvaluationCase(
        id=UUID(int=1),
        case_key="case-1",
        input={"question": "question"},
        expected_output=None,
        expected_evidence=["a", "b"],
    )
    result = PipelineResult("answer", ["context"], ["a"], ["a"])

    score = deterministic_scores(["evidence_recall"], case, result)[0]

    assert score.value == 0.5
    assert score.passed is False


def test_rank_metrics_handle_no_expected_evidence_without_fabricating_quality() -> None:
    """Leave rank metrics unscored when a case has no relevance judgment."""
    case = EvaluationCase(
        id=UUID(int=1),
        case_key="unjudged",
        input={"question": "What changed?"},
        expected_output=None,
        expected_evidence=[],
    )
    result = PipelineResult(
        response="Answer",
        contexts=["Context"],
        retrieved_chunk_ids=["chunk-a"],
        cited_chunk_ids=["chunk-a"],
    )

    scores = deterministic_scores(["retrieval_mrr", "retrieval_ndcg"], case, result)

    assert [score.name for score in scores] == ["retrieval_mrr", "retrieval_ndcg"]
    assert all(score.value is None and score.passed is None for score in scores)
    assert all(score.details["reason"] == "expected_evidence_missing" for score in scores)


def test_regression_summary_separates_execution_quality_and_baseline_regression() -> None:
    """Keep execution quality distinct from baseline regression signals."""
    summary = build_regression_summary(
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 0.70,
                "pass_rate": 0.5,
                "failed_count": 1,
            }
        },
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 0.90,
                "pass_rate": 1.0,
                "failed_count": 0,
            }
        },
        total_cases=2,
        execution_failures=0,
        baseline_run_id=UUID(int=2),
        budget_limit_usd=Decimal("1.00"),
        budget_reserved_usd=Decimal("0.10"),
    )

    assert summary["execution_succeeded"] is True
    assert summary["quality_passed"] is False
    assert summary["regression_detected"] is True
    assert summary["regressed_metrics"] == ["faithfulness"]
    assert summary["budget_reserved_usd"] == "0.10"


def test_regression_summary_is_incomplete_when_a_rank_metric_has_unjudged_cases() -> None:
    """Prevent a small judged subset from representing an otherwise unjudged dataset."""
    summary = build_regression_summary(
        {
            "retrieval_mrr": {
                "score_count": 2,
                "judged_count": 1,
                "mean_value": 1.0,
                "pass_rate": 1.0,
                "failed_count": 0,
            }
        },
        {},
        total_cases=2,
        execution_failures=0,
        baseline_run_id=None,
        budget_limit_usd=Decimal("1.00"),
        budget_reserved_usd=Decimal("0.10"),
        requested_metrics=["retrieval_mrr"],
    )

    assert summary["complete"] is False
    assert summary["quality_passed"] is False
    assert summary["unscored_counts"] == {"retrieval_mrr": 1}
