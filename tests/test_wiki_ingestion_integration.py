"""Verify incremental Wiki generation state at the ingestion service boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.store import ChunkEntry
from researchmate_worker.ingestion import (
    DocumentIngestionService,
    IngestionEvent,
    IngestionRecord,
    PageProjection,
    ParsedBlock,
    WikiProjectState,
)

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("20000000-0000-4000-8000-000000000001")
DOCUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
EVENT = IngestionEvent(
    job_id=UUID("50000000-0000-4000-8000-000000000001"),
    user_id=USER_ID,
    project_id=PROJECT_ID,
    document_id=DOCUMENT_ID,
)


@dataclass
class IncrementalStore:
    """Record separate raw and affected-Wiki persistence inputs."""

    state: WikiProjectState = field(
        default_factory=lambda: WikiProjectState(
            chunks=[], knowledge_generation=10, wiki_generation=10
        )
    )
    raw_chunks: list[ChunkEntry] = field(default_factory=list)
    wiki_chunks: list[ChunkEntry] | None = None
    base_generation: int | None = None
    ready: bool = False

    def claim(
        self, event: IngestionEvent, *, worker_id: str, lease_seconds: int
    ) -> IngestionRecord:
        return IngestionRecord(
            job_id=event.job_id,
            user_id=event.user_id,
            project_id=event.project_id,
            document_id=event.document_id,
            filename="source.pdf",
            file_type="pdf",
            r2_object_key="source.pdf",
            checksum_sha256=None,
            attempts=1,
        )

    def load_wiki_state(self, record: IngestionRecord) -> WikiProjectState:
        return self.state

    def replace_content(
        self,
        record: IngestionRecord,
        *,
        worker_id: str,
        pages: list[PageProjection],
        chunks: list[ChunkEntry],
        pipeline_version: str,
        wiki_chunks: list[ChunkEntry] | None,
        base_knowledge_generation: int,
        recovered_wiki_generation: int | None = None,
    ) -> None:
        self.raw_chunks = chunks
        self.wiki_chunks = wiki_chunks
        self.base_generation = base_knowledge_generation

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None:
        self.ready = True

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        raise AssertionError(code)

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        raise AssertionError(code)


class ObjectReader:
    """Write a bounded local source fixture."""

    def download_to_file(self, object_key: str, destination: Path) -> None:
        destination.write_bytes(b"source")


class Parser:
    """Return one raw block for the ingestion proof."""

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        return [ParsedBlock(text="Hybrid retrieval uses lexical and semantic search.")]


class VectorProjection:
    """Reject unexpected vector work for the lightweight fixture."""

    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None:
        raise AssertionError("lightweight fixture must not enter vector projection")


class IncrementalCompiler:
    """Return one affected canonical page and record the generation contract."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.generation: int | None = None

    def compile_index(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
        existing_chunks: list[ChunkEntry],
        generation: int,
    ) -> list[ChunkEntry]:
        self.generation = generation
        if self.fail:
            raise RuntimeError("provider unavailable")
        return [
            ChunkEntry(
                id=UUID("60000000-0000-4000-8000-000000000001"),
                user_id=user_id,
                project_id=project_id,
                document_id=None,
                source_type=SourceType.LOCAL_DOC,
                source_title="Hybrid Retrieval",
                text="Canonical page",
                has_vector=False,
                metadata={"wiki_mode": True, "wiki_source_chunk_ids": [str(chunks[0].id)]},
            )
        ]


def _service(
    store: IncrementalStore, compiler: IncrementalCompiler | None
) -> DocumentIngestionService:
    return DocumentIngestionService(
        store=store,
        object_reader=ObjectReader(),
        parser=Parser(),
        vector_projection=VectorProjection(),
        pipeline_version="v1",
        lease_seconds=120,
        max_attempts=3,
        max_upload_bytes=1024,
        wiki_compiler=compiler,
    )


def test_incremental_ingestion_separates_raw_and_affected_wiki_writes() -> None:
    store = IncrementalStore()
    compiler = IncrementalCompiler()

    result = _service(store, compiler).handle(EVENT, worker_id="worker")

    assert result == "succeeded"
    assert store.ready is True
    assert compiler.generation == 11
    assert store.base_generation == 10
    assert store.wiki_chunks is not None and len(store.wiki_chunks) == 1
    assert all(chunk.metadata["knowledge_role"] == "raw_evidence" for chunk in store.raw_chunks)
    assert all(chunk.metadata.get("wiki_mode") is not True for chunk in store.raw_chunks)


def test_wiki_failure_persists_raw_with_no_wiki_update() -> None:
    store = IncrementalStore()
    compiler = IncrementalCompiler(fail=True)

    result = _service(store, compiler).handle(EVENT, worker_id="worker")

    assert result == "succeeded"
    assert store.ready is True
    assert store.raw_chunks
    assert store.wiki_chunks is None


def test_unconfigured_wiki_compiler_keeps_wiki_generation_stale() -> None:
    store = IncrementalStore()

    result = _service(store, None).handle(EVENT, worker_id="worker")

    assert result == "succeeded"
    assert store.raw_chunks
    assert store.wiki_chunks is None


def test_stale_ingestion_compensates_missing_documents_before_current_document() -> None:
    missing_document = UUID("30000000-0000-4000-8000-000000000002")
    missing = ChunkEntry(
        id=UUID("40000000-0000-4000-8000-000000000002"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=missing_document,
        source_type=SourceType.LOCAL_DOC,
        source_title="Missing source",
        text="Missed knowledge",
        metadata={"knowledge_generation": 11},
    )
    store = IncrementalStore(
        state=WikiProjectState(
            knowledge_generation=11,
            wiki_generation=10,
            pending_chunks=[missing],
        )
    )

    class RecoveryCompiler(IncrementalCompiler):
        def __init__(self) -> None:
            super().__init__()
            self.documents: list[UUID] = []
            self.existing_counts: list[int] = []

        def compile_index(
            self,
            chunks: list[ChunkEntry],
            *,
            filename: str,
            user_id: UUID,
            project_id: UUID,
            document_id: UUID,
            existing_chunks: list[ChunkEntry],
            generation: int,
        ) -> list[ChunkEntry]:
            self.documents.append(document_id)
            self.existing_counts.append(len(existing_chunks))
            return super().compile_index(
                chunks,
                filename=filename,
                user_id=user_id,
                project_id=project_id,
                document_id=document_id,
                existing_chunks=existing_chunks,
                generation=generation,
            )

    compiler = RecoveryCompiler()
    assert _service(store, compiler).handle(EVENT, worker_id="worker") == "succeeded"
    assert compiler.documents == [missing_document, DOCUMENT_ID]
    assert compiler.existing_counts == [0, 1]
    assert store.base_generation == 11
