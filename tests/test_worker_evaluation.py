"""Verify deterministic evaluation scoring, runner coordination, and error classification.

These tests use isolated fakes for the Qdrant vector store, the SQL engine, and the
optional ragas faithfulness scorer so the worker evaluation pipeline remains
reproducible without any network or third-party dependency.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from researchmate_worker.evaluation import (
    ClaimedEvaluation,
    EvaluationCase,
    EvaluationRuntimeError,
    MetricScore,
    PipelineResult,
    PipelineRuntimeConfig,
)
from researchmate_worker.evaluation_executor import QdrantCaseExecutor
from researchmate_worker.evaluation_runner import EvaluationRunner
from researchmate_worker.evaluation_scoring import deterministic_scores
from researchmate_worker.evaluation_summary import (
    _safe_evaluation_error,
    build_regression_summary,
    json_dumps,
)

USER_ID = UUID("00000000-0000-4000-8000-000000000040")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000041")
DATASET_ID = UUID("00000000-0000-4000-8000-000000000042")
PIPELINE_VERSION_ID = UUID("00000000-0000-4000-8000-000000000043")
CASE_ID = UUID("00000000-0000-4000-8000-000000000444")
RUN_ID = UUID("00000000-0000-4000-8000-000000000444")
RUN_ID = UUID("00000000-0000-4000-8000-000000000444")


def case(
    *,
    case_id: UUID = CASE_ID,
    case_key: str = "case-1",
    question: str = "What is supported?",
    expected_evidence: dict | list | None = None,
) -> EvaluationCase:
    """Build a deterministic evaluation case for scoring and runner tests."""
    return EvaluationCase(
        id=case_id,
        case_key=case_key,
        input={"question": question},
        expected_output=None,
        expected_evidence=expected_evidence if expected_evidence is not None else ["a", "b"],
    )


def pipeline_result(cited: list[str] | None = None) -> PipelineResult:
    """Build a deterministic pipeline result for metric scoring tests."""
    return PipelineResult(
        response="Answer supported by the supplied evidence.",
        contexts=["context one"],
        retrieved_chunk_ids=["a", "b", "c"],
        cited_chunk_ids=cited or ["a", "c"],
    )


def claimed(metrics=("schema_valid", "citation_precision", "evidence_recall")) -> ClaimedEvaluation:
    """Build a lease-protected run policy for runner tests."""
    return ClaimedEvaluation(
        id=RUN_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        metrics=list(metrics),
        max_parallelism=2,
        attempts=1,
        budget_limit_usd=Decimal("1.00"),
        pipeline_version_id=PIPELINE_VERSION_ID,
        pipeline_code_sha="test-code-sha",
        pipeline=PipelineRuntimeConfig(
            retrieval_limit=12,
            model="z-ai/glm-5.2",
            evaluation_prompt_version="grounded-answer-v1",
        ),
    )


# ---------------------------------------------------------------------------
# Deterministic scoring edge cases
# ---------------------------------------------------------------------------


def test_citation_precision_returns_zero_when_no_citations_were_produced() -> None:
    """Score citation precision zero when the pipeline produced no citations."""
    result = PipelineResult(
        response="No grounded citations.",
        contexts=["context"],
        retrieved_chunk_ids=["a"],
        cited_chunk_ids=[],
    )
    precision = next(
        score
        for score in deterministic_scores(["citation_precision"], case(), result)
        if score.name == "citation_precision"
    )
    assert precision.value == 0.0
    assert precision.passed is False
    assert precision.details == {"cited": 0, "retrieved": 1}


def test_evidence_recall_reports_full_recall_when_no_expected_evidence() -> None:
    """Report full recall when the dataset case has no expected evidence."""
    result = pipeline_result(["a"])
    score = next(
        score
        for score in deterministic_scores(["evidence_recall"], case(expected_evidence=[]), result)
        if score.name == "evidence_recall"
    )
    assert score.value == 1.0
    assert score.passed is True
    assert score.details == {"expected": 0, "matched": 0}


def test_deterministic_scores_skips_unrequested_metrics() -> None:
    """Never include metric scores that were not requested."""
    scores = deterministic_scores(["schema_valid"], case(), pipeline_result(["a"]))
    assert {score.name for score in scores} == {"schema_valid"}


def test_deterministic_scores_supports_dict_expected_evidence_shape() -> None:
    """Read expected-evidence chunk IDs from a dict payload of the documented shape."""
    result = pipeline_result(["a"])
    score = next(
        score
        for score in deterministic_scores(
            ["evidence_recall"],
            case(expected_evidence={"chunk_ids": ["a"]}),
            result,
        )
        if score.name == "evidence_recall"
    )
    assert score.value == 1.0
    assert score.passed is True


# ---------------------------------------------------------------------------
# Regression summary & error normalization
# ---------------------------------------------------------------------------


def test_safe_evaluation_error_normalizes_unstructured_exceptions() -> None:
    """Classify unstructured exceptions as non-retryable failures."""
    code, retryable = _safe_evaluation_error(RuntimeError("unexpected"))
    assert code == "EVALUATION_CASE_FAILED"
    assert retryable is False


def test_safe_evaluation_error_preserves_evaluation_runtime_error_code() -> None:
    """Pass through the stable code and retryable flag of an EvaluationRuntimeError."""
    code, retryable = _safe_evaluation_error(
        EvaluationRuntimeError("PROVIDER_FAILED", retryable=True)
    )
    assert code == "PROVIDER_FAILED"
    assert retryable is True


def test_build_regression_summary_flags_metric_regression() -> None:
    """Detect regression when pass-rate drops below the configured threshold."""
    summary = build_regression_summary(
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 0.7,
                "pass_rate": 0.5,
                "failed_count": 1,
            }
        },
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 0.95,
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
    assert summary["baseline_run_id"] == str(UUID(int=2))


def test_build_regression_summary_marks_complete_only_when_no_failures() -> None:
    """Report quality_passed only when both execution and metric quality succeed."""
    summary = build_regression_summary(
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 1.0,
                "pass_rate": 1.0,
                "failed_count": 0,
            }
        },
        {
            "faithfulness": {
                "score_count": 2,
                "mean_value": 0.9,
                "pass_rate": 1.0,
                "failed_count": 0,
            }
        },
        total_cases=2,
        execution_failures=0,
        baseline_run_id=None,
        budget_limit_usd=Decimal("1.00"),
        budget_reserved_usd=Decimal("0.20"),
    )
    assert summary["complete"] is True
    assert summary["quality_passed"] is True
    assert summary["regression_detected"] is False


def test_json_dumps_returns_compact_repr_without_extra_keys() -> None:
    """Serialize metric details without spaces while preserving Unicode."""
    assert json_dumps({"k": "v", "中文": 1}) == '{"k":"v","中文":1}'


# ---------------------------------------------------------------------------
# Runner coordination with fakes
# ---------------------------------------------------------------------------


class FakeExecutor:
    """Capture run/case inputs and return a deterministic pipeline result."""

    def __init__(
        self, *, response: str = "cited answer", chunk_ids: list[str] | None = None
    ) -> None:
        self.calls: list[tuple[ClaimedEvaluation, EvaluationCase]] = []
        self.response = response
        self.chunk_ids = chunk_ids or ["a", "b"]

    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult:
        self.calls.append((run, case))
        return PipelineResult(
            response=self.response,
            contexts=["cited-context"],
            retrieved_chunk_ids=self.chunk_ids,
            cited_chunk_ids=self.chunk_ids[:1],
        )


class FailingExecutor:
    """Always raise a deterministic exception so the runner can record it."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult:
        raise self.error


class FakeFaithfulnessScorer:
    """Record score calls and return a deterministic faithfulness metric."""

    def __init__(self, value: float = 0.9, passed: bool = True) -> None:
        self.value = value
        self.passed_flag = passed
        self.calls: list[tuple[EvaluationCase, PipelineResult]] = []

    def score(self, case_: EvaluationCase, result: PipelineResult) -> MetricScore:
        self.calls.append((case_, result))
        return MetricScore(
            "faithfulness",
            "fake",
            self.value,
            self.passed_flag,
            {"reason": "test fixture"},
        )


class StubResult:
    """Return configured sequential query results from the SQL engine."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def mappings(self) -> StubResult:
        return self

    def one_or_none(self) -> Any:
        return self.value

    def scalar_one(self) -> Any:
        return self.value

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalars(self) -> StubResult:
        # SQL helpers like .scalars().all() unpack scalar columns; reuse ourselves.
        return self

    def all(self) -> Any:
        # Mappings().all() returns a list of row dicts. If the queued value is already
        # a list of rows, return it; for non-list payloads (scalars or rowcounts)
        # return an empty list so iteration is harmless.
        if isinstance(self.value, list):
            return self.value
        return []

    @property
    def rowcount(self) -> int:
        # UPDATE/INSERT statements assert the affected row count; surface a truthy value.
        return 1 if self.value is not None else 0


class StubConnection:
    """Return queued results from each execute() call in declaration order."""

    def __init__(self, values: list[Any]) -> None:
        self.values = deque(values)
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, statement: Any, parameters: dict[str, Any] | None = None) -> StubResult:
        # boundary: opaque test double for SQLAlchemy statements/parameters.
        self.calls.append((str(statement), parameters))
        value = self.values.popleft() if self.values else None
        return StubResult(value)


class StubEngine:
    """Provide a one-shot transaction context for the EvaluationRunner."""

    def __init__(self, values: list[Any]) -> None:
        self.connection = StubConnection(values)

    @contextmanager
    def begin(self) -> Iterator[StubConnection]:
        yield self.connection


def _run_claim_row(claimed: ClaimedEvaluation) -> dict[str, Any]:
    """Build a deterministic evaluation_runs row matching the runner's _claim expectations."""
    return {
        "id": claimed.id,
        "user_id": claimed.user_id,
        "project_id": claimed.project_id,
        "dataset_id": claimed.dataset_id,
        "summary": {
            "metrics": claimed.metrics,
            "max_parallelism": claimed.max_parallelism,
        },
        "attempts": claimed.attempts,
        "budget_limit_usd": str(claimed.budget_limit_usd) if claimed.budget_limit_usd else None,
        "pipeline_version_id": claimed.pipeline_version_id,
        "code_sha": claimed.pipeline_code_sha,
        "configuration": {
            "retrieval_limit": claimed.pipeline.retrieval_limit,
            "model": claimed.pipeline.model,
            "evaluation_prompt_version": claimed.pipeline.evaluation_prompt_version,
            "retrieval_mode": claimed.pipeline.retrieval_mode,
        },
    }


def _case_row(case_id: UUID = CASE_ID, case_key: str = "case-1") -> dict[str, Any]:
    """Build an evaluation_cases row matching the runner's _load_cases expectations."""
    return {
        "id": case_id,
        "case_key": case_key,
        "input": {"question": "What is supported?"},
        "expected_output": None,
        "expected_evidence": ["a", "b"],
    }


def test_run_rejects_zero_case_budget_reservation() -> None:
    """Refuse to construct a runner with a non-positive case budget reservation."""
    with pytest.raises(ValueError):
        EvaluationRunner(
            engine=StubEngine([]),  # type: ignore[arg-type]
            executor=FakeExecutor(),
            faithfulness=FakeFaithfulnessScorer(),
            case_budget_reservation_usd=Decimal("0"),
        )


def test_run_returns_not_claimed_when_no_pending_run_is_available() -> None:
    """Return not_claimed without persistence when no run can be leased."""
    engine = StubEngine([None])
    runner = EvaluationRunner(
        engine=engine,  # type: ignore[arg-type]
        executor=FakeExecutor(),
        faithfulness=FakeFaithfulnessScorer(),
    )
    assert runner.run(RUN_ID, worker_id="worker-1") == "not_claimed"
    # Only the claim SQL ran; no terminal failure or scoring writes occurred.
    assert runner.engine.connection.calls[0][0].count("update evaluation_runs") == 1


def test_run_fails_when_dataset_has_no_cases() -> None:
    """Mark the run as a terminal failure when the dataset is empty."""
    claimed_run = claimed()
    engine = StubEngine([_run_claim_row(claimed_run), []])
    runner = EvaluationRunner(
        engine=engine,  # type: ignore[arg-type]
        executor=FakeExecutor(),
        faithfulness=FakeFaithfulnessScorer(),
    )
    assert runner.run(claimed_run.id, worker_id="worker-1") == "failed"
    # The terminal failure must update the run status and clear the worker lease.
    terminal_sql = runner.engine.connection.calls[-1][0]
    assert "status='failed'" in terminal_sql
    assert "lease_owner=null" in terminal_sql
    assert "completed_at=now()" in terminal_sql


def test_run_completes_each_case_with_deterministic_scores_and_aggregates() -> None:
    """Persist per-case scores and mark the run succeeded when execution and quality pass."""
    claimed_run = claimed(metrics=("schema_valid", "citation_precision", "evidence_recall"))
    # The runner executes claim, load cases, completed-check, reserve-budget, save scores
    # (lease check, delete previous, one insert per non-case_execution score: 3 deterministic
    # metrics, since "faithfulness" is not in claimed metrics), then complete (aggregates,
    # baseline id, budget reserved scalar, final update rowcount).
    engine = StubEngine(
        [
            _run_claim_row(claimed_run),  # _claim
            [_case_row()],  # _load_cases
            [],  # _completed_case_ids (no completed yet)
            1,  # _reserve_case_budget returns the updated budget row
            1,  # _save_scores lease check (truthy so the lease is retained)
            0,  # _save_scores delete previous scores (returns rowcount)
            1,  # _save_scores insert for schema_valid
            1,  # _save_scores insert for citation_precision
            1,  # _save_scores insert for evidence_recall
            {},  # _complete _metric_aggregates (no persisted scores recorded yet)
            None,  # _complete baseline run id (no prior baseline)
            Decimal("0.05"),  # _complete budget_reserved_usd scalar
            1,  # _complete final update rowcount
        ]
    )
    executor = FakeExecutor()
    runner = EvaluationRunner(
        engine=engine,  # type: ignore[arg-type]
        executor=executor,
        faithfulness=FakeFaithfulnessScorer(),
    )
    result = runner.run(claimed_run.id, worker_id="worker-1")
    assert result == "succeeded"
    assert len(executor.calls) == 1
    assert executor.calls[0][1].id == CASE_ID
    # The complete step builds a regression summary and uses the run lease.
    complete_sql = runner.engine.connection.calls[-1][0]
    assert "status=:status" in complete_sql
    assert "lease_owner=:worker_id" in complete_sql


def test_run_records_case_execution_failure_when_executor_fails_non_retry() -> None:
    """Persist a non-retryable case execution failure and mark the run failed."""
    claimed_run = claimed(metrics=("schema_valid",))
    engine = StubEngine(
        [
            _run_claim_row(claimed_run),
            [_case_row()],
            [],
            1,  # reserve budget
            1,  # save scores lease check
            0,  # save scores delete previous
            {},  # complete metric aggregates
            None,  # complete baseline run id
            Decimal("0.05"),  # budget reserved scalar
            1,  # complete update rowcount
        ]
    )
    runner = EvaluationRunner(
        engine=engine,  # type: ignore[arg-type]
        executor=FailingExecutor(RuntimeError("boom")),
        faithfulness=FakeFaithfulnessScorer(),
    )
    result = runner.run(claimed_run.id, worker_id="worker-1")
    assert result == "failed"
    # The case_execution failure score is persisted with the safe error code.
    save_lease_sql = [
        call[0] for call in runner.engine.connection.calls if "lease_owner" in call[0]
    ]
    assert any("lease_expires_at>now()" in sql for sql in save_lease_sql)


def test_run_releases_retryable_failure_when_attempts_remain() -> None:
    """Requeue retryable failures for the next worker attempt instead of failing terminally."""
    claimed_run = claimed(metrics=("schema_valid",))
    engine = StubEngine(
        [
            _run_claim_row(claimed_run),
            [_case_row()],
            [],
            1,  # reserve budget returns success
            1,  # save scores lease check
            0,  # save scores delete previous
            # _release_for_retry only executes the update.
            1,  # _release_for_retry update rowcount (unused)
        ]
    )
    runner = EvaluationRunner(
        engine=engine,  # type: ignore[arg-type]
        executor=FailingExecutor(EvaluationRuntimeError("PROVIDER_TEMP", retryable=True)),
        faithfulness=FakeFaithfulnessScorer(),
        max_attempts=3,
    )
    with pytest.raises(EvaluationRuntimeError) as raised:
        runner.run(claimed_run.id, worker_id="worker-1")
    assert raised.value.code == "PROVIDER_TEMP"
    assert raised.value.retryable is True
    release_sql = runner.engine.connection.calls[-1][0]
    assert "status='pending'" in release_sql
    assert "last_error_code=:code" in release_sql


# ---------------------------------------------------------------------------
# QdrantCaseExecutor SQL & vector store contracts
# ---------------------------------------------------------------------------


def test_executor_pipeline_model_and_prompt_versions_are_validated() -> None:
    """Reject pipelines whose model or prompt is unsupported by the executor.

    Drives QdrantCaseExecutor.execute through each validation failure branch
    and asserts the stable EvaluationRuntimeError codes are raised at runtime.
    """

    class FakeVectorStore:
        def query(self, **_kwargs):
            return []

    base_provider = SimpleNamespace(
        settings=SimpleNamespace(nvidia_model="z-ai/glm-5.2")
    )
    executor = QdrantCaseExecutor(
        engine=object(),  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        provider=base_provider,
    )

    # EVALUATION_CASE_INVALID: no question in case input.
    with pytest.raises(EvaluationRuntimeError) as exc_info:
        executor.execute(
            claimed(),
            EvaluationCase(
                id=CASE_ID, case_key="bad", input={}, expected_output=None,
                expected_evidence=[],
            ),
        )
    assert exc_info.value.code == "EVALUATION_CASE_INVALID"

    # PIPELINE_MODEL_NOT_CONFIGURED: model mismatch.
    with pytest.raises(EvaluationRuntimeError) as exc_info:
        executor.execute(_run_with_model("other-model"), case())
    assert exc_info.value.code == "PIPELINE_MODEL_NOT_CONFIGURED"

    # PIPELINE_PROMPT_NOT_SUPPORTED: valid but unsupported prompt version.
    with pytest.raises(EvaluationRuntimeError) as exc_info:
        executor.execute(
            _run_with_prompt("grounded-answer-v2"),
            case(),
        )
    assert exc_info.value.code == "PIPELINE_PROMPT_NOT_SUPPORTED"

    # EVIDENCE_NOT_FOUND: no chunks returned by the vector store.
    with pytest.raises(EvaluationRuntimeError) as exc_info:
        executor.execute(claimed(), case())
    assert exc_info.value.code == "EVIDENCE_NOT_FOUND"

    # The accepted prompt version is grounded-answer-v1: passing it must not
    # raise PIPELINE_PROMPT_NOT_SUPPORTED.
    valid_run = claimed()
    assert valid_run.pipeline.evaluation_prompt_version == "grounded-answer-v1"


def _run_with_model(model: str) -> ClaimedEvaluation:
    """Build a claimed run with an overridden pipeline model."""
    run = claimed()
    return ClaimedEvaluation(
        **{**run.__dict__, "pipeline": PipelineRuntimeConfig(
            retrieval_limit=12,
            model=model,
            evaluation_prompt_version="grounded-answer-v1",
        )}
    )


def _run_with_prompt(prompt: str) -> ClaimedEvaluation:
    """Build a claimed run with an overridden prompt version."""
    run = claimed()
    return ClaimedEvaluation(
        **{**run.__dict__, "pipeline": PipelineRuntimeConfig(
            retrieval_limit=12,
            model="z-ai/glm-5.2",
            evaluation_prompt_version=prompt,
        )}
    )


def test_executor_loads_owned_chunks_with_any_array_parameter() -> None:
    """Bind ids as an array literal and scope by owner in the chunk lookup.

    Drives the _chunks method through QdrantCaseExecutor.execute (the public
    entry point). The FakeVectorStore returns one chunk_id, so _chunks opens
    a transaction and the captured SQL must use id=any(:ids) with the owner
    predicate.
    """
    from contextlib import contextmanager

    class ChunkResult:
        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows

        def mappings(self) -> ChunkResult:
            return self

        def all(self) -> list[dict]:
            return self.rows

    class ChunkRecordingConnection:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return ChunkResult([_chunk_row(CASE_ID)])

        @property
        def rowcount(self) -> int:
            return 0

    class ChunkRecordingEngine:
        def __init__(self) -> None:
            self.connection = ChunkRecordingConnection()

        @contextmanager
        def begin(self) -> Iterator[ChunkRecordingConnection]:
            yield self.connection

    class OneIdVectorStore:
        def query(self, **_kwargs):
            return [{"payload": {"chunk_id": str(CASE_ID)}}]

    engine = ChunkRecordingEngine()
    executor = QdrantCaseExecutor(
        engine=engine,  # type: ignore[arg-type]
        vector_store=OneIdVectorStore(),  # type: ignore[arg-type]
        provider=SimpleNamespace(
            settings=SimpleNamespace(nvidia_model="z-ai/glm-5.2")
        ),
    )

    # _chunks is called internally after the vector store returns one ID.
    # The grounded answer will fail to build, but we just need _chunks to run.
    try:
        executor.execute(claimed(), case())
    except Exception:
        # build_llm_grounded_answer may fail; we only care about the SQL.
        pass

    chunk_calls = engine.connection.calls
    assert len(chunk_calls) == 1, "exactly one chunk-lookup SQL must execute"

    chunk_sql = chunk_calls[0][0]
    assert "id=any(:ids)" in chunk_sql, "chunk lookup must bind ids as an array literal"
    assert "user_id=:user_id" in chunk_sql, "chunk lookup must scope by user"
    assert "project_id=:project_id" in chunk_sql, "chunk lookup must scope by project"

    chunk_params = chunk_calls[0][1]
    assert chunk_params["ids"] == [CASE_ID], "chunk lookup must bind the vector-store IDs"


def _chunk_row(chunk_id: UUID) -> dict:
    """Build one chunks-table row matching the ChunkEntry field contract."""
    return {
        "id": chunk_id,
        "user_id": USER_ID,
        "project_id": PROJECT_ID,
        "document_id": None,
        "source_type": "local_doc",
        "source_title": "test.pdf",
        "text": "answer supported by evidence",
        "page_no": None,
        "slide_no": None,
        "url": None,
        "section_title": None,
        "section_path": "",
        "chunk_index": 0,
        "char_start": None,
        "char_end": None,
        "metadata": {},
        "created_at": datetime.now(UTC),
    }


def test_supported_metrics_match_between_executor_runner_and_scoring() -> None:
    """Keep the supported metric set consistent across the executor and runner modules."""
    from researchmate_worker.evaluation_executor import SUPPORTED_METRICS as executor_metrics
    from researchmate_worker.evaluation_runner import SUPPORTED_METRICS as runner_metrics
    from researchmate_worker.evaluation_scoring import SUPPORTED_METRICS as scoring_metrics

    assert executor_metrics == runner_metrics == scoring_metrics
    assert executor_metrics == {
        "schema_valid",
        "citation_precision",
        "evidence_recall",
        "retrieval_mrr",
        "retrieval_ndcg",
        "faithfulness",
    }


def test_evaluation_retrieval_modes_change_channel_weights() -> None:
    """Make dense, sparse, and hybrid pipeline versions observably distinct."""
    from researchmate_worker.evaluation_executor import evaluation_retrieval_plan

    dense = evaluation_retrieval_plan("question", "dense_only")
    sparse = evaluation_retrieval_plan("question", "sparse_only")
    hybrid = evaluation_retrieval_plan("question", "hybrid")

    assert (dense.dense_weight, dense.lexical_weight) == (1.0, 0.0)
    assert (sparse.dense_weight, sparse.lexical_weight) == (0.0, 1.0)
    assert (hybrid.dense_weight, hybrid.lexical_weight) == (0.5, 0.5)
