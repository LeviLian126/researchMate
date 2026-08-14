"""Test the LLM Wiki Compiler contract and ingestion integration.

These tests are organized as ISTQB/IEEE 29119 aligned two-phase coverage:

* Phase 1 (black-box): behaviors asserted from the public contract only.
* Phase 2 (white-box): branches surfaced by reading the implementation.

Both phases share hermetic in-memory doubles; no real LLM, DB, Qdrant, or
HTTP traffic is exercised.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest
from researchmate_api.schemas.common import CurrentUser, SourceType
from researchmate_api.services._store_core import InMemoryStoreCore
from researchmate_api.services._store_models import WikiPage
from researchmate_api.services._store_wiki import WikiStoreMixin
from researchmate_api.services.answering import _build_evidence_entry
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.wiki_compiler import (
    WikiCompilationError,
    WikiCompiler,
    wiki_pages_to_chunks,
)
from researchmate_worker.ingestion_models import (
    IngestionEvent,
    IngestionRecord,
    PageProjection,
    ParsedBlock,
)
from researchmate_worker.ingestion_service import DocumentIngestionService
from researchmate_worker.task_builders import WorkerWikiCompiler

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000002")
DOCUMENT_ID = UUID("10000000-0000-4000-8000-000000000003")


# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------


class FakeChatProvider:
    """Return a canned completion payload for the wiki compiler."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.received_messages: list[dict[str, str]] = []

    def complete(self, messages) -> LLMResult:  # type: ignore[no-untyped-def]
        # Capture the messages list (an iterable of chat dicts) so tests can
        # assert that the chunk text reached the prompt.
        self.received_messages = list(messages)
        return LLMResult(
            content=self._content,
            reasoning=None,
            model="fake-model",
            prompt_tokens=10,
            completion_tokens=20,
        )


def make_chunk(
    *,
    text: str,
    chunk_index: int = 0,
    document_id: UUID = DOCUMENT_ID,
    source_title: str = "source.pdf",
) -> ChunkEntry:
    """Build a lightweight source chunk for compiler tests."""
    return ChunkEntry(
        id=UUID(f"20000000-0000-4000-8000-{chunk_index:012d}"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=document_id,
        source_type=SourceType.LOCAL_DOC,
        source_title=source_title,
        text=text,
        chunk_index=chunk_index,
        has_vector=False,
    )


def make_source_chunks(count: int = 2) -> list[ChunkEntry]:
    """Build a small set of raw chunks to feed into the compiler."""
    return [
        make_chunk(text=f"Chunk {i} content about topic {i}.", chunk_index=i) for i in range(count)
    ]


def proposal_payload(*proposals: dict) -> str:
    """Serialize one or more proposal dicts as the LLM JSON output."""
    return json.dumps(list(proposals))


def valid_proposal(**overrides) -> dict:  # type: ignore[no-untyped-def]
    """Build a minimally-valid wiki proposal dict."""
    base = {
        "title": "Sample Page",
        "page_type": "concept",
        "content": "Body text for the sample page.",
        "aliases": ["alias-one"],
        "links": ["Related Page"],
        "source_chunk_indices": [0],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. WikiCompiler.compile — happy path and proposal conversion
# ---------------------------------------------------------------------------


def test_compile_produces_wiki_pages_from_valid_llm_output() -> None:
    """Valid JSON proposals become WikiPage objects with provenance copied."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Alpha", source_chunk_indices=[0]),
            valid_proposal(title="Beta", source_chunk_indices=[1]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Alpha", "Beta"]
    assert all(p.user_id == USER_ID for p in pages)
    assert all(p.project_id == PROJECT_ID for p in pages)
    assert all(p.document_id == DOCUMENT_ID for p in pages)
    assert [len(p.source_chunk_ids) for p in pages] == [1, 1]
    assert pages[0].source_chunk_ids == [chunks[0].id]
    assert pages[1].source_chunk_ids == [chunks[1].id]
    # Each page gets a fresh UUID.
    assert pages[0].id != pages[1].id
    # Chunk text reaches the prompt messages.
    assert any(chunks[0].text in m.get("content", "") for m in provider.received_messages)


def test_compile_strips_json_markdown_fences() -> None:
    """LLM output wrapped in ```json fences is still parsed."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(f"```json\n{proposal_payload(valid_proposal(title='Fenced'))}\n```")

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Fenced"]


def test_compile_extracts_wikilinks_and_deduplicates_with_links() -> None:
    """[[wikilinks]] inside content are merged into links, deduplicated."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(
                title="Linked Page",
                content="See [[Alpha]] and [[Beta]] and again [[Alpha]].",
                links=["Beta"],
                source_chunk_indices=[0],
            )
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # Extracted wikilinks (in first-occurrence content order) come first,
    # followed by the proposal's explicit links; union is deduplicated.
    assert pages[0].links == ["Alpha", "Beta"]


# ---------------------------------------------------------------------------
# 2. WikiCompiler.compile — error paths
# ---------------------------------------------------------------------------


def test_compile_empty_chunks_raises_no_chunks_error() -> None:
    """An empty chunks list is rejected before any LLM call."""
    provider = FakeChatProvider(proposal_payload())

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            [],
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "NO_CHUNKS"


def test_compile_invalid_json_raises_error() -> None:
    """LLM output lacking any JSON array brackets surfaces as INVALID_FORMAT.

    The compiler locates the array via raw.find('[')/rfind(']'); content with
    neither bracket cannot be an array, so it raises INVALID_FORMAT before
    json.loads is ever attempted.
    """
    chunks = make_source_chunks(1)
    provider = FakeChatProvider("this is not json")

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "INVALID_FORMAT"


def test_compile_malformed_array_json_raises_parse_error() -> None:
    """Output containing array brackets but unparseable JSON raises JSON_PARSE_FAILED."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider("[this is not valid json]")

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "JSON_PARSE_FAILED"


def test_compile_non_array_json_raises_error() -> None:
    """A JSON object (no array delimiters) is rejected as INVALID_FORMAT.

    A plain JSON object has no '[' bracket, so the compiler reports an invalid
    format at the array-location step rather than reaching the NOT_ARRAY branch
    (JSON grammar guarantees any slice beginning with '[' parses to a list, so
    NOT_ARRAY is only reachable by a value that has no '[' at all, which is the
    INVALID_FORMAT path instead).
    """
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(json.dumps({"title": "Not an array"}))

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "INVALID_FORMAT"


def test_compile_empty_array_raises_empty_output_error() -> None:
    """A valid but empty JSON array surfaces as EMPTY_OUTPUT."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload())

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "EMPTY_OUTPUT"


def test_compile_all_proposals_skipped_raises_empty_output_error() -> None:
    """When every proposal is filtered out, EMPTY_OUTPUT is raised."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            # Out-of-range index -> skipped.
            valid_proposal(source_chunk_indices=[99]),
            # Missing required field -> skipped by pydantic validation.
            {"title": "NoType", "content": "x", "source_chunk_indices": [0]},
        )
    )

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "EMPTY_OUTPUT"


def test_compile_rejects_unknown_proposal_field_via_extra_forbid() -> None:
    """extra=forbid drops proposals carrying unknown fields (skipped, not raised)."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(bogus_field="nope", source_chunk_indices=[0]),
            valid_proposal(title="Kept", source_chunk_indices=[0]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Kept"]


def test_compile_skips_out_of_range_index_but_keeps_valid_proposals() -> None:
    """A proposal with valid indices is kept alongside one with bad indices."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Good", source_chunk_indices=[0]),
            valid_proposal(title="BadIdx", source_chunk_indices=[5]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Good"]


def test_compile_negative_chunk_index_proposal_is_skipped() -> None:
    """Negative indices are out of range and the proposal is skipped."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Neg", source_chunk_indices=[-1]),
            valid_proposal(title="Kept", source_chunk_indices=[0]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Kept"]


def test_wiki_compilation_error_carries_code_and_message() -> None:
    """The error exposes both a stable code and a human message."""
    err = WikiCompilationError("NO_CHUNKS", "no source chunks supplied")
    assert err.code == "NO_CHUNKS"
    assert err.message == "no source chunks supplied"
    assert str(err) == "no source chunks supplied"


# ---------------------------------------------------------------------------
# 3. wiki_pages_to_chunks — metadata projection
# ---------------------------------------------------------------------------


def test_wiki_pages_to_chunks_preserves_metadata_and_provenance() -> None:
    """WikiPage objects project back into ChunkEntry with wiki metadata."""
    source_chunk_id = UUID("30000000-0000-4000-8000-000000000001")
    page_id = UUID("40000000-0000-4000-8000-000000000001")
    page = WikiPage(
        id=page_id,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Concept Page",
        page_type="concept",
        content="Page body text.",
        aliases=["alias-a"],
        links=["Linked Page"],
        source_chunk_ids=[source_chunk_id],
    )

    chunks = wiki_pages_to_chunks([page])

    assert len(chunks) == 1
    assert chunks[0].id == page_id
    assert chunks[0].user_id == USER_ID
    assert chunks[0].project_id == PROJECT_ID
    assert chunks[0].document_id == DOCUMENT_ID
    assert chunks[0].source_type == SourceType.LOCAL_DOC
    assert chunks[0].source_title == "Concept Page"
    assert chunks[0].text == "Page body text."
    assert chunks[0].chunk_index == 0
    assert chunks[0].has_vector is False
    assert chunks[0].metadata["wiki_mode"] is True
    assert chunks[0].metadata["wiki_type"] == "concept"
    assert chunks[0].metadata["wiki_links"] == ["Linked Page"]
    assert chunks[0].metadata["wiki_aliases"] == ["alias-a"]
    assert chunks[0].metadata["wiki_source_chunk_ids"] == [str(source_chunk_id)]


def test_wiki_pages_to_chunks_assigns_sequential_chunk_indices() -> None:
    """Multiple pages receive chunk_index 0, 1, 2, ... in order."""
    pages = [
        WikiPage(
            id=UUID(f"50000000-0000-4000-8000-{i:012d}"),
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
            title=f"Page {i}",
            page_type="concept",
            content=f"body {i}",
            source_chunk_ids=[],
        )
        for i in range(3)
    ]

    chunks = wiki_pages_to_chunks(pages)

    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    # Page UUIDs are reused as chunk ids.
    assert [c.id for c in chunks] == [p.id for p in pages]


def test_wiki_pages_to_chunks_empty_pages_returns_empty_list() -> None:
    """An empty page list projects to an empty chunk list."""
    assert wiki_pages_to_chunks([]) == []


# ---------------------------------------------------------------------------
# 4. WikiStoreMixin — store, retrieve, delete, reset
# ---------------------------------------------------------------------------


class WikiMemoryStore(WikiStoreMixin, InMemoryStoreCore):
    """Concrete in-memory store exercising the wiki mixin."""


def _uuid_for(title: str, salt: int = 0) -> UUID:
    """Derive a deterministic valid UUID from a title so pages are keyed stably.

    Uses zlib.crc32 (a stable, positive 32-bit hash) combined with a salt to
    produce distinct UUIDs per title without relying on Python's randomized
    built-in hash().
    """
    import zlib

    digest = zlib.crc32(title.encode("utf-8")) + salt
    # Spread the 32-bit digest across a valid RFC-4122 v4 layout.
    hex32 = f"{digest:08x}" + f"{digest:08x}" + "40008000" + f"{digest & 0x0FFFFFFF:07x}1"
    return UUID(hex32)


def make_wiki_page(
    *,
    title: str,
    document_id: UUID = DOCUMENT_ID,
    project_id: UUID = PROJECT_ID,
    salt: int = 0,
) -> WikiPage:
    """Build a WikiPage with stable identifiers for store tests."""
    return WikiPage(
        id=_uuid_for(title, salt=salt),
        user_id=USER_ID,
        project_id=project_id,
        document_id=document_id,
        title=title,
        page_type="concept",
        content=f"Content for {title}.",
        aliases=[],
        links=[],
        source_chunk_ids=[],
    )


def test_store_wiki_pages_persists_pages_by_id() -> None:
    """Stored pages are retained and individually keyed by id."""
    store = WikiMemoryStore()
    page = make_wiki_page(title="Stored")

    store.store_wiki_pages([page])

    assert store.project_wiki_pages(CurrentUser(id=USER_ID), PROJECT_ID) == [page]


def test_project_wiki_pages_filters_by_user_and_project() -> None:
    """Only pages matching both user_id and project_id are returned."""
    store = WikiMemoryStore()
    other_user_page = WikiPage(
        id=UUID("70000000-0000-4000-8000-000000000001"),
        user_id=UUID("80000000-0000-4000-8000-000000000001"),
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Other User",
        page_type="concept",
        content="x",
    )
    other_project_page = make_wiki_page(
        title="Other Project",
        project_id=UUID("80000000-0000-4000-8000-000000000002"),
    )
    matching_page = make_wiki_page(title="Match")
    store.store_wiki_pages([other_user_page, other_project_page, matching_page])

    result = store.project_wiki_pages(CurrentUser(id=USER_ID), PROJECT_ID)

    assert result == [matching_page]


def test_document_wiki_pages_filters_by_user_and_document() -> None:
    """Only pages matching both user_id and document_id are returned."""
    store = WikiMemoryStore()
    doc_a = make_wiki_page(title="A", document_id=UUID("90000000-0000-4000-8000-000000000001"))
    doc_b = make_wiki_page(title="B", document_id=DOCUMENT_ID)
    store.store_wiki_pages([doc_a, doc_b])

    result = store.document_wiki_pages(CurrentUser(id=USER_ID), DOCUMENT_ID)

    assert result == [doc_b]


def test_delete_document_wiki_pages_removes_only_matching_document() -> None:
    """delete_document_wiki_pages drops pages for one document only."""
    store = WikiMemoryStore()
    target_doc = UUID("A1000000-0000-4000-8000-000000000001")
    other_doc = DOCUMENT_ID
    keep = make_wiki_page(title="Keep", document_id=other_doc)
    drop = make_wiki_page(title="Drop", document_id=target_doc)
    store.store_wiki_pages([keep, drop])

    store.delete_document_wiki_pages(target_doc)

    assert store.document_wiki_pages(CurrentUser(id=USER_ID), target_doc) == []
    assert store.document_wiki_pages(CurrentUser(id=USER_ID), other_doc) == [keep]


def test_store_reset_clears_all_wiki_pages() -> None:
    """reset() wipes the wiki page collection along with other state."""
    store = WikiMemoryStore()
    store.store_wiki_pages([make_wiki_page(title="One"), make_wiki_page(title="Two")])
    assert store.project_wiki_pages(CurrentUser(id=USER_ID), PROJECT_ID) != []

    store.reset()

    assert store.project_wiki_pages(CurrentUser(id=USER_ID), PROJECT_ID) == []


# ---------------------------------------------------------------------------
# Phase 1 (black-box): compile_overview contract — single overview page
# ---------------------------------------------------------------------------


def test_compile_overview_empty_chunks_raises_no_chunks_error() -> None:
    """An empty chunks list is rejected before the overview LLM call."""
    provider = FakeChatProvider(proposal_payload())

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            [],
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "NO_CHUNKS"


def test_compile_overview_single_chunk_returns_one_page() -> None:
    """A single chunk with a valid proposal yields exactly one overview page."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Overview", page_type="overview", source_chunk_indices=[0])
        )
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages) == 1
    assert pages[0].title == "Overview"
    assert pages[0].page_type == "overview"


def test_compile_overview_multiple_chunks_returns_one_page() -> None:
    """Multiple chunks still compile to a single overview page."""
    chunks = make_source_chunks(4)
    provider = FakeChatProvider(
        proposal_payload(valid_proposal(title="Multi Overview", source_chunk_indices=[0, 1, 2, 3]))
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages) == 1
    assert pages[0].title == "Multi Overview"


def test_compile_overview_two_proposals_returns_only_first() -> None:
    """compile_overview always keeps the first proposal, regardless of count."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="First", source_chunk_indices=[0]),
            valid_proposal(title="Second", source_chunk_indices=[1]),
        )
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages) == 1
    assert pages[0].title == "First"


def test_compile_overview_empty_array_raises_empty_output_error() -> None:
    """A valid but empty JSON array surfaces as EMPTY_OUTPUT."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload())

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "EMPTY_OUTPUT"


def test_compile_overview_invalid_json_raises_error() -> None:
    """Non-JSON output is rejected before any page is built."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider("this is not json at all")

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code in {"INVALID_FORMAT", "JSON_PARSE_FAILED"}


def test_compile_overview_large_chunks_still_returns_one_page() -> None:
    """A corpus of many large chunks still compiles to a single overview page."""
    # Each chunk is large enough that the corpus exceeds the overview input
    # token budget, forcing the sampler to run; compile_overview still returns
    # one page built from the sampled subset.
    chunks = [make_chunk(text=("topic " * 2000), chunk_index=i) for i in range(6)]
    provider = FakeChatProvider(
        proposal_payload(valid_proposal(title="Big Overview", source_chunk_indices=[0]))
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages) == 1
    assert pages[0].title == "Big Overview"


def test_compile_overview_receives_chunk_text_in_prompt() -> None:
    """The chunk text is embedded into the prompt sent to the LLM."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(valid_proposal(title="Prompted Overview", source_chunk_indices=[0]))
    )

    WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # The sampled chunks text must reach the captured messages.
    assert provider.received_messages != []
    user_msg = provider.received_messages[-1]["content"]
    assert chunks[0].text in user_msg
    assert chunks[1].text in user_msg


def test_compile_overview_propagates_page_type_from_llm_response() -> None:
    """The page_type returned by the LLM is preserved on the WikiPage."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="TypedOverview", page_type="overview", source_chunk_indices=[0])
        )
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert pages[0].page_type == "overview"


def test_compile_overview_resolves_source_chunk_ids_from_indices() -> None:
    """source_chunk_indices are converted to source_chunk_ids from sampled chunks."""
    chunks = make_source_chunks(3)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(
                title="ProvenanceOverview",
                source_chunk_indices=[0, 2],
            )
        )
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert pages[0].source_chunk_ids == [chunks[0].id, chunks[2].id]


# ---------------------------------------------------------------------------
# Phase 1 (black-box): structured references contract
# ---------------------------------------------------------------------------


def test_compile_proposal_has_references_matching_source_chunks() -> None:
    """WikiPage carries references for every source chunk."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(valid_proposal(title="RefPage", source_chunk_indices=[0, 1]))
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages[0].references) == 2


def test_compile_reference_document_id_matches_chunk_document_id_as_string() -> None:
    """Each reference document_id matches the chunk's document_id (as string)."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert pages[0].references[0]["document_id"] == str(chunks[0].document_id)


def test_compile_reference_chunk_id_matches_chunk_id_as_string() -> None:
    """Each reference chunk_id matches the chunk's id (as string)."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert pages[0].references[0]["chunk_id"] == str(chunks[0].id)


def test_wiki_pages_to_chunks_carries_references_in_metadata() -> None:
    """wiki_pages_to_chunks projects the references list into chunk metadata."""
    source_chunk_id = UUID("60000000-0000-4000-8000-000000000001")
    references = [
        {
            "document_id": str(DOCUMENT_ID),
            "section_title": "Intro",
            "page_no": 1,
            "chunk_id": str(source_chunk_id),
        }
    ]
    page = WikiPage(
        id=UUID("60000000-0000-4000-8000-000000000002"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Ref Page",
        page_type="concept",
        content="body",
        source_chunk_ids=[source_chunk_id],
        references=references,
    )

    chunks = wiki_pages_to_chunks([page])

    assert chunks[0].metadata["wiki_references"] == references


def test_compile_reference_document_id_is_none_when_chunk_has_none() -> None:
    """A chunk with document_id=None projects to None in the reference."""
    chunk = make_chunk(text="No document chunk.", chunk_index=0, document_id=None)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile(
        [chunk],
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert pages[0].references[0]["document_id"] is None


def test_compile_reference_carries_section_title_and_page_no() -> None:
    """section_title and page_no from the chunk appear on the reference."""
    chunk = ChunkEntry(
        id=UUID("20000000-0000-4000-8000-000000000020"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        source_type=SourceType.LOCAL_DOC,
        source_title="sectioned.pdf",
        text="Some section content.",
        chunk_index=0,
        section_title="Methodology",
        page_no=7,
        has_vector=False,
    )
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile(
        [chunk],
        filename="sectioned.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    ref = pages[0].references[0]
    assert ref["section_title"] == "Methodology"
    assert ref["page_no"] == 7


# ---------------------------------------------------------------------------
# Phase 2 (white-box): branches surfaced from reading the implementation.
# ---------------------------------------------------------------------------


class BoundedChatProvider:
    """Provider exposing complete_bounded, which the compiler prefers when set."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.bounded_calls: list[tuple[int]] = []

    def complete(self, messages) -> LLMResult:  # type: ignore[no-untyped-def]
        raise AssertionError("complete_bounded provider must not fall back to complete()")

    def complete_bounded(self, messages, *, max_tokens: int) -> LLMResult:  # type: ignore[no-untyped-def]
        self.bounded_calls.append((max_tokens,))
        return LLMResult(
            content=self._content,
            reasoning=None,
            model="fake-bounded",
            prompt_tokens=10,
            completion_tokens=20,
        )


def test_compile_prefers_complete_bounded_when_available() -> None:
    """The compiler routes through complete_bounded when the provider offers it."""
    chunks = make_source_chunks(1)
    provider = BoundedChatProvider(proposal_payload(valid_proposal(title="Bounded")))

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Bounded"]
    # The bounded budget passed by the compiler is surfaced to the provider.
    assert provider.bounded_calls == [(8192,)]


def test_compile_max_pages_caps_proposal_count() -> None:
    """Only the first max_pages proposals are considered, even if more arrive."""
    chunks = make_source_chunks(8)
    provider = FakeChatProvider(
        proposal_payload(
            *[valid_proposal(title=f"P{i}", source_chunk_indices=[i]) for i in range(8)]
        )
    )

    pages = WikiCompiler(provider, max_pages=3).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["P0", "P1", "P2"]


def test_compile_filters_individual_bad_indices_not_whole_proposal() -> None:
    """A proposal with mixed valid/invalid indices keeps the valid ones only.

    The contract's 'skip on out-of-range' applies per-index: a proposal with
    source_chunk_indices [0, 99] against two chunks is retained with [0],
    not dropped entirely. Only when ALL indices are out of range is the
    proposal skipped.
    """
    chunks = make_source_chunks(4)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Mixed", source_chunk_indices=[0, 99]),
            valid_proposal(title="AllBad", source_chunk_indices=[100, 101]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Mixed"]
    # The valid index survives; the bad index is filtered out.
    assert pages[0].source_chunk_ids == [chunks[0].id]


def test_compile_parses_json_surrounded_by_prose() -> None:
    """LLM output with prose before/after the array (no fences) still parses."""
    chunks = make_source_chunks(1)
    payload = proposal_payload(valid_proposal(title="Prose"))
    provider = FakeChatProvider(f"Here are the wiki pages:\n{payload}\nThat was the output.")

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Prose"]


def test_compile_strips_plain_fences_without_json_label() -> None:
    """Fences without the 'json' label are still stripped before parsing."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(f"```\n{proposal_payload(valid_proposal(title='PlainFence'))}\n```")

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["PlainFence"]


def test_compile_wikilinks_deduplication_across_repeats_and_proposal_links() -> None:
    """Repeated wikilinks and overlapping proposal links collapse to first-seen."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(
                title="Dedupe",
                content="[[A]] [[B]] [[A]] [[C]]",
                links=["B", "D"],
                source_chunk_indices=[0],
            )
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # Order: content wikilinks first (A, B, C with dupes removed), then proposal
    # links not already present (D). B and A appear once each despite repeats.
    assert pages[0].links == ["A", "B", "C", "D"]


def test_compile_proposal_with_invalid_type_is_skipped() -> None:
    """A proposal whose page_type exceeds length is skipped, siblings kept."""
    chunks = make_source_chunks(1)
    long_type = "x" * 51  # WIKI_PAGE_TYPE_LENGTH is 50.
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="TooLongType", page_type=long_type, source_chunk_indices=[0]),
            valid_proposal(title="Kept", source_chunk_indices=[0]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["Kept"]


def test_compile_proposal_with_empty_source_indices_is_skipped() -> None:
    """source_chunk_indices is min_length=1; an empty list fails validation and is skipped."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="NoIdx", source_chunk_indices=[]),
            valid_proposal(title="Kept", source_chunk_indices=[0]),
        )
    )

    pages = WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # The empty-indices proposal fails Pydantic validation (min_length=1) and
    # is skipped; the valid sibling survives.
    assert [p.title for p in pages] == ["Kept"]


def test_compile_sends_chunks_in_index_order_and_truncates_text() -> None:
    """The prompt embeds each chunk's text, truncated to the content max."""
    chunks = [
        make_chunk(text="A" * 10_000, chunk_index=0),  # exceeds 8000 char cap
        make_chunk(text="B", chunk_index=1),
    ]
    provider = FakeChatProvider(proposal_payload(valid_proposal(title="Truncated")))

    WikiCompiler(provider).compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    user_msg = provider.received_messages[-1]["content"]
    # The oversized chunk is truncated to the WIKI_MAX_CONTENT_LENGTH cap.
    assert "A" * 8000 in user_msg
    assert "A" * 8001 not in user_msg
    # The second chunk survives intact and is identifiable.
    assert "B" in user_msg


def test_worker_wiki_compiler_adapter_returns_chunks_with_wiki_metadata() -> None:
    """WorkerWikiCompiler chains API compiler + wiki_pages_to_chunks end-to-end.

    The worker adapter wraps the API WikiCompiler (returns list[WikiPage]) and
    projects to list[ChunkEntry] so the ingestion store can persist compiled
    pages via the existing replace_content path.
    """
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(
        proposal_payload(
            valid_proposal(title="Adapter Page", source_chunk_indices=[0, 1]),
        )
    )
    adapter = WorkerWikiCompiler(provider)  # type: ignore[arg-type]

    result = adapter.compile(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(result) == 1
    compiled = result[0]
    assert isinstance(compiled, ChunkEntry)
    assert compiled.user_id == USER_ID
    assert compiled.project_id == PROJECT_ID
    assert compiled.document_id == DOCUMENT_ID
    assert compiled.source_title == "Adapter Page"
    assert compiled.source_type == SourceType.LOCAL_DOC
    assert compiled.has_vector is False
    assert compiled.metadata["wiki_mode"] is True
    assert compiled.metadata["wiki_source_chunk_ids"] == [
        str(chunks[0].id),
        str(chunks[1].id),
    ]


def test_build_evidence_entry_surfaces_wiki_structure_for_compiled_chunks() -> None:
    """Answer evidence formatting promotes wiki metadata for compiled chunks."""
    chunk = ChunkEntry(
        id=UUID("E0000000-0000-4000-8000-000000000001"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        source_type=SourceType.LOCAL_DOC,
        source_title="Concept Title",
        text="Body text.",
        chunk_index=0,
        has_vector=False,
        metadata={
            "wiki_mode": True,
            "wiki_type": "concept",
            "wiki_links": ["Linked Page"],
            "wiki_aliases": ["alias-a"],
            "wiki_source_chunk_ids": [],
        },
    )

    entry = _build_evidence_entry(1, chunk)

    assert entry["wiki_title"] == "Concept Title"
    assert entry["wiki_type"] == "concept"
    assert entry["wiki_links"] == ["Linked Page"]
    assert entry["source_type"] == "local_doc"
    assert entry["text"] == "Body text."


def test_build_evidence_entry_omits_wiki_fields_for_raw_chunks() -> None:
    """Raw (non-wiki) chunks produce the legacy flat evidence format."""
    chunk = ChunkEntry(
        id=UUID("E0000000-0000-4000-8000-000000000002"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        source_type=SourceType.LOCAL_DOC,
        source_title="Raw Doc",
        text="Raw body.",
        chunk_index=0,
        has_vector=True,
        metadata={},
    )

    entry = _build_evidence_entry(2, chunk)

    assert "wiki_title" not in entry
    assert "wiki_type" not in entry
    assert "wiki_links" not in entry
    assert entry["text"] == "Raw body."


def test_build_evidence_entry_omits_wiki_links_when_empty() -> None:
    """wiki_links is only attached when the list is non-empty."""
    chunk = ChunkEntry(
        id=UUID("E0000000-0000-4000-8000-000000000003"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        source_type=SourceType.LOCAL_DOC,
        source_title="Lonely Page",
        text="Body.",
        chunk_index=0,
        has_vector=False,
        metadata={
            "wiki_mode": True,
            "wiki_type": "reference",
            "wiki_links": [],
            "wiki_aliases": [],
            "wiki_source_chunk_ids": [],
        },
    )

    entry = _build_evidence_entry(1, chunk)

    assert entry["wiki_title"] == "Lonely Page"
    assert entry["wiki_type"] == "reference"
    assert "wiki_links" not in entry


# ---------------------------------------------------------------------------
# Phase 2 (white-box): compile_overview sampler boundaries and error routing
# ---------------------------------------------------------------------------


def test_compile_overview_prefers_complete_bounded_when_available() -> None:
    """compile_overview routes through complete_bounded when the provider offers it."""
    chunks = make_source_chunks(1)
    provider = BoundedChatProvider(
        proposal_payload(valid_proposal(title="BoundedOverview", source_chunk_indices=[0]))
    )

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert [p.title for p in pages] == ["BoundedOverview"]
    # The bounded budget passed by the compiler is surfaced to the provider.
    assert provider.bounded_calls == [(8192,)]


def test_compile_overview_malformed_array_json_raises_parse_error() -> None:
    """Output containing array brackets but unparseable JSON raises JSON_PARSE_FAILED."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider("[this is not valid json]")

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "JSON_PARSE_FAILED"


def test_compile_overview_non_array_json_raises_invalid_format() -> None:
    """A JSON object (no array delimiters) is rejected as INVALID_FORMAT."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(json.dumps({"title": "Not an array"}))

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "INVALID_FORMAT"


def test_compile_overview_all_proposals_skipped_raises_empty_output() -> None:
    """When every proposal is filtered out, EMPTY_OUTPUT is raised."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(
        proposal_payload(
            # Out-of-range index (relative to sampled chunks) -> skipped.
            valid_proposal(source_chunk_indices=[99])
        )
    )

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "EMPTY_OUTPUT"


def test_compile_overview_single_chunk_under_budget_returns_full_sample() -> None:
    """With one chunk the total fits the budget; sampler returns the full list."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # Single chunk: not sampled; the proposal references index 0 and survives.
    assert pages[0].source_chunk_ids == [chunks[0].id]


def test_compile_overview_two_chunks_over_budget_returns_both() -> None:
    """When total exceeds the budget but only two chunks exist, both are kept.

    _sample_for_overview short-circuits when len(chunks) <= 2, returning the
    full list regardless of token count, so first/last pinning is not applied.
    """
    chunks = [
        make_chunk(text="topic " * 4000, chunk_index=0),
        make_chunk(text="topic " * 4000, chunk_index=1),
    ]
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0, 1])))

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # Both chunks survive; the proposal references both indices and resolves.
    assert pages[0].source_chunk_ids == [chunks[0].id, chunks[1].id]


def test_compile_overview_many_chunks_over_budget_keeps_first_pin() -> None:
    """Sampling always pins the first chunk, so index 0 always resolves.

    compile_overview passes the SAMPLED chunk list to _build_pages. The first
    chunk is always in the sample (pinned), so a proposal referencing index 0
    resolves to the original first chunk's id regardless of corpus size.
    """
    # Each chunk is large enough that the corpus exceeds the overview budget.
    chunks = [make_chunk(text=("z " * 4000), chunk_index=i) for i in range(5)]
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0])))

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    # The first chunk is pinned by the sampler, so it remains in the sample and
    # proposal index 0 resolves to its id even though other chunks were dropped.
    assert pages[0].source_chunk_ids == [chunks[0].id]


def test_compile_overview_out_of_range_index_in_proposal_is_dropped() -> None:
    """Out-of-range indices in the proposal are filtered per-index; siblings kept."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0, 99])))

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    assert len(pages) == 1
    assert pages[0].source_chunk_ids == [chunks[0].id]


def test_compile_overview_proposal_with_empty_indices_skipped_raises_empty_output() -> None:
    """source_chunk_indices is min_length=1; empty list fails validation and is skipped."""
    chunks = make_source_chunks(1)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[])))

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).compile_overview(
            chunks,
            filename="doc.pdf",
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
        )

    assert exc_info.value.code == "EMPTY_OUTPUT"


def test_compile_overview_reference_chunk_id_is_string_for_sampled_chunks() -> None:
    """compile_overview also fills references for the sampled subset."""
    chunks = make_source_chunks(2)
    provider = FakeChatProvider(proposal_payload(valid_proposal(source_chunk_indices=[0, 1])))

    pages = WikiCompiler(provider).compile_overview(
        chunks,
        filename="doc.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )

    refs = pages[0].references
    assert [r["chunk_id"] for r in refs] == [str(chunks[0].id), str(chunks[1].id)]
    assert all(r["document_id"] == str(DOCUMENT_ID) for r in refs)


# ---------------------------------------------------------------------------
# 5. Ingestion integration — wiki compiler replaces raw chunks
# ---------------------------------------------------------------------------


EVENT = IngestionEvent(
    job_id=UUID("10000000-0000-4000-8000-000000000010"),
    user_id=USER_ID,
    project_id=PROJECT_ID,
    document_id=DOCUMENT_ID,
)


@dataclass
class FakeIngestionStore:
    """Record ingestion lifecycle calls and capture replaced chunks."""

    record: IngestionRecord = field(
        default_factory=lambda: IngestionRecord(
            job_id=EVENT.job_id,
            user_id=EVENT.user_id,
            project_id=EVENT.project_id,
            document_id=EVENT.document_id,
            filename="small.pdf",
            file_type="pdf",
            r2_object_key="private/small.pdf",
            checksum_sha256=None,
            attempts=1,
        )
    )
    ready: bool = False
    retry: str | None = None
    failed: str | None = None
    captured_chunks: list[ChunkEntry] = field(default_factory=list)
    captured_pages: list[PageProjection] = field(default_factory=list)

    def claim(
        self, event: IngestionEvent, *, worker_id: str, lease_seconds: int
    ) -> IngestionRecord:
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
        self.captured_pages = pages
        self.captured_chunks = chunks

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None:
        self.ready = True

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        self.retry = code

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None:
        self.failed = code


class FakeObjectReader:
    """Write deterministic source bytes to a destination path."""

    def __init__(self, content: bytes = b"source bytes") -> None:
        self.content = content

    def download_to_file(self, object_key: str, destination: Path) -> None:
        destination.write_bytes(self.content)


class FakeParser:
    """Return a single short parsed block (lightweight by construction)."""

    def __init__(self, text: str = "Short lightweight content.") -> None:
        self.text = text

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        return [
            ParsedBlock(
                text=self.text,
                page_no=1,
                section_title="Lightweight",
                metadata={},
            )
        ]


class FakeVectorProjection:
    """Capture vector upserts without touching a vector store."""

    def __init__(self) -> None:
        self.captured: list[ChunkEntry] = []

    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None:
        self.captured = chunks


class FakeWorkerWikiCompiler:
    """Adapter-shaped worker compiler returning canned compiled chunks.

    Implements the worker WikiCompiler Protocol (returns list[ChunkEntry]).
    """

    def __init__(self, chunks: list[ChunkEntry]) -> None:
        self._chunks = chunks
        self.invoked = False

    def compile(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]:
        self.invoked = True
        return self._chunks


class FailingWikiCompiler:
    """Always raise, to exercise the ingestion fallback path."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def compile(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]:
        raise self.error


def build_ingestion_service(
    store: FakeIngestionStore,
    *,
    wiki_compiler: object | None = None,
) -> DocumentIngestionService:
    """Assemble a service wired with hermetic doubles and lightweight routing."""
    return DocumentIngestionService(
        store=store,
        object_reader=FakeObjectReader(),
        parser=FakeParser(),
        vector_projection=FakeVectorProjection(),
        pipeline_version="pipeline-v1",
        lease_seconds=120,
        max_attempts=3,
        max_upload_bytes=1024,
        lightweight_token_threshold=4000,
        wiki_compiler=wiki_compiler,
    )


def make_compiled_chunk() -> ChunkEntry:
    """A chunk produced by a successful wiki compilation (has_vector=False)."""
    return ChunkEntry(
        id=UUID("C0000000-0000-4000-8000-000000000001"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        source_type=SourceType.LOCAL_DOC,
        source_title="Wiki Page Title",
        text="Compiled wiki body.",
        chunk_index=0,
        has_vector=False,
        metadata={"wiki_mode": True},
    )


def test_lightweight_ingestion_with_wiki_compiler_replaces_chunks() -> None:
    """A lightweight document's chunks are replaced by compiled wiki chunks.

    The contract guarantees that when a wiki_compiler is supplied and
    compilation succeeds with a non-empty result, the compiled chunks replace
    the raw chunks (ingestion_service._compile_wiki returns them). The stored
    chunks must carry the compiled wiki metadata, not the raw chunk provenance.
    """
    store = FakeIngestionStore()
    compiled = make_compiled_chunk()
    wiki = FakeWorkerWikiCompiler([compiled])

    result = build_ingestion_service(store, wiki_compiler=wiki).handle(EVENT, worker_id="worker-1")

    assert result == "succeeded"
    assert wiki.invoked is True
    assert store.captured_chunks == [compiled]
    assert store.captured_chunks[0].has_vector is False
    assert store.captured_chunks[0].metadata["wiki_mode"] is True
    assert store.captured_chunks[0].source_title == "Wiki Page Title"


def test_lightweight_ingestion_sets_has_vector_false_without_compiler() -> None:
    """Lightweight chunks get has_vector=False even when no compiler is set."""
    store = FakeIngestionStore()

    result = build_ingestion_service(store, wiki_compiler=None).handle(EVENT, worker_id="worker-1")

    assert result == "succeeded"
    assert store.captured_chunks != []
    assert all(c.has_vector is False for c in store.captured_chunks)


def test_ingestion_falls_back_to_raw_chunks_when_wiki_compile_fails() -> None:
    """A compiler exception is swallowed and raw chunks are stored instead."""
    store = FakeIngestionStore()
    wiki = FailingWikiCompiler(RuntimeError("LLM is down"))

    result = build_ingestion_service(store, wiki_compiler=wiki).handle(EVENT, worker_id="worker-1")

    assert result == "succeeded"
    assert store.captured_chunks != []
    # Fallback raw chunks are still lightweight (has_vector False).
    assert all(c.has_vector is False for c in store.captured_chunks)
    # None of the fallback chunks carry the wiki metadata injected by the stub.
    assert all(c.metadata.get("wiki_mode") is not True for c in store.captured_chunks)


def test_ingestion_falls_back_to_raw_chunks_when_compiler_returns_empty() -> None:
    """An empty compiled list falls back to the raw lightweight chunks."""
    store = FakeIngestionStore()
    wiki = FakeWorkerWikiCompiler([])

    result = build_ingestion_service(store, wiki_compiler=wiki).handle(EVENT, worker_id="worker-1")

    assert result == "succeeded"
    assert wiki.invoked is True
    assert store.captured_chunks != []
    assert all(c.has_vector is False for c in store.captured_chunks)
    assert all(c.metadata.get("wiki_mode") is not True for c in store.captured_chunks)
