"""Own tenant-filtered Qdrant hybrid retrieval and vector projection operations."""

from __future__ import annotations

import logging
from collections import Counter
from hashlib import sha256
from math import log1p
from typing import Any

from qdrant_client import QdrantClient, models
from researchmate_api.config import Settings
from researchmate_api.schemas.common import MAX_TEXT_LENGTH, SourceType
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.retrieval import tokenize
from researchmate_api.services.store import ChunkEntry

LOGGER = logging.getLogger(__name__)


class VectorStoreRequestError(RuntimeError):
    """Normalize vector-store failures and their retryability."""

    def __init__(self, operation: str, *, retryable: bool = True) -> None:
        super().__init__(f"Vector store {operation} failed")
        self.operation = operation
        self.retryable = retryable


def sparse_text_vector(text: str) -> models.SparseVector:
    """Build a deterministic sorted sparse vector from lexical tokens."""
    counts = Counter(tokenize(text))
    indexed = sorted(
        (
            (int.from_bytes(sha256(token.encode("utf-8")).digest()[:4], "big"), 1.0 + log1p(count))
            for token, count in counts.items()
        ),
        key=lambda item: item[0],
    )
    return models.SparseVector(
        indices=[item[0] for item in indexed],
        values=[item[1] for item in indexed],
    )


class QdrantHybridStore:
    """Enforce owner filters around hybrid Qdrant queries and mutations."""

    def __init__(
        self,
        settings: Settings,
        embedding: NvidiaEmbeddingProvider,
        client: Any | None = None,
    ) -> None:
        if not settings.qdrant_url:
            raise ValueError("Qdrant URL is not configured")
        self.settings = settings
        self.collection = settings.qdrant_collection
        self.rerank_collection = settings.qdrant_rerank_collection
        self.embedding = embedding
        self.client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            timeout=settings.llm_timeout_seconds,
            cloud_inference=bool(settings.qdrant_rerank_model),
        )

    @staticmethod
    def owner_filter(
        user_id: str,
        project_id: str,
        source_type: SourceType | str,
        document_ids: list[str] | None = None,
    ) -> models.Filter:
        """Build the mandatory owner, project, source, and document filter."""
        source_value = source_type.value if isinstance(source_type, SourceType) else source_type
        conditions: list[Any] = [
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
            models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id)),
            models.FieldCondition(key="source_type", match=models.MatchValue(value=source_value)),
        ]
        if document_ids:
            conditions.append(
                models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))
            )
        return models.Filter(must=conditions)

    def query(
        self,
        *,
        user_id: str,
        project_id: str,
        source_type: SourceType | str,
        text: str,
        limit: int = 10,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fuse dense and sparse channels inside an owner-scoped query."""
        dense = self.embedding.embed([text], input_type="query")[0]
        query_filter = self.owner_filter(user_id, project_id, source_type, document_ids)
        try:
            result = self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    models.Prefetch(
                        query=sparse_text_vector(text),
                        using="sparse",
                        filter=query_filter,
                        limit=max(limit * 3, 20),
                    ),
                    models.Prefetch(
                        query=dense,
                        using="dense",
                        filter=query_filter,
                        limit=max(limit * 3, 20),
                    ),
                ],
                query=models.RrfQuery(rrf=models.Rrf()),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreRequestError("query") from exc
        return [
            {"id": str(point.id), "score": point.score, "payload": dict(point.payload or {})}
            for point in result.points
        ]

    def query_dense(
        self,
        *,
        user_id: str,
        project_id: str,
        source_type: SourceType | str,
        text: str,
        limit: int = 30,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the semantic channel only; application BM25 is fused separately."""
        dense = self.embedding.embed([text], input_type="query")[0]
        query_filter = self.owner_filter(user_id, project_id, source_type, document_ids)
        try:
            result = self.client.query_points(
                collection_name=self.collection,
                query=dense,
                using="dense",
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreRequestError("dense_query") from exc
        return [
            {"id": str(point.id), "score": point.score, "payload": dict(point.payload or {})}
            for point in result.points
        ]

    def rerank_query(
        self,
        *,
        user_id: str,
        project_id: str,
        text: str,
        candidate_ids: list[str],
        model: str,
        limit: int,
    ) -> list[str]:
        """Rerank an allowlist of owner-scoped candidate identifiers."""
        if not candidate_ids:
            return []
        query_filter = self.owner_filter(user_id, project_id, SourceType.LOCAL_DOC)
        query_filter.must.append(models.HasIdCondition(has_id=candidate_ids))
        try:
            result = self.client.query_points(
                collection_name=self.rerank_collection,
                query=models.Document(text=text[:MAX_TEXT_LENGTH], model=model),
                using="multi",
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreRequestError("rerank") from exc
        return [str(point.payload.get("chunk_id", point.id)) for point in result.points]

    def rerank_ready(self) -> bool:
        """Check that the optional rerank collection is configured and complete."""
        if not self.settings.qdrant_rerank_model or not self.settings.qdrant_rerank_model_is_free:
            return False
        try:
            info = self.client.get_collection(self.rerank_collection)
        except Exception as exc:
            LOGGER.warning("rerank_collection_check_failed error=%s", type(exc).__name__)
            return False
        vectors = getattr(getattr(info.config, "params", None), "vectors", None)
        if not isinstance(vectors, dict) or "multi" not in vectors:
            return False
        try:
            primary_count = int(
                self.client.count(
                    collection_name=self.collection,
                    exact=True,
                ).count
            )
            rerank_count = int(
                self.client.count(
                    collection_name=self.rerank_collection,
                    exact=True,
                ).count
            )
        except Exception as exc:
            LOGGER.warning("rerank_count_check_failed error=%s", type(exc).__name__)
            return False
        return primary_count > 0 and rerank_count == primary_count

    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None:
        """Project chunks into owner-tagged dense, sparse, and rerank vectors."""
        if not chunks:
            return
        dense_vectors = self.embedding.embed([chunk.text for chunk in chunks], input_type="passage")
        points = []
        for chunk, dense in zip(chunks, dense_vectors, strict=True):
            points.append(
                models.PointStruct(
                    id=str(chunk.id),
                    vector={"dense": dense, "sparse": sparse_text_vector(chunk.text)},
                    payload={
                        "user_id": str(chunk.user_id),
                        "project_id": str(chunk.project_id),
                        "document_id": str(chunk.document_id) if chunk.document_id else None,
                        "chunk_id": str(chunk.id),
                        "source_type": chunk.source_type.value,
                        "page_no": chunk.page_no,
                        "slide_no": chunk.slide_no,
                        "title": chunk.source_title,
                        "url": chunk.url,
                        "content_hash": sha256(chunk.text.encode("utf-8")).hexdigest(),
                        "pipeline_version": pipeline_version,
                    },
                )
            )
        try:
            self.client.upsert(collection_name=self.collection, points=points, wait=True)
        except Exception as exc:
            raise VectorStoreRequestError("upsert") from exc
        if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
            rerank_points = [
                models.PointStruct(
                    id=str(chunk.id),
                    vector={
                        "multi": models.Document(
                            text=chunk.text[:MAX_TEXT_LENGTH],
                            model=self.settings.qdrant_rerank_model,
                        )
                    },
                    payload={
                        "user_id": str(chunk.user_id),
                        "project_id": str(chunk.project_id),
                        "document_id": str(chunk.document_id) if chunk.document_id else None,
                        "chunk_id": str(chunk.id),
                        "source_type": chunk.source_type.value,
                    },
                )
                for chunk in chunks
            ]
            try:
                self.client.upsert(
                    collection_name=self.rerank_collection,
                    points=rerank_points,
                    wait=True,
                )
            except Exception as exc:
                raise VectorStoreRequestError("rerank_upsert") from exc

    def delete_points(
        self,
        point_ids: list[str],
        *,
        user_id: str,
        project_id: str,
    ) -> None:
        """Delete selected points without crossing their owner boundary."""
        if not point_ids:
            return
        owner_filter = models.Filter(
            must=[
                models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
                models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id)),
                models.HasIdCondition(has_id=point_ids),
            ]
        )
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.FilterSelector(filter=owner_filter),
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreRequestError("delete") from exc
        if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
            try:
                self.client.delete(
                    collection_name=self.rerank_collection,
                    points_selector=models.FilterSelector(filter=owner_filter),
                    wait=True,
                )
            except Exception as exc:
                raise VectorStoreRequestError("rerank_delete") from exc

    def delete_project_points(self, *, user_id: str, project_id: str) -> None:
        """Delete every vector projection belonging to one owner's project."""
        owner_filter = models.Filter(
            must=[
                models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
                models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id)),
            ]
        )
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.FilterSelector(filter=owner_filter),
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreRequestError("project_delete") from exc
        if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
            try:
                self.client.delete(
                    collection_name=self.rerank_collection,
                    points_selector=models.FilterSelector(filter=owner_filter),
                    wait=True,
                )
            except Exception as exc:
                raise VectorStoreRequestError("rerank_project_delete") from exc
