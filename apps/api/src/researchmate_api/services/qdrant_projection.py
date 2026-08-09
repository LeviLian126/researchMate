"""Reconcile document-scoped vector projections after deterministic re-ingestion."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from hashlib import sha256
from math import log1p
from typing import Any, cast

from qdrant_client import models
from qdrant_client.http.models import Condition, ExtendedPointId

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.retrieval import tokenize
from researchmate_api.services.store import ChunkEntry

OwnerFilterFactory = Callable[[str, str, SourceType | str, list[str] | None], models.Filter]


def build_owner_filter(
    user_id: str,
    project_id: str,
    source_type: SourceType | str,
    document_ids: list[str] | None = None,
) -> models.Filter:
    """Build the mandatory owner, project, source, and optional document filter."""
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


def legacy_sparse_text_vector(text: str) -> models.SparseVector:
    """Preserve the rollback collection's deterministic hashed sparse contract."""
    counts = Counter(tokenize(text))
    indexed = sorted(
        (
            (int.from_bytes(sha256(token.encode()).digest()[:4], "big"), 1.0 + log1p(count))
            for token, count in counts.items()
        ),
        key=lambda item: item[0],
    )
    return models.SparseVector(
        indices=[item[0] for item in indexed],
        values=[item[1] for item in indexed],
    )


def snapshot_stale_points(
    client: Any,  # Qdrant SDK clients and test doubles share no stable public protocol.
    collection: str,
    chunks: list[ChunkEntry],
    owner_filter: OwnerFilterFactory,
) -> set[str]:
    """Read previous point identities for the single document represented by a batch."""
    document_ids = {str(chunk.document_id) for chunk in chunks if chunk.document_id is not None}
    if len(document_ids) != 1:
        return set()
    scroll = getattr(client, "scroll", None)
    if scroll is None:
        return set()
    first = chunks[0]
    query_filter = owner_filter(
        str(first.user_id),
        str(first.project_id),
        SourceType.LOCAL_DOC,
        list(document_ids),
    )
    previous: set[str] = set()
    offset: object | None = None
    while True:
        points, offset = scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        previous.update(str(point.id) for point in points)
        if offset is None:
            return previous


def delete_stale_points(
    client: Any,  # Qdrant SDK clients and test doubles share no stable public protocol.
    collection: str,
    stale_ids: set[str],
    chunks: list[ChunkEntry],
) -> None:
    """Delete only old identities after every replacement projection was written."""
    current = {str(chunk.id) for chunk in chunks}
    targets = sorted(stale_ids - current)
    if not targets:
        return
    first = chunks[0]
    selector = models.FilterSelector(
        filter=models.Filter(
            must=cast(
                list[Condition],
                [
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=str(first.user_id))
                    ),
                    models.FieldCondition(
                        key="project_id", match=models.MatchValue(value=str(first.project_id))
                    ),
                    models.HasIdCondition(has_id=cast(list[ExtendedPointId], targets)),
                ],
            )
        )
    )
    client.delete(collection_name=collection, points_selector=selector, wait=True)
