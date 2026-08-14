"""Provision, replay, and verify the shadow native-BM25 hybrid collection."""

from __future__ import annotations

import logging
import os
from hashlib import sha256
from typing import Any

LOGGER = logging.getLogger(__name__)

BACKFILL_VERSION = "20260809_native_bm25_dense_v1"
FILTER_INDEXES = ("user_id", "project_id", "document_id", "source_type")
BATCH_SIZE = 24


def main() -> None:
    """Run an explicitly approved resumable replay outside the API startup path."""
    if os.getenv("ALLOW_QDRANT_HYBRID_BACKFILL") != "1":
        raise SystemExit("Set ALLOW_QDRANT_HYBRID_BACKFILL=1 for an approved replay")

    import psycopg
    from openai import OpenAI
    from qdrant_client import QdrantClient, models

    database_url = os.environ["DATABASE_URL"]
    collection = os.getenv("QDRANT_HYBRID_COLLECTION", "researchmate_chunks_v3")
    sparse_model = os.getenv("QDRANT_SPARSE_MODEL", "qdrant/bm25")
    dense_model = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embed-v1")
    migration_model = f"{collection}:{dense_model}"
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "4096"))
    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        cloud_inference=True,
        timeout=180,
    )
    embedding = OpenAI(
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.environ["NVIDIA_API_KEY"],
        timeout=120,
        max_retries=2,
    )
    _ensure_collection(qdrant, models, collection, dimension)
    rows = _load_chunks(psycopg, database_url)
    digest = sha256(
        "\n".join(f"{row[0]}:{sha256(row[6].encode()).hexdigest()}" for row in rows).encode()
    ).hexdigest()
    if _already_verified(psycopg, database_url, migration_model, len(rows), digest):
        LOGGER.info("Hybrid replay already verified for %s chunks in %s.", len(rows), collection)
        return

    expected_ids: set[str] = set()
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset : offset + BATCH_SIZE]
        texts = [row[6] for row in batch]
        response = embedding.embeddings.create(
            model=dense_model,
            input=texts,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"},
        )
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        points = []
        for row, dense in zip(batch, vectors, strict=True):
            chunk_id, user_id, project_id, document_id, source_type, title, text = row[:7]
            expected_ids.add(str(chunk_id))
            points.append(
                models.PointStruct(
                    id=str(chunk_id),
                    vector={
                        "dense": dense,
                        "bm25": models.Document(text=text[:1200], model=sparse_model),
                    },
                    payload=_payload(row),
                )
            )
        qdrant.upsert(collection_name=collection, points=points, wait=True)
        LOGGER.info("replayed=%s/%s", min(offset + len(batch), len(rows)), len(rows))

    _remove_stale(qdrant, models, collection, expected_ids)
    _verify(qdrant, models, collection, rows, sparse_model)
    _record(psycopg, database_url, migration_model, len(rows), digest)
    qdrant.close()
    LOGGER.info(
        "Verified native hybrid shadow collection %s with %s chunks.", collection, len(rows)
    )


def _ensure_collection(
    qdrant: Any,  # SDK boundary has runtime-generated response types.
    models: Any,  # SDK model namespace is passed to keep optional imports inside main.
    collection: str,
    dimension: int,
) -> None:
    """Create the versioned collection and filter indexes idempotently."""
    if not qdrant.collection_exists(collection):
        qdrant.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": models.VectorParams(size=dimension, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
    info = qdrant.get_collection(collection)
    schema = getattr(info, "payload_schema", {}) or {}
    for field_name in FILTER_INDEXES:
        if field_name not in schema:
            qdrant.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )


def _load_chunks(
    psycopg: Any,  # Database driver is an optional script-only dependency.
    database_url: str,
) -> list[tuple[Any, ...]]:
    """Load the current authorized source projection in deterministic identity order."""
    with psycopg.connect(database_url) as connection:
        return connection.execute(
            """
            select c.id,c.user_id,c.project_id,c.document_id,c.source_type,c.source_title,c.text,
                   c.page_no,c.slide_no,c.section_title,c.section_path,c.chunk_index,
                   c.char_start,c.char_end,c.metadata
            from chunks c
            join documents d on d.id=c.document_id and d.user_id=c.user_id
            where c.source_type='local_doc' and d.status='ready' and d.deleted_at is null
              and (c.expires_at is null or c.expires_at>now())
            order by c.id
            """
        ).fetchall()


def _payload(row: tuple[Any, ...]) -> dict[str, object]:
    """Map a database row to the production vector payload contract."""
    metadata = row[14] if isinstance(row[14], dict) else {}
    return {
        "chunk_id": str(row[0]),
        "user_id": str(row[1]),
        "project_id": str(row[2]),
        "document_id": str(row[3]) if row[3] else None,
        "source_type": str(row[4]),
        "title": row[5],
        "page_no": row[7],
        "slide_no": row[8],
        "section_title": row[9],
        "section_path": row[10] or [],
        "chunk_index": row[11],
        "char_start": row[12],
        "char_end": row[13],
        "source_anchors": metadata.get("source_anchors", []),
    }


def _remove_stale(
    qdrant: Any,  # SDK boundary has runtime-generated response types.
    models: Any,  # SDK model namespace is passed to keep optional imports inside main.
    collection: str,
    expected: set[str],
) -> None:
    """Reconcile points deleted after an earlier resumable replay batch."""
    offset = None
    stale: list[str] = []
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        stale.extend(str(point.id) for point in points if str(point.id) not in expected)
        if offset is None:
            break
    if stale:
        qdrant.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=stale),
            wait=True,
        )


def _verify(
    qdrant: Any,  # SDK boundary has runtime-generated response types.
    models: Any,  # SDK model namespace is passed to keep optional imports inside main.
    collection: str,
    rows: list[tuple[Any, ...]],
    model: str,
) -> None:
    """Verify exact count and one owner-filtered native BM25 sample."""
    if int(qdrant.count(collection_name=collection, exact=True).count) != len(rows):
        raise SystemExit("Hybrid replay count verification failed")
    if not rows:
        return
    row = rows[0]
    result = qdrant.query_points(
        collection_name=collection,
        query=models.Document(text=row[6][:1200], model=model),
        using="bm25",
        query_filter=models.Filter(
            must=[
                models.FieldCondition(key="user_id", match=models.MatchValue(value=str(row[1]))),
                models.FieldCondition(key="project_id", match=models.MatchValue(value=str(row[2]))),
                models.HasIdCondition(has_id=[str(row[0])]),
            ]
        ),
        limit=1,
    )
    if not result.points or str(result.points[0].id) != str(row[0]):
        raise SystemExit("Hybrid replay owner-filtered sample verification failed")


def _already_verified(
    psycopg: Any,  # Database driver is an optional script-only dependency.
    database_url: str,
    migration_model: str,
    count: int,
    digest: str,
) -> bool:
    """Skip only an identical corpus fingerprint, never a version label alone."""
    with psycopg.connect(database_url) as connection:
        _ensure_migration_table(connection)
        row = connection.execute(
            """select chunk_count,checksum_sha256 from researchmate_vector_migrations
               where version=%s and model=%s""",
            (BACKFILL_VERSION, migration_model),
        ).fetchone()
        return row == (count, digest)


def _record(
    psycopg: Any,  # Database driver is an optional script-only dependency.
    database_url: str,
    migration_model: str,
    count: int,
    digest: str,
) -> None:
    """Persist the verified corpus fingerprint as release evidence."""
    with psycopg.connect(database_url) as connection:
        _ensure_migration_table(connection)
        connection.execute(
            """
            insert into researchmate_vector_migrations(version,model,chunk_count,checksum_sha256)
            values (%s,%s,%s,%s)
            on conflict (version) do update set model=excluded.model,
              chunk_count=excluded.chunk_count,checksum_sha256=excluded.checksum_sha256,
              applied_at=now()
            """,
            (BACKFILL_VERSION, migration_model, count, digest),
        )
        connection.commit()


def _ensure_migration_table(
    connection: Any,  # Psycopg connection is kept opaque at the script boundary.
) -> None:
    """Create the shared replay ledger when an older environment lacks it."""
    connection.execute(
        """
        create table if not exists researchmate_vector_migrations (
          version text primary key, model text not null, chunk_count integer not null,
          checksum_sha256 text not null, applied_at timestamptz not null default now()
        )
        """
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
