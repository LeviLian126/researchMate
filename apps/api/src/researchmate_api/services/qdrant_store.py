"""Own tenant-filtered Qdrant hybrid retrieval and vector projection operations."""

from __future__ import annotations

import logging
from hashlib import sha256
from typing import Any, cast

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Condition, ExtendedPointId

from researchmate_api.config import Settings
from researchmate_api.schemas.common import MAX_TEXT_LENGTH, SourceType
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.qdrant_errors import (
    VectorStoreRequestError,
    raise_vector_store_error,
)
from researchmate_api.services.qdrant_hybrid_query import execute_hybrid_query
from researchmate_api.services.qdrant_projection import (
    build_owner_filter,
    delete_stale_points,
    legacy_sparse_text_vector,
    snapshot_stale_points,
)
from researchmate_api.services.query_planning import RetrievalPlan, RetrievalRoute
from researchmate_api.services.store import ChunkEntry

LOGGER = logging.getLogger(__name__)
__all__ = ["QdrantHybridStore", "VectorStoreRequestError"]


class QdrantHybridStore:
    """Enforce owner filters around hybrid Qdrant queries and mutations."""

    owner_filter = staticmethod(build_owner_filter)

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
            timeout=round(settings.llm_timeout_seconds),
            cloud_inference=True,
        )

    def query(
        self,
        *,
        user_id: str,
        project_id: str,
        source_type: SourceType | str,
        text: str,
        limit: int = 10,
        document_ids: list[str] | None = None,
        plan: RetrievalPlan | None = None,
    ) -> list[dict[str, Any]]:
        """Fuse native BM25 and dense variants inside one owner-scoped Qdrant query."""
        effective_plan = plan or RetrievalPlan(
            route=RetrievalRoute.HYBRID,
            queries=(text,),
            dense_weight=0.5,
            lexical_weight=0.5,
            reason="adapter_default",
        )
        query_filter = self.owner_filter(user_id, project_id, source_type, document_ids)
        try:
            result = execute_hybrid_query(
                self.client,
                self.embedding,
                self.settings,
                self.collection,
                effective_plan,
                query_filter,
                limit=limit,
            )
        except Exception as exc:
            raise_vector_store_error("query", exc)
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
        query_filter = self.owner_filter(user_id, project_id, source_type, document_ids)
        try:
            dense = self.embedding.embed([text], input_type="query")[0]
            result = self.client.query_points(
                collection_name=self.collection,
                query=dense,
                using="dense",
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise_vector_store_error("dense_query", exc)
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
        # must may be a single Condition, list, or None; normalize to a list to append safely.
        base_must: list[Condition] = (
            list(query_filter.must)
            if isinstance(query_filter.must, list)
            else ([query_filter.must] if query_filter.must is not None else [])
        )
        base_must.append(models.HasIdCondition(has_id=cast(list[ExtendedPointId], candidate_ids)))
        query_filter = models.Filter(must=base_must)
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
            raise_vector_store_error("rerank", exc)
        return [str((point.payload or {}).get("chunk_id", point.id)) for point in result.points]

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
        try:
            primary_previous = snapshot_stale_points(
                self.client, self.collection, chunks, self.owner_filter
            )
            rerank_previous = (
                snapshot_stale_points(
                    self.client, self.rerank_collection, chunks, self.owner_filter
                )
                if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free
                else set()
            )
        except Exception as exc:
            raise_vector_store_error("stale_scan", exc)
        dense_vectors = self.embedding.embed([chunk.text for chunk in chunks], input_type="passage")
        points = []
        for chunk, dense in zip(chunks, dense_vectors, strict=True):
            points.append(
                models.PointStruct(
                    id=str(chunk.id),
                    vector=(
                        {
                            "dense": dense,
                            "bm25": models.Document(
                                text=chunk.text[:MAX_TEXT_LENGTH],
                                model=self.settings.qdrant_sparse_model,
                            ),
                        }
                        if self.settings.qdrant_native_hybrid_enabled
                        else {
                            "dense": dense,
                            "sparse": legacy_sparse_text_vector(chunk.text),
                        }
                    ),
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
                        "section_title": chunk.section_title,
                        "section_path": list(chunk.section_path),
                        "chunk_index": chunk.chunk_index,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "source_anchors": chunk.metadata.get("source_anchors", []),
                        "content_hash": sha256(chunk.text.encode("utf-8")).hexdigest(),
                        "pipeline_version": pipeline_version,
                    },
                )
            )
        try:
            self.client.upsert(collection_name=self.collection, points=points, wait=True)
        except Exception as exc:
            raise_vector_store_error("upsert", exc)
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
                raise_vector_store_error("rerank_upsert", exc)
        try:
            delete_stale_points(self.client, self.collection, primary_previous, chunks)
            if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
                delete_stale_points(self.client, self.rerank_collection, rerank_previous, chunks)
        except Exception as exc:
            raise_vector_store_error("stale_delete", exc)

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
            must=cast(
                list[Condition],
                [
                    models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
                    models.FieldCondition(
                        key="project_id", match=models.MatchValue(value=project_id)
                    ),
                    models.HasIdCondition(has_id=cast(list[ExtendedPointId], point_ids)),
                ],
            )
        )
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.FilterSelector(filter=owner_filter),
                wait=True,
            )
        except Exception as exc:
            raise_vector_store_error("delete", exc)
        if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
            try:
                self.client.delete(
                    collection_name=self.rerank_collection,
                    points_selector=models.FilterSelector(filter=owner_filter),
                    wait=True,
                )
            except Exception as exc:
                raise_vector_store_error("rerank_delete", exc)

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
            raise_vector_store_error("project_delete", exc)
        if self.settings.qdrant_rerank_model and self.settings.qdrant_rerank_model_is_free:
            try:
                self.client.delete(
                    collection_name=self.rerank_collection,
                    points_selector=models.FilterSelector(filter=owner_filter),
                    wait=True,
                )
            except Exception as exc:
                raise_vector_store_error("rerank_project_delete", exc)
