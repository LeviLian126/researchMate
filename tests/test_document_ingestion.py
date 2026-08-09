"""Verify ingestion state transitions and deterministic content projections."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from researchmate_api.services.store import ChunkEntry
from researchmate_worker.ingestion import (
    DocumentIngestionService,
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    PageProjection,
    ParsedBlock,
)

EVENT = IngestionEvent(
    job_id=UUID("10000000-0000-4000-8000-000000000001"),
    user_id=UUID("10000000-0000-4000-8000-000000000002"),
    project_id=UUID("10000000-0000-4000-8000-000000000003"),
    document_id=UUID("10000000-0000-4000-8000-000000000004"),
)


class FakeStore:
    """Record ingestion claims, projections, and lifecycle transitions."""

    def __init__(self, checksum: str | None = None, attempts: int = 1) -> None:
        self.record = IngestionRecord(
            **EVENT.model_dump(),
            filename="evidence.pdf",
            file_type="pdf",
            r2_object_key="private/evidence.pdf",
            checksum_sha256=checksum,
            attempts=attempts,
        )
        self.pages: list[PageProjection] = []
        self.chunks: list[ChunkEntry] = []
        self.ready = False
        self.retry = None
        self.failed = None

    def claim(
        self, event: IngestionEvent, *, worker_id: str, lease_seconds: int
    ) -> IngestionRecord:
        assert event == EVENT
        assert worker_id == "worker-1"
        assert lease_seconds == 120
        return self.record

    def replace_content(
        self,
        record: IngestionRecord,
        *,
        worker_id: str,
        pages: list[PageProjection],
        chunks: list[ChunkEntry],
        pipeline_version: str,
    ) -> None:
        self.pages = pages
        self.chunks = chunks
        assert pipeline_version == "pipeline-v1"

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None:
        self.ready = True

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        self.retry = code

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        self.failed = code


class FakeObjectReader:
    """Provide deterministic uploaded bytes to the ingestion service."""

    def __init__(self, content: bytes = b"source bytes") -> None:
        self.content = content

    def download_to_file(self, object_key: str, destination: Path) -> None:
        destination.write_bytes(self.content)


class FakeParser:
    """Return deterministic parsed pages for ingestion tests."""

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        assert source.read_bytes() == b"source bytes"
        assert file_type == "pdf"
        return [
            ParsedBlock(
                text="Evidence on page one.",
                page_no=1,
                section_title="Finding",
                metadata={"bbox": [0, 0, 10, 10]},
            )
        ]


class FakeVectorProjection:
    """Record vector upserts and inject configured projection failures."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.chunks: list[ChunkEntry] = []

    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None:
        if self.error:
            raise self.error
        self.chunks = chunks
        assert pipeline_version == "pipeline-v1"


def service(
    store: FakeStore,
    *,
    reader: FakeObjectReader | None = None,
    parser: FakeParser | None = None,
    vector: FakeVectorProjection | None = None,
) -> DocumentIngestionService:
    """Build an ingestion service from isolated test doubles."""
    return DocumentIngestionService(
        store=store,
        object_reader=reader or FakeObjectReader(),
        parser=parser or FakeParser(),
        vector_projection=vector or FakeVectorProjection(),
        pipeline_version="pipeline-v1",
        lease_seconds=120,
        max_attempts=3,
        max_upload_bytes=1024,
    )


def test_ingestion_builds_stable_page_and_chunk_projections() -> None:
    """Require deterministic page, chunk, and vector projections."""
    checksum = sha256(b"source bytes").hexdigest()
    store = FakeStore(checksum=checksum)
    vector = FakeVectorProjection()

    assert service(store, vector=vector).handle(EVENT, worker_id="worker-1") == "succeeded"
    assert store.ready is True
    assert len(store.pages) == 1
    assert store.pages[0].page_no == 1
    assert store.pages[0].metadata["pipeline_version"] == "pipeline-v1"
    assert len(store.chunks) == 1
    assert store.chunks[0].page_no == 1
    assert store.chunks[0].section_title == "Finding"
    assert store.chunks[0].section_path == ("Finding",)
    assert store.chunks[0].chunk_index == 0
    assert store.chunks[0].char_start == 0
    assert store.chunks[0].char_end == len("Evidence on page one.")
    assert vector.chunks == store.chunks


def test_checksum_mismatch_is_terminal_and_never_reaches_parser() -> None:
    """Reject corrupt uploads before parsing or projection."""
    store = FakeStore(checksum="0" * 64)

    with pytest.raises(IngestionFailure) as failure:
        service(store).handle(EVENT, worker_id="worker-1")

    assert failure.value.code == "CHECKSUM_MISMATCH"
    assert failure.value.retryable is False
    assert store.failed == "CHECKSUM_MISMATCH"
    assert store.retry is None


def test_retryable_projection_failure_requeues_before_attempt_limit() -> None:
    """Requeue transient projection failures below the attempt limit."""
    from researchmate_api.services.qdrant_store import VectorStoreRequestError

    store = FakeStore(attempts=2)
    vector = FakeVectorProjection(error=VectorStoreRequestError("upsert", retryable=True))

    with pytest.raises(IngestionFailure) as failure:
        service(store, vector=vector).handle(EVENT, worker_id="worker-1")

    assert failure.value.retryable is True
    assert store.retry == "VECTOR_STORE_UNAVAILABLE"
    assert store.failed is None
