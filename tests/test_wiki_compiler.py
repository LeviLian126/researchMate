"""Verify wiki compilation transforms lightweight chunks into structured pages.

Tests cover:
- WikiCompiler LLM call with schema-validated output
- wiki_pages_to_chunks conversion for retrieval compatibility
- WikiCompilationError on invalid LLM output
- Ingestion integration: wiki compilation replaces lightweight chunks
- WikiStoreMixin CRUD operations
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from researchmate_api.schemas.common import CurrentUser, SourceType
from researchmate_api.services._store_core import InMemoryStoreCore
from researchmate_api.services._store_models import WikiPage
from researchmate_api.services._store_wiki import WikiStoreMixin
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.wiki_compiler import (
    WikiCompilationError,
    WikiCompiler,
    wiki_pages_to_chunks,
)

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000002")
DOCUMENT_ID = UUID("10000000-0000-4000-8000-000000000003")


class FakeChatProvider:
    """Return a canned LLM response for wiki compiler tests."""

    def __init__(self, content: str) -> None:
        self._content = content

    def complete(self, messages) -> LLMResult:  # type: ignore[override]
        return LLMResult(
            content=self._content,
            reasoning=None,
            model="fake-model",
            prompt_tokens=10,
            completion_tokens=20,
        )


def _make_chunks(texts: list[str]) -> list[ChunkEntry]:
    """Create lightweight ChunkEntry objects from text fragments."""
    return [
        ChunkEntry(
            id=uuid4(),
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
            source_type=SourceType.LOCAL_DOC,
            source_title="test.pdf",
            text=text,
            chunk_index=index,
            has_vector=False,
        )
        for index, text in enumerate(texts)
    ]


# ---------------------------------------------------------------------------
# WikiCompiler: valid LLM output
# ---------------------------------------------------------------------------


def test_compile_valid_wiki_pages() -> None:
    """Verify the compiler produces WikiPage objects from valid LLM output."""
    llm_output = json.dumps(
        [
            {
                "title": "Apollo",
                "page_type": "project",
                "content": "Apollo is a migration project. See [[Phoenix]] for history.",
                "aliases": ["Phoenix v2"],
                "links": ["Phoenix"],
                "source_chunk_indices": [0, 1],
            },
            {
                "title": "Phoenix",
                "page_type": "reference",
                "content": "Phoenix was the predecessor system. See [[Apollo]].",
                "aliases": [],
                "links": ["Apollo"],
                "source_chunk_indices": [0],
            },
        ]
    )
    provider = FakeChatProvider(llm_output)
    compiler = WikiCompiler(provider)
    chunks = _make_chunks(["Apollo replaces Phoenix.", "The migration is ongoing."])
    pages = compiler.compile(
        chunks,
        filename="design.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )
    assert len(pages) == 2
    assert pages[0].title == "Apollo"
    assert pages[0].page_type == "project"
    assert "Phoenix" in pages[0].links
    assert len(pages[0].source_chunk_ids) == 2
    assert pages[1].title == "Phoenix"


# ---------------------------------------------------------------------------
# WikiCompiler: wikilink extraction from content
# ---------------------------------------------------------------------------


def test_wikilinks_extracted_from_content() -> None:
    """Verify [[wikilinks]] in content are extracted into the links list."""
    llm_output = json.dumps(
        [
            {
                "title": "Test Page",
                "page_type": "concept",
                "content": "Links to [[Alpha]] and [[Beta]] and [[Alpha]] again.",
                "aliases": [],
                "links": ["Gamma"],
                "source_chunk_indices": [0],
            },
        ]
    )
    provider = FakeChatProvider(llm_output)
    compiler = WikiCompiler(provider)
    chunks = _make_chunks(["Some text."])
    pages = compiler.compile(
        chunks,
        filename="test.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )
    assert len(pages) == 1
    links = pages[0].links
    assert "Alpha" in links
    assert "Beta" in links
    assert "Gamma" in links
    # Deduplicated
    assert links.count("Alpha") == 1


# ---------------------------------------------------------------------------
# WikiCompiler: invalid LLM output
# ---------------------------------------------------------------------------


def test_compile_invalid_json_raises_error() -> None:
    """Verify invalid JSON triggers WikiCompilationError."""
    provider = FakeChatProvider("not json at all")
    compiler = WikiCompiler(provider)
    chunks = _make_chunks(["text"])
    try:
        compiler.compile(
            chunks,
            filename="test.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )
        assert False, "Expected WikiCompilationError"
    except WikiCompilationError as exc:
        assert exc.code in ("INVALID_FORMAT", "JSON_PARSE_FAILED", "NOT_ARRAY")


def test_compile_empty_array_raises_error() -> None:
    """Verify an empty JSON array triggers WikiCompilationError."""
    provider = FakeChatProvider("[]")
    compiler = WikiCompiler(provider)
    chunks = _make_chunks(["text"])
    try:
        compiler.compile(
            chunks,
            filename="test.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )
        assert False, "Expected WikiCompilationError"
    except WikiCompilationError as exc:
        assert exc.code == "EMPTY_OUTPUT"


def test_compile_skips_invalid_proposals() -> None:
    """Verify proposals with out-of-range chunk indices are skipped."""
    llm_output = json.dumps(
        [
            {
                "title": "Valid Page",
                "page_type": "concept",
                "content": "Valid content.",
                "aliases": [],
                "links": [],
                "source_chunk_indices": [0],
            },
            {
                "title": "Invalid Page",
                "page_type": "concept",
                "content": "Invalid indices.",
                "aliases": [],
                "links": [],
                "source_chunk_indices": [99],
            },
        ]
    )
    provider = FakeChatProvider(llm_output)
    compiler = WikiCompiler(provider)
    chunks = _make_chunks(["one text"])
    pages = compiler.compile(
        chunks,
        filename="test.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )
    # Only the valid page survives; the invalid one is filtered out.
    assert len(pages) == 1
    assert pages[0].title == "Valid Page"


# ---------------------------------------------------------------------------
# wiki_pages_to_chunks: retrieval compatibility
# ---------------------------------------------------------------------------


def test_wiki_pages_to_chunks_preserves_metadata() -> None:
    """Verify wiki pages convert to ChunkEntry with wiki metadata."""
    page = WikiPage(
        id=uuid4(),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Test Wiki Page",
        page_type="concept",
        content="# Test Wiki Page\n\nSome content with [[links]].",
        aliases=["Alias1"],
        links=["links"],
        source_chunk_ids=[uuid4()],
    )
    chunks = wiki_pages_to_chunks([page])
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.source_title == "Test Wiki Page"
    assert chunk.has_vector is False
    assert chunk.metadata["wiki_mode"] is True
    assert chunk.metadata["wiki_type"] == "concept"
    assert "links" in chunk.metadata["wiki_links"]
    assert chunk.metadata["wiki_aliases"] == ["Alias1"]


# ---------------------------------------------------------------------------
# WikiStoreMixin: in-memory CRUD
# ---------------------------------------------------------------------------


class TestStore(WikiStoreMixin, InMemoryStoreCore):
    """Compose wiki mixin with core for isolated testing."""

    __test__ = False


def test_wiki_store_crud() -> None:
    """Verify wiki page store, retrieve, and delete operations."""
    store = TestStore()
    user = CurrentUser(id=USER_ID)
    page = WikiPage(
        id=uuid4(),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="CRUD Test",
        page_type="reference",
        content="Content.",
    )
    store.store_wiki_pages([page])
    assert len(store.project_wiki_pages(user, PROJECT_ID)) == 1
    assert len(store.document_wiki_pages(user, DOCUMENT_ID)) == 1
    store.delete_document_wiki_pages(DOCUMENT_ID)
    assert len(store.project_wiki_pages(user, PROJECT_ID)) == 0


def test_wiki_store_reset_clears_pages() -> None:
    """Verify reset() clears the wiki_pages dict."""
    store = TestStore()
    page = WikiPage(
        id=uuid4(),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Reset Test",
        page_type="reference",
        content="Content.",
    )
    store.store_wiki_pages([page])
    assert len(store.wiki_pages) == 1
    store.reset()
    assert len(store.wiki_pages) == 0


# ---------------------------------------------------------------------------
# Ingestion integration: wiki compilation replaces lightweight chunks
# ---------------------------------------------------------------------------


def _make_wiki_compiler_provider(pages: list[dict]) -> FakeChatProvider:
    """Create a fake provider that returns the given wiki page proposals as JSON."""
    return FakeChatProvider(json.dumps(pages))


def test_ingestion_wiki_compilation_replaces_chunks() -> None:
    """Verify lightweight ingestion with wiki compiler produces wiki-form chunks."""
    from researchmate_worker.ingestion_models import (
        IngestionEvent,
        IngestionRecord,
    )
    from researchmate_worker.ingestion_service import DocumentIngestionService

    event = IngestionEvent(
        job_id=UUID("20000000-0000-4000-8000-000000000001"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    class WikiTestStore:
        def __init__(self) -> None:
            self.record = IngestionRecord(
                job_id=event.job_id,
                user_id=event.user_id,
                project_id=event.project_id,
                document_id=event.document_id,
                filename="lightweight.pdf",
                file_type="pdf",
                r2_object_key="private/lightweight.pdf",
                checksum_sha256=None,
                attempts=1,
            )
            self.stored_chunks: list[ChunkEntry] = []

        def claim(self, event, *, worker_id, lease_seconds):
            return self.record

        def replace_content(self, record, *, worker_id, pages, chunks, pipeline_version):
            self.stored_chunks = chunks

        def mark_ready(self, record, *, worker_id):
            pass

        def mark_retryable(self, record, *, worker_id, code):
            pass

        def mark_failed(self, record, *, worker_id, code):
            pass

    class FakeObjectReader:
        def download_to_file(self, object_key, destination):
            destination.write_text("Lightweight document about Apollo and Phoenix migration.")

    class FakeParser:
        def parse(self, source, *, file_type):
            return [
                type(
                    "ParsedBlock",
                    (),
                    {
                        "text": "Apollo replaces Phoenix in the migration.",
                        "page_no": 1,
                        "slide_no": None,
                        "section_title": "Overview",
                        "metadata": {},
                    },
                )(),
                type(
                    "ParsedBlock",
                    (),
                    {
                        "text": "The payment database is migrated by Alice.",
                        "page_no": 1,
                        "slide_no": None,
                        "section_title": "Details",
                        "metadata": {},
                    },
                )(),
            ]

    class FakeVectorProjection:
        def upsert_chunks(self, chunks, *, pipeline_version):
            pass

    llm_output = json.dumps(
        [
            {
                "title": "Apollo Migration",
                "page_type": "project",
                "content": "# Apollo Migration\n\nApollo replaces [[Phoenix]]. See [[Alice]].",
                "aliases": [],
                "links": ["Phoenix", "Alice"],
                "source_chunk_indices": [0, 1],
            },
        ]
    )
    provider = FakeChatProvider(llm_output)
    wiki_compiler = WikiCompiler(provider)

    # Wrap to match the worker WikiCompiler protocol (returns ChunkEntry)
    class WorkerWikiAdapter:
        def compile(self, chunks, *, filename, user_id, project_id, document_id):
            pages = wiki_compiler.compile(
                chunks,
                filename=filename,
                user_id=user_id,
                project_id=project_id,
                document_id=document_id,
            )
            return wiki_pages_to_chunks(pages)

    test_store = WikiTestStore()
    service = DocumentIngestionService(
        store=test_store,  # type: ignore[arg-type]
        object_reader=FakeObjectReader(),  # type: ignore[arg-type]
        parser=FakeParser(),  # type: ignore[arg-type]
        vector_projection=FakeVectorProjection(),  # type: ignore[arg-type]
        pipeline_version="test-v1",
        lease_seconds=300,
        max_attempts=3,
        max_upload_bytes=10_000_000,
        lightweight_token_threshold=4000,
        wiki_compiler=WorkerWikiAdapter(),  # type: ignore[arg-type]
    )
    result = service.handle(event, worker_id="test-worker")
    assert result == "succeeded"
    # Wiki-compiled chunks should have wiki_mode metadata
    assert len(test_store.stored_chunks) > 0
    chunk = test_store.stored_chunks[0]
    assert chunk.metadata.get("wiki_mode") is True
    assert chunk.has_vector is False
    assert "Apollo" in chunk.source_title


def test_ingestion_wiki_fallback_on_failure() -> None:
    """Verify ingestion falls back to raw chunks when wiki compilation fails."""
    from researchmate_worker.ingestion_models import (
        IngestionEvent,
        IngestionRecord,
    )
    from researchmate_worker.ingestion_service import DocumentIngestionService

    event = IngestionEvent(
        job_id=UUID("30000000-0000-4000-8000-000000000001"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    class FallbackTestStore:
        def __init__(self) -> None:
            self.record = IngestionRecord(
                job_id=event.job_id,
                user_id=event.user_id,
                project_id=event.project_id,
                document_id=event.document_id,
                filename="lightweight.pdf",
                file_type="pdf",
                r2_object_key="private/lightweight.pdf",
                checksum_sha256=None,
                attempts=1,
            )
            self.stored_chunks: list[ChunkEntry] = []

        def claim(self, event, *, worker_id, lease_seconds):
            return self.record

        def replace_content(self, record, *, worker_id, pages, chunks, pipeline_version):
            self.stored_chunks = chunks

        def mark_ready(self, record, *, worker_id):
            pass

        def mark_retryable(self, record, *, worker_id, code):
            pass

        def mark_failed(self, record, *, worker_id, code):
            pass

    class FakeObjectReader:
        def download_to_file(self, object_key, destination):
            destination.write_text("Short text.")

    class FakeParser:
        def parse(self, source, *, file_type):
            return [
                type(
                    "ParsedBlock",
                    (),
                    {
                        "text": "Short text content.",
                        "page_no": 1,
                        "slide_no": None,
                        "section_title": None,
                        "metadata": {},
                    },
                )(),
            ]

    class FakeVectorProjection:
        def upsert_chunks(self, chunks, *, pipeline_version):
            pass

    class FailingWikiCompiler:
        def compile(self, chunks, **kwargs):
            raise WikiCompilationError("LLM_FAILED", "LLM call failed")

    test_store = FallbackTestStore()
    service = DocumentIngestionService(
        store=test_store,  # type: ignore[arg-type]
        object_reader=FakeObjectReader(),  # type: ignore[arg-type]
        parser=FakeParser(),  # type: ignore[arg-type]
        vector_projection=FakeVectorProjection(),  # type: ignore[arg-type]
        pipeline_version="test-v1",
        lease_seconds=300,
        max_attempts=3,
        max_upload_bytes=10_000_000,
        lightweight_token_threshold=4000,
        wiki_compiler=FailingWikiCompiler(),  # type: ignore[arg-type]
    )
    result = service.handle(event, worker_id="test-worker")
    assert result == "succeeded"
    # Should fall back to raw chunks (no wiki metadata)
    assert len(test_store.stored_chunks) > 0
    chunk = test_store.stored_chunks[0]
    assert chunk.metadata.get("wiki_mode") is None
