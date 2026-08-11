"""Coordinate bounded parallel evaluation while preserving retry and budget semantics."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine

from researchmate_worker.evaluation_models import (
    CaseExecutor,
    ClaimedEvaluation,
    EvaluationCase,
    EvaluationRuntimeError,
    FaithfulnessScorer,
    MetricScore,
)
from researchmate_worker.evaluation_persistence import EvaluationPersistenceMixin
from researchmate_worker.evaluation_scoring import deterministic_scores
from researchmate_worker.evaluation_summary import _safe_evaluation_error

SUPPORTED_METRICS = {
    "schema_valid",
    "citation_precision",
    "evidence_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "faithfulness",
}


class EvaluationRunner(EvaluationPersistenceMixin):
    """Coordinate bounded case evaluation under one durable run lease."""

    def __init__(
        self,
        *,
        engine: Engine,
        executor: CaseExecutor,
        faithfulness: FaithfulnessScorer,
        lease_seconds: int = 1800,
        max_attempts: int = 3,
        case_budget_reservation_usd: Decimal = Decimal("0.050000"),
    ) -> None:
        self.engine = engine
        self.executor = executor
        self.faithfulness = faithfulness
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        if case_budget_reservation_usd <= 0:
            raise ValueError("case budget reservation must be positive")
        self.case_budget_reservation_usd = case_budget_reservation_usd

    def run(self, evaluation_run_id: UUID, *, worker_id: str) -> str:
        """Evaluate incomplete cases within configured parallelism and budget limits."""
        try:
            claimed = self._claim(evaluation_run_id, worker_id)
        except EvaluationRuntimeError as exc:
            self._terminal_failure(evaluation_run_id, worker_id, exc.code)
            raise
        if claimed is None:
            return "not_claimed"
        cases = self._load_cases(claimed.id)
        if not cases:
            self._terminal_failure(claimed.id, worker_id, "EVALUATION_DATASET_EMPTY")
            return "failed"
        completed = self._completed_case_ids(claimed.id, claimed.metrics)
        pending_cases = [case for case in cases if case.id not in completed]
        permanent_failures = 0
        retryable_codes: list[str] = []
        with ThreadPoolExecutor(max_workers=claimed.max_parallelism) as pool:
            futures = {}
            for case in pending_cases:
                if not self._reserve_case_budget(claimed.id, worker_id):
                    permanent_failures += 1
                    self._save_scores(
                        claimed.id,
                        case.id,
                        [
                            MetricScore(
                                "case_execution",
                                "1.0",
                                None,
                                False,
                                {"error_code": "EVALUATION_BUDGET_EXHAUSTED"},
                            )
                        ],
                        worker_id=worker_id,
                    )
                    continue
                futures[pool.submit(self._execute_case, claimed, case)] = case
            for future in as_completed(futures):
                case = futures[future]
                try:
                    scores = future.result()
                except Exception as exc:
                    code, retryable = _safe_evaluation_error(exc)
                    if retryable:
                        retryable_codes.append(code)
                    else:
                        permanent_failures += 1
                    scores = [
                        MetricScore(
                            "case_execution",
                            "1.0",
                            None,
                            False,
                            {"error_code": code, "retryable": retryable},
                        )
                    ]
                self._save_scores(claimed.id, case.id, scores, worker_id=worker_id)
        if retryable_codes:
            code = min(set(retryable_codes))
            if claimed.attempts < self.max_attempts:
                self._release_for_retry(claimed.id, worker_id, code)
                raise EvaluationRuntimeError(code, retryable=True)
            permanent_failures += len(retryable_codes)
        return self._complete(
            claimed,
            worker_id,
            total=len(cases),
            failures=permanent_failures,
        )

    def _execute_case(self, run: ClaimedEvaluation, case: EvaluationCase) -> list[MetricScore]:
        result = self.executor.execute(run, case)
        scores = deterministic_scores(run.metrics, case, result)
        if "faithfulness" in run.metrics:
            scores.append(self.faithfulness.score(case, result))
        return scores
