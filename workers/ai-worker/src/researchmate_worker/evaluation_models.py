"""Define evaluation configurations, immutable results, and adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

SUPPORTED_METRICS = {"schema_valid", "citation_precision", "evidence_recall", "faithfulness"}


class PipelineRuntimeConfig(BaseModel):
    """Validate the accepted model, prompt, and retrieval configuration."""

    retrieval_limit: int = Field(default=12, ge=1, le=50)
    model: str = Field(min_length=1, max_length=200)
    evaluation_prompt_version: str = Field(pattern=r"^grounded-answer-v[0-9]+$")
    retrieval_mode: str = "dense_sparse_rerank"


@dataclass(frozen=True)
class EvaluationCase:
    """Carry one immutable dataset case and its expected evidence."""

    id: UUID
    case_key: str
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    expected_evidence: dict[str, Any] | list[Any]


@dataclass(frozen=True)
class PipelineResult:
    """Carry the generated answer and evidence selected by a pipeline."""

    response: str
    contexts: list[str]
    retrieved_chunk_ids: list[str]
    cited_chunk_ids: list[str]


@dataclass(frozen=True)
class MetricScore:
    """Carry one normalized metric outcome and optional judge provenance."""

    name: str
    version: str
    value: float | None
    passed: bool | None
    details: dict[str, Any]
    judge_model: str | None = None


@dataclass(frozen=True)
class ClaimedEvaluation:
    """Carry the lease-protected run policy needed by case workers."""

    id: UUID
    user_id: UUID
    project_id: UUID
    dataset_id: UUID
    metrics: list[str]
    max_parallelism: int
    attempts: int
    budget_limit_usd: Decimal | None
    pipeline_version_id: UUID
    pipeline: PipelineRuntimeConfig


class EvaluationRuntimeError(RuntimeError):
    """Expose a stable evaluation failure code and retry classification."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class CaseExecutor(Protocol):
    """Define the replaceable boundary for executing one evaluation case."""

    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult: ...


class FaithfulnessScorer(Protocol):
    """Define the optional model-judged faithfulness boundary."""

    def score(self, case: EvaluationCase, result: PipelineResult) -> MetricScore: ...
