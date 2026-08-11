"""Score deterministic retrieval metrics and optional model-judged faithfulness."""

from __future__ import annotations

import asyncio
import math

from researchmate_worker.evaluation_models import (
    EvaluationCase,
    EvaluationRuntimeError,
    MetricScore,
    PipelineResult,
)

SUPPORTED_METRICS = {
    "schema_valid",
    "citation_precision",
    "evidence_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "faithfulness",
}


def _expected_chunk_ids(case: EvaluationCase) -> set[str]:
    raw = case.expected_evidence
    if isinstance(raw, dict):
        raw = raw.get("chunk_ids", [])
    return {str(value) for value in raw if value}


def _unjudged_rank_score(name: str) -> MetricScore:
    """Represent a missing relevance judgment without inventing a zero-quality result."""
    return MetricScore(
        name,
        "1.0",
        None,
        None,
        {"reason": "expected_evidence_missing"},
    )


def _reciprocal_rank(expected: set[str], retrieved: list[str]) -> tuple[float, int | None]:
    """Return the reciprocal rank and one-based rank of the first relevant chunk."""
    for index, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in expected:
            return 1.0 / index, index
    return 0.0, None


def _normalized_discounted_gain(expected: set[str], retrieved: list[str]) -> float:
    """Compute binary-relevance NDCG across the bounded retrieved list."""
    if not retrieved:
        return 0.0
    gains = [1.0 if chunk_id in expected else 0.0 for chunk_id in retrieved]
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal_hits = min(len(expected), len(retrieved))
    ideal = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / ideal if ideal else 0.0


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
    if "retrieval_mrr" in metrics:
        expected = _expected_chunk_ids(case)
        if not expected:
            scores.append(_unjudged_rank_score("retrieval_mrr"))
        else:
            value, first_rank = _reciprocal_rank(expected, result.retrieved_chunk_ids)
            scores.append(
                MetricScore(
                    "retrieval_mrr",
                    "1.0",
                    value,
                    value >= 0.5,
                    {
                        "first_relevant_rank": first_rank,
                        "k": len(result.retrieved_chunk_ids),
                    },
                )
            )
    if "retrieval_ndcg" in metrics:
        expected = _expected_chunk_ids(case)
        if not expected:
            scores.append(_unjudged_rank_score("retrieval_ndcg"))
        else:
            value = _normalized_discounted_gain(expected, result.retrieved_chunk_ids)
            scores.append(
                MetricScore(
                    "retrieval_ndcg",
                    "1.0",
                    value,
                    value >= 0.8,
                    {
                        "expected": len(expected),
                        "k": len(result.retrieved_chunk_ids),
                    },
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
