"""Verify local Wiki knowledge extraction and provenance validation."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.wiki_compiler import (
    WikiCompilationError,
    WikiCompiler,
    wiki_chunks_to_pages,
    wiki_pages_to_chunks,
)

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("20000000-0000-4000-8000-000000000001")
DOCUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")


class FragmentProvider:
    """Return one deterministic structured extraction response."""

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def complete(self, messages: list[dict[str, str]]) -> LLMResult:
        return LLMResult(
            content=json.dumps(self.payload),
            reasoning=None,
            model="test",
            prompt_tokens=None,
            completion_tokens=None,
        )


def _chunks() -> list[ChunkEntry]:
    return [
        ChunkEntry(
            id=UUID(f"40000000-0000-4000-8000-{index:012d}"),
            user_id=USER_ID,
            project_id=PROJECT_ID,
            document_id=DOCUMENT_ID,
            source_type=SourceType.LOCAL_DOC,
            source_title="source.pdf",
            text=f"chunk {index}",
            chunk_index=index,
        )
        for index in range(2)
    ]


def test_incremental_compilation_persists_stable_document_overview_and_synthesis() -> None:
    class NarrativeProvider:
        def complete(self, messages: list[dict[str, str]]) -> LLMResult:
            if "Synthesize" in messages[0]["content"]:
                payload = {
                    "summary": "A coherent document conclusion.",
                    "argument_flow": ["Premise", "Result"],
                }
            else:
                payload = [
                    {
                        "section_context": "A section",
                        "entities": [{"name": "Topic", "source_chunk_indices": [0]}],
                        "claims": [],
                        "relations": [],
                        "source_chunk_indices": [0, 1],
                    }
                ]
            return LLMResult(json.dumps(payload), None, "fixture", 0, 0)

    compiler = WikiCompiler(NarrativeProvider())
    arguments = dict(
        filename="source.pdf",
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=1,
    )
    first = compiler.compile_incremental(_chunks(), existing_pages=[], **arguments)
    second = compiler.compile_incremental(
        _chunks(), existing_pages=first.affected_pages, **arguments
    )
    first_overview = next(
        page for page in first.affected_pages if page.page_type == "document_overview"
    )
    second_overview = next(
        page for page in second.affected_pages if page.page_type == "document_overview"
    )
    assert first_overview.id == second_overview.id
    assert first.delta.summary == "A coherent document conclusion."
    assert first_overview.source_chunk_ids == [chunk.id for chunk in _chunks()]
    assert "Result" in first_overview.content
    projected = wiki_pages_to_chunks([first_overview])
    projected[0].document_id = None
    restored = wiki_chunks_to_pages(projected)[0]
    assert restored.document_id == DOCUMENT_ID
    assert restored.id == first_overview.id


def test_extract_fragments_resolves_item_provenance_to_input_chunk_ids() -> None:
    chunks = _chunks()
    provider = FragmentProvider(
        [
            {
                "section_context": "Retrieval design",
                "source_chunk_indices": [0, 1],
                "entities": [
                    {
                        "name": "Hybrid Search",
                        "aliases": ["Hybrid Retrieval"],
                        "source_chunk_indices": [0],
                    }
                ],
                "claims": [
                    {
                        "subject": "Hybrid Search",
                        "predicate": "combines",
                        "object": "lexical and semantic retrieval",
                        "source_chunk_indices": [0, 1],
                    }
                ],
                "relations": [],
            }
        ]
    )

    fragments = WikiCompiler(provider).extract_fragments(chunks)  # type: ignore[arg-type]

    assert fragments[0].source_chunk_ids == [chunks[0].id, chunks[1].id]
    assert fragments[0].entities[0].source_chunk_ids == [chunks[0].id]
    assert fragments[0].claims[0].source_chunk_ids == [chunks[0].id, chunks[1].id]


def test_extract_fragments_rejects_unknown_only_provenance() -> None:
    provider = FragmentProvider(
        [
            {
                "section_context": "Invalid",
                "source_chunk_indices": [99],
                "entities": [],
                "claims": [],
                "relations": [],
            }
        ]
    )

    with pytest.raises(WikiCompilationError) as exc_info:
        WikiCompiler(provider).extract_fragments(_chunks())  # type: ignore[arg-type]

    assert exc_info.value.code == "EMPTY_OUTPUT"
