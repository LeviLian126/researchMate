from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Engine, text
from pydantic import BaseModel, Field

from researchmate_api.schemas.common import SourceMode, SourceType
from researchmate_api.services.answering import build_llm_grounded_answer
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.store import ChunkEntry


SUPPORTED_METRICS = {"schema_valid", "citation_precision", "evidence_recall", "faithfulness"}


class PipelineRuntimeConfig(BaseModel):
    retrieval_limit: int = Field(default=12, ge=1, le=50)
    model: str = Field(min_length=1, max_length=200)
    evaluation_prompt_version: str = Field(pattern=r"^grounded-answer-v[0-9]+$")
    retrieval_mode: str = "dense_sparse_rerank"


@dataclass(frozen=True)
class EvaluationCase:
    id: UUID
    case_key: str
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    expected_evidence: dict[str, Any] | list[Any]


@dataclass(frozen=True)
class PipelineResult:
    response: str
    contexts: list[str]
    retrieved_chunk_ids: list[str]
    cited_chunk_ids: list[str]


@dataclass(frozen=True)
class MetricScore:
    name: str
    version: str
    value: float | None
    passed: bool | None
    details: dict[str, Any]
    judge_model: str | None = None


@dataclass(frozen=True)
class ClaimedEvaluation:
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
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class CaseExecutor(Protocol):
    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult: ...


class FaithfulnessScorer(Protocol):
    def score(self, case: EvaluationCase, result: PipelineResult) -> MetricScore: ...


def _expected_chunk_ids(case: EvaluationCase) -> set[str]:
    raw = case.expected_evidence
    if isinstance(raw, dict):
        raw = raw.get("chunk_ids", [])
    return {str(value) for value in raw if value}


def deterministic_scores(
    metrics: list[str], case: EvaluationCase, result: PipelineResult
) -> list[MetricScore]:
    scores = []
    if "schema_valid" in metrics:
        valid = bool(result.response.strip()) and bool(result.cited_chunk_ids)
        scores.append(
            MetricScore("schema_valid", "1.0", float(valid), valid, {"has_citations": bool(result.cited_chunk_ids)})
        )
    if "citation_precision" in metrics:
        retrieved = set(result.retrieved_chunk_ids)
        cited = set(result.cited_chunk_ids)
        value = len(cited & retrieved) / len(cited) if cited else 0.0
        scores.append(
            MetricScore(
                "citation_precision",
                "1.0",
                value,
                value == 1.0,
                {"cited": len(cited), "retrieved": len(retrieved)},
            )
        )
    if "evidence_recall" in metrics:
        expected = _expected_chunk_ids(case)
        retrieved = set(result.retrieved_chunk_ids)
        value = len(expected & retrieved) / len(expected) if expected else 1.0
        scores.append(
            MetricScore(
                "evidence_recall",
                "1.0",
                value,
                value >= 0.8,
                {"expected": len(expected), "matched": len(expected & retrieved)},
            )
        )
    return scores


class RagasFaithfulnessScorer:
    """Ragas 0.4 collections API backed by the configured OpenAI-compatible NVIDIA client."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def score(self, case: EvaluationCase, result: PipelineResult) -> MetricScore:
        async def evaluate() -> MetricScore:
            try:
                from openai import AsyncOpenAI
                from ragas.llms import llm_factory
                from ragas.metrics.collections import Faithfulness
            except ImportError as exc:
                raise EvaluationRuntimeError("RAGAS_NOT_INSTALLED") from exc
            client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0)
            evaluator = llm_factory(self.model, client=client)
            metric = Faithfulness(llm=evaluator)
            scored = await metric.ascore(
                user_input=str(case.input.get("question", "")),
                response=result.response,
                retrieved_contexts=result.contexts,
            )
            value = float(scored.value)
            return MetricScore(
                "faithfulness",
                "ragas-0.4.3",
                value,
                value >= 0.8,
                {"reason": getattr(scored, "reason", None)},
                judge_model=self.model,
            )

        return asyncio.run(evaluate())


class QdrantCaseExecutor:
    def __init__(self, engine: Engine, vector_store: QdrantHybridStore, provider: ChatProvider) -> None:
        self.engine = engine
        self.vector_store = vector_store
        self.provider = provider

    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult:
        question = case.input.get("question")
        if not isinstance(question, str) or not question.strip():
            raise EvaluationRuntimeError("EVALUATION_CASE_INVALID")
        provider_settings = getattr(self.provider, "settings", None)
        if (
            provider_settings is None
            or getattr(provider_settings, "nvidia_model", None) != run.pipeline.model
        ):
            raise EvaluationRuntimeError("PIPELINE_MODEL_NOT_CONFIGURED")
        if run.pipeline.evaluation_prompt_version != "grounded-answer-v1":
            raise EvaluationRuntimeError("PIPELINE_PROMPT_NOT_SUPPORTED")
        points = self.vector_store.query(
            user_id=str(run.user_id),
            project_id=str(run.project_id),
            source_type=SourceType.LOCAL_DOC,
            text=question,
            limit=run.pipeline.retrieval_limit,
        )
        ids = []
        for point in points:
            try:
                ids.append(UUID(str(point.get("payload", {}).get("chunk_id"))))
            except (TypeError, ValueError):
                continue
        chunks = self._chunks(run, ids)
        if not chunks:
            raise EvaluationRuntimeError("EVIDENCE_NOT_FOUND")
        answer, citations, _ = build_llm_grounded_answer(
            self.provider, question, SourceMode.LOCAL_ONLY, chunks
        )
        return PipelineResult(
            response=answer,
            contexts=[chunk.text for chunk in chunks],
            retrieved_chunk_ids=[str(chunk.id) for chunk in chunks],
            cited_chunk_ids=[str(citation.chunk_id) for citation in citations if citation.chunk_id],
        )

    def _chunks(self, run: ClaimedEvaluation, ids: list[UUID]) -> list[ChunkEntry]:
        if not ids:
            return []
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    select id,user_id,project_id,document_id,source_type,source_title,text,
                      page_no,slide_no,url,created_at
                    from chunks where user_id=:user_id and project_id=:project_id and id=any(:ids)
                    """
                ),
                {"user_id": run.user_id, "project_id": run.project_id, "ids": ids},
            ).mappings().all()
        by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[value] for value in ids if value in by_id]


class EvaluationRunner:
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
            code = sorted(set(retryable_codes))[0]
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

    def _execute_case(
        self, run: ClaimedEvaluation, case: EvaluationCase
    ) -> list[MetricScore]:
        result = self.executor.execute(run, case)
        scores = deterministic_scores(run.metrics, case, result)
        if "faithfulness" in run.metrics:
            scores.append(self.faithfulness.score(case, result))
        return scores

    def _claim(self, run_id: UUID, worker_id: str) -> ClaimedEvaluation | None:
        with self.engine.begin() as connection:
            row = connection.execute(
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
                      r.budget_limit_usd,r.pipeline_version_id,v.configuration
                    """
                ),
                {
                    "id": run_id,
                    "worker_id": worker_id,
                    "lease_seconds": self.lease_seconds,
                    "max_attempts": self.max_attempts,
                },
            ).mappings().one_or_none()
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
                Decimal(row["budget_limit_usd"])
                if row["budget_limit_usd"] is not None
                else None
            ),
            pipeline_version_id=row["pipeline_version_id"],
            pipeline=PipelineRuntimeConfig.model_validate(row["configuration"]),
        )

    def _load_cases(self, run_id: UUID) -> list[EvaluationCase]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    select c.id,c.case_key,c.input,c.expected_output,c.expected_evidence
                    from evaluation_cases c join evaluation_runs r on r.dataset_id=c.dataset_id
                    where r.id=:id order by c.case_key
                    """
                ),
                {"id": run_id},
            ).mappings().all()
        return [EvaluationCase(**dict(row)) for row in rows]

    def _completed_case_ids(self, run_id: UUID, metrics: list[str]) -> set[UUID]:
        with self.engine.begin() as connection:
            rows = connection.execute(
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
            ).scalars().all()
        return set(rows)

    def _reserve_case_budget(self, run_id: UUID, worker_id: str) -> bool:
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
            )
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


def _safe_evaluation_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, EvaluationRuntimeError):
        return exc.code, exc.retryable
    code = getattr(exc, "code", None)
    class_name = type(exc).__name__.lower()
    inferred_retryable = any(
        marker in class_name for marker in ("timeout", "connection", "ratelimit", "temporar")
    )
    safe_code = code if isinstance(code, str) and code else (
        "EVALUATION_PROVIDER_TEMPORARY" if inferred_retryable else "EVALUATION_CASE_FAILED"
    )
    return safe_code[:120], bool(getattr(exc, "retryable", inferred_retryable))


def _metric_aggregates(connection: Any, run_id: UUID) -> dict[str, dict[str, float | int]]:
    rows = connection.execute(
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
    ).mappings().all()
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
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
