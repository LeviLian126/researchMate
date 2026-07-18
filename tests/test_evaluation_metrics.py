from decimal import Decimal
from uuid import UUID

from researchmate_worker.evaluation import (
    EvaluationCase,
    PipelineResult,
    build_regression_summary,
    deterministic_scores,
)


def test_deterministic_evaluation_metrics_reconcile_evidence_sets() -> None:
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
        ["schema_valid", "citation_precision", "evidence_recall"], case, result
    )
    by_name = {score.name: score for score in scores}

    assert by_name["schema_valid"].passed is True
    assert by_name["citation_precision"].value == 1.0
    assert by_name["evidence_recall"].value == 1.0


def test_evidence_recall_exposes_missing_expected_chunks() -> None:
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


def test_regression_summary_separates_execution_quality_and_baseline_regression() -> None:
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
