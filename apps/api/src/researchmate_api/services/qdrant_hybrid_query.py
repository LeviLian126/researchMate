"""Build and execute native BM25 plus dense Qdrant fusion requests."""

from __future__ import annotations

from typing import Any

from qdrant_client import models

from researchmate_api.config import Settings
from researchmate_api.schemas.common import MAX_TEXT_LENGTH
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.query_planning import RetrievalPlan


def execute_hybrid_query(
    client: Any,  # Qdrant SDK clients and test doubles share no stable public protocol.
    embedding: NvidiaEmbeddingProvider,
    settings: Settings,
    collection: str,
    plan: RetrievalPlan,
    query_filter: models.Filter,
    *,
    limit: int,
) -> Any:  # Qdrant response models vary across compatible client patch versions.
    """Weight every query variant fairly across native lexical and dense branches."""
    dense_vectors = (
        embedding.embed(list(plan.queries), input_type="query")
        if plan.dense_weight > 0
        else [None] * len(plan.queries)
    )
    branch_limit = max(limit * 3, 20)
    per_query_dense = plan.dense_weight / len(plan.queries)
    per_query_lexical = plan.lexical_weight / len(plan.queries)
    prefetch: list[models.Prefetch] = []
    weights: list[float] = []
    for query_text, dense in zip(plan.queries, dense_vectors, strict=True):
        if plan.lexical_weight > 0:
            prefetch.append(
                models.Prefetch(
                    query=models.Document(
                        text=query_text[:MAX_TEXT_LENGTH],
                        model=settings.qdrant_sparse_model,
                    ),
                    using="bm25",
                    filter=query_filter,
                    limit=branch_limit,
                )
            )
            weights.append(per_query_lexical)
        if plan.dense_weight > 0 and dense is not None:
            prefetch.append(
                models.Prefetch(
                    query=dense,
                    using="dense",
                    filter=query_filter,
                    limit=branch_limit,
                )
            )
            weights.append(per_query_dense)
    return client.query_points(
        collection_name=collection,
        prefetch=prefetch,
        query=models.RrfQuery(rrf=models.Rrf(weights=weights)),
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
