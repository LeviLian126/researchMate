"""Score deterministic retrieval metrics and optional model-judged faithfulness."""

from __future__ import annotations

import asyncio

from researchmate_worker.evaluation_models import (
    EvaluationCase,
    EvaluationRuntimeError,
    MetricScore,
    PipelineResult,
)

SUPPORTED_METRICS = {"schema_valid", "citation_precision", "evidence_recall", "faithfulness"}


def _expected_chunk_ids(case: EvaluationCase) -> set[str]:
    raw = case.expected_evidence
    if isinstance(raw, dict):
        raw = raw.get("chunk_ids", [])
    return {str(value) for value in raw if value}


def deterministic_scores(
    metrics: list[str], case: EvaluationCase, result: PipelineResult
) -> list[MetricScore]:
    """Compute reproducible schema, citation, and evidence-recall metrics."""
    scores = []
    if "schema_valid" in metrics:
        valid = bool(result.response.strip()) and bool(result.cited_chunk_ids)
        scores.append(
            MetricScore(
                "schema_valid",
                "1.0",
                float(valid),
                valid,
                {"has_citations": bool(result.cited_chunk_ids)},
            )
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
