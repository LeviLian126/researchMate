from hashlib import sha256
from uuid import UUID

import pytest

from researchmate_worker.ingestion import (
    DocumentIngestionService,
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    ParsedBlock,
)


EVENT = IngestionEvent(
    job_id=UUID("10000000-0000-4000-8000-000000000001"),
    user_id=UUID("10000000-0000-4000-8000-000000000002"),
    project_id=UUID("10000000-0000-4000-8000-000000000003"),
    document_id=UUID("10000000-0000-4000-8000-000000000004"),
)


class FakeStore:
    def __init__(self, checksum=None, attempts=1):
        self.record = IngestionRecord(
            **EVENT.model_dump(),
            filename="evidence.pdf",
            file_type="pdf",
            r2_object_key="private/evidence.pdf",
            checksum_sha256=checksum,
            attempts=attempts,
        )
        self.pages = []
        self.chunks = []
        self.ready = False
        self.retry = None
        self.failed = None

    def claim(self, event, *, worker_id, lease_seconds):
        assert event == EVENT
        assert worker_id == "worker-1"
        assert lease_seconds == 120
        return self.record

    def replace_content(self, record, *, worker_id, pages, chunks, pipeline_version):
        self.pages = pages
        self.chunks = chunks
        assert pipeline_version == "pipeline-v1"

    def mark_ready(self, record, *, worker_id):
        self.ready = True

    def mark_retryable(self, record, *, worker_id, code):
        self.retry = code

    def mark_failed(self, record, *, worker_id, code):
        self.failed = code


class FakeObjectReader:
    def __init__(self, content=b"source bytes"):
        self.content = content

    def download_to_file(self, object_key, destination):
        destination.write_bytes(self.content)


class FakeParser:
    def parse(self, source, *, file_type):
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
    def __init__(self, error=None):
        self.error = error
        self.chunks = []

    def upsert_chunks(self, chunks, *, pipeline_version):
        if self.error:
            raise self.error
        self.chunks = chunks
        assert pipeline_version == "pipeline-v1"


def service(store, *, reader=None, parser=None, vector=None):
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
    assert vector.chunks == store.chunks


def test_checksum_mismatch_is_terminal_and_never_reaches_parser() -> None:
    store = FakeStore(checksum="0" * 64)

    with pytest.raises(IngestionFailure) as failure:
        service(store).handle(EVENT, worker_id="worker-1")

    assert failure.value.code == "CHECKSUM_MISMATCH"
    assert failure.value.retryable is False
    assert store.failed == "CHECKSUM_MISMATCH"
    assert store.retry is None


def test_retryable_projection_failure_requeues_before_attempt_limit() -> None:
    from researchmate_api.services.qdrant_store import VectorStoreRequestError

    store = FakeStore(attempts=2)
    vector = FakeVectorProjection(error=VectorStoreRequestError("upsert", retryable=True))

    with pytest.raises(IngestionFailure) as failure:
        service(store, vector=vector).handle(EVENT, worker_id="worker-1")

    assert failure.value.retryable is True
    assert store.retry == "VECTOR_STORE_UNAVAILABLE"
    assert store.failed is None
