from __future__ import annotations

from hashlib import sha256
import os


BACKFILL_VERSION = "20260728_answerai_colbert_small_v1"


def main() -> None:
    if os.getenv("ALLOW_QDRANT_RERANK_BACKFILL") != "1":
        raise SystemExit("Set ALLOW_QDRANT_RERANK_BACKFILL=1 for an approved cloud backfill")
    if os.getenv("QDRANT_RERANK_MODEL_IS_FREE", "").lower() != "true":
        raise SystemExit("QDRANT_RERANK_MODEL_IS_FREE=true is required")

    import psycopg
    from qdrant_client import QdrantClient, models

    database_url = os.environ["DATABASE_URL"]
    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_api_key = os.environ["QDRANT_API_KEY"]
    collection = os.getenv("QDRANT_RERANK_COLLECTION", "researchmate_chunks_v2")
    model = os.environ["QDRANT_RERANK_MODEL"]
    dimension = int(os.getenv("QDRANT_RERANK_DIMENSION", "96"))
    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        cloud_inference=True,
        timeout=120,
    )
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config={
                "multi": models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM
                    ),
                    hnsw_config=models.HnswConfigDiff(m=0),
                )
            },
        )

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            create table if not exists researchmate_vector_migrations (
              version text primary key,
              model text not null,
              chunk_count integer not null,
              checksum_sha256 text not null,
              applied_at timestamptz not null default now()
            )
            """
        )
        completed = connection.execute(
            """
            select chunk_count from researchmate_vector_migrations
            where version=%s and model=%s
            """,
            (BACKFILL_VERSION, model),
        ).fetchone()
        if completed is not None:
            print(
                f"Qdrant rerank backfill {BACKFILL_VERSION} already verified "
                f"for {completed[0]} chunks."
            )
            return
        rows = connection.execute(
            """
            select id,user_id,project_id,document_id,source_type,text
            from chunks
            where source_type='local_doc' and (expires_at is null or expires_at>now())
            order by created_at,id
            """
        ).fetchall()
    for offset in range(0, len(rows), 32):
        points = []
        for chunk_id, user_id, project_id, document_id, source_type, text in rows[offset : offset + 32]:
            points.append(
                models.PointStruct(
                    id=str(chunk_id),
                    vector={"multi": models.Document(text=text[:1200], model=model)},
                    payload={
                        "chunk_id": str(chunk_id),
                        "user_id": str(user_id),
                        "project_id": str(project_id),
                        "document_id": str(document_id) if document_id else None,
                        "source_type": str(source_type),
                    },
                )
            )
        client.upsert(collection_name=collection, points=points, wait=True)
    info = client.get_collection(collection)
    if int(info.points_count or 0) != len(rows):
        raise SystemExit("Qdrant rerank backfill count verification failed")
    if rows:
        sample_id, user_id, project_id, *_rest, sample_text = rows[0]
        sample = client.query_points(
            collection_name=collection,
            query=models.Document(text=sample_text[:1200], model=model),
            using="multi",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=str(user_id))
                    ),
                    models.FieldCondition(
                        key="project_id", match=models.MatchValue(value=str(project_id))
                    ),
                    models.HasIdCondition(has_id=[str(sample_id)]),
                ]
            ),
            limit=1,
        )
        if not sample.points or str(sample.points[0].id) != str(sample_id):
            raise SystemExit("Qdrant rerank tenant-filter sample verification failed")
    digest = sha256(
        "\n".join(str(row[0]) for row in rows).encode("utf-8")
    ).hexdigest()
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            insert into researchmate_vector_migrations(
              version,model,chunk_count,checksum_sha256
            ) values (%s,%s,%s,%s)
            on conflict (version) do update
            set model=excluded.model,
                chunk_count=excluded.chunk_count,
                checksum_sha256=excluded.checksum_sha256,
                applied_at=now()
            """,
            (BACKFILL_VERSION, model, len(rows), digest),
        )
        connection.commit()
    print(f"Backfilled {len(rows)} free late-interaction vectors into {collection}.")


if __name__ == "__main__":
    main()
