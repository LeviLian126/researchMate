"""Expose the stable evaluation API from focused execution, scoring, and persistence modules."""

from researchmate_worker.evaluation_executor import QdrantCaseExecutor
from researchmate_worker.evaluation_models import (
    CaseExecutor,
    ClaimedEvaluation,
    EvaluationCase,
    EvaluationRuntimeError,
    FaithfulnessScorer,
    MetricScore,
    PipelineResult,
    PipelineRuntimeConfig,
)
from researchmate_worker.evaluation_runner import EvaluationRunner
from researchmate_worker.evaluation_scoring import RagasFaithfulnessScorer, deterministic_scores
from researchmate_worker.evaluation_summary import build_regression_summary

__all__ = [
    "CaseExecutor",
    "ClaimedEvaluation",
    "EvaluationCase",
    "EvaluationRunner",
    "EvaluationRuntimeError",
    "FaithfulnessScorer",
    "MetricScore",
    "PipelineResult",
    "PipelineRuntimeConfig",
    "QdrantCaseExecutor",
    "RagasFaithfulnessScorer",
    "build_regression_summary",
    "deterministic_scores",
]
