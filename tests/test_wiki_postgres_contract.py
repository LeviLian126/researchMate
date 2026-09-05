"""Exercise ingestion SQL on isolated PostgreSQL temporary tables with rollback."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.store import ChunkEntry
from researchmate_worker.config import psycopg_database_url
from researchmate_worker.ingestion import IngestionRecord, SqlIngestionStore
from sqlalchemy import Connection, create_engine, text


def test_postgres_generation_cas_and_recovery_are_atomic() -> None:
    database_url = os.getenv("WIKI_DATABASE_TEST_URL")
    if not database_url:
        pytest.skip("hosted PostgreSQL contract requires WIKI_DATABASE_TEST_URL")
    engine = create_engine(psycopg_database_url(database_url), connect_args={"connect_timeout": 15})
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            for statement in [
                """create temporary table projects (
                    id uuid primary key, user_id uuid, status text, deleted_at timestamptz,
                    knowledge_generation bigint, wiki_generation bigint, updated_at timestamptz)""",
                """create temporary table documents (
                    id uuid primary key, user_id uuid, status text, deleted_at timestamptz,
                    parser text, updated_at timestamptz)""",
                """create temporary table jobs (
                    id uuid primary key, user_id uuid, project_id uuid, document_id uuid,
                    status text, lease_owner text, lease_expires_at timestamptz, progress int,
                    updated_at timestamptz)""",
                """create temporary table document_pages (
                    id uuid, document_id uuid, page_no int, slide_no int, section_title text,
                    text text, metadata jsonb)""",
                """create temporary table chunks (
                    id uuid primary key, user_id uuid, project_id uuid, document_id uuid,
                    source_type text, source_title text, page_no int, slide_no int,
                    section_title text, section_path text[], chunk_index int, char_start int,
                    char_end int, text text, token_count int, qdrant_point_id text,
                    has_vector boolean, metadata jsonb)""",
            ]:
                connection.execute(text(statement))
            user_id, project_id, document_id, job_id = (uuid4() for _ in range(4))
            identifiers = {
                "user": user_id,
                "project": project_id,
                "doc": document_id,
                "job": job_id,
            }
            connection.execute(
                text("insert into projects values (:project,:user,'active',null,10,10,now())"),
                identifiers,
            )
            connection.execute(
                text("insert into documents values (:doc,:user,'parsing',null,null,now())"),
                identifiers,
            )
            connection.execute(
                text("""insert into jobs values
                (:job,:user,:project,:doc,'running','test',now()+interval '10 minutes',0,now())"""),
                identifiers,
            )

            class TransactionEngine:
                @contextmanager
                def begin(self) -> Iterator[Connection]:
                    yield connection

            store = SqlIngestionStore(TransactionEngine())  # type: ignore[arg-type]
            record = IngestionRecord(
                job_id, user_id, project_id, document_id, "fixture.txt", "txt", "fixture", None, 1
            )
            wiki = ChunkEntry(
                uuid4(),
                user_id,
                project_id,
                None,
                SourceType.LOCAL_DOC,
                "Topic",
                "Fact",
                metadata={"wiki_mode": True},
            )

            def persist(base: int, *, recover: int | None = None, fail: bool = False) -> None:
                connection.execute(text("update documents set status='parsing'"))
                store.replace_content(
                    record,
                    worker_id="test",
                    pages=[],
                    chunks=[],
                    pipeline_version="fixture",
                    wiki_chunks=None if fail else [wiki],
                    base_knowledge_generation=base,
                    recovered_wiki_generation=recover,
                )

            def generations() -> tuple[int, int]:
                row = connection.execute(
                    text("select knowledge_generation,wiki_generation from projects")
                ).one()
                return int(row[0]), int(row[1])

            persist(10, fail=True)
            assert generations() == (11, 10)
            persist(11)
            assert generations() == (12, 10)
            assert connection.execute(text("select count(*) from chunks")).scalar_one() == 0
            persist(12, recover=10)
            assert generations() == (13, 13)
            assert connection.execute(text("select count(*) from chunks")).scalar_one() == 1
            persist(12, recover=13)
            assert generations() == (14, 13)
        finally:
            transaction.rollback()
    engine.dispose()
