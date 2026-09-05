"""Verify document-level Wiki knowledge reduction across chunk groups."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.services.wiki_compiler import WikiCompiler
from researchmate_api.services.wiki_knowledge import (
    KnowledgeClaim,
    KnowledgeEntity,
    KnowledgeFragment,
    KnowledgeRelation,
)

DOCUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
CHUNK_A = UUID("40000000-0000-4000-8000-000000000001")
CHUNK_B = UUID("40000000-0000-4000-8000-000000000002")


def test_reduce_merges_cross_chunk_entities_claims_relations_and_argument_flow() -> None:
    fragments = [
        KnowledgeFragment(
            section_context="Defines hybrid retrieval.",
            entities=[
                KnowledgeEntity(
                    name="Hybrid Search",
                    aliases=["Hybrid Retrieval"],
                    source_chunk_ids=[CHUNK_A],
                )
            ],
            claims=[
                KnowledgeClaim(
                    subject="Hybrid Search",
                    predicate="uses",
                    object="BM25",
                    source_chunk_ids=[CHUNK_A],
                )
            ],
            source_chunk_ids=[CHUNK_A],
        ),
        KnowledgeFragment(
            section_context="Explains reranking after retrieval.",
            entities=[
                KnowledgeEntity(
                    name="Hybrid Retrieval",
                    aliases=["Qdrant Hybrid Search"],
                    source_chunk_ids=[CHUNK_B],
                ),
                KnowledgeEntity(name="Reranking", source_chunk_ids=[CHUNK_B]),
            ],
            claims=[
                KnowledgeClaim(
                    subject="Hybrid Retrieval",
                    predicate="uses",
                    object="BM25",
                    source_chunk_ids=[CHUNK_B],
                )
            ],
            relations=[
                KnowledgeRelation(
                    source="Hybrid Retrieval",
                    relation="followed by",
                    target="Reranking",
                    source_chunk_ids=[CHUNK_B],
                )
            ],
            source_chunk_ids=[CHUNK_B],
        ),
    ]

    delta = WikiCompiler(object()).reduce_document_knowledge(  # type: ignore[arg-type]
        fragments,
        filename="source.pdf",
        document_id=DOCUMENT_ID,
    )

    assert [entity.name for entity in delta.entities] == ["Hybrid Search", "Reranking"]
    assert "Qdrant Hybrid Search" in delta.entities[0].aliases
    assert delta.claims[0].source_chunk_ids == [CHUNK_A, CHUNK_B]
    assert delta.relations[0].source == "Hybrid Search"
    assert delta.argument_flow == [
        "Defines hybrid retrieval.",
        "Explains reranking after retrieval.",
    ]


def test_reduce_preserves_conflicting_values_and_marks_them() -> None:
    fragments = [
        KnowledgeFragment(
            entities=[KnowledgeEntity(name="Limit", source_chunk_ids=[CHUNK_A])],
            claims=[
                KnowledgeClaim(
                    subject="Limit",
                    predicate="value",
                    object="10",
                    source_chunk_ids=[CHUNK_A],
                )
            ],
            source_chunk_ids=[CHUNK_A],
        ),
        KnowledgeFragment(
            entities=[KnowledgeEntity(name="Limit", source_chunk_ids=[CHUNK_B])],
            claims=[
                KnowledgeClaim(
                    subject="Limit",
                    predicate="value",
                    object="20",
                    qualifiers={"version": "v2"},
                    source_chunk_ids=[CHUNK_B],
                )
            ],
            source_chunk_ids=[CHUNK_B],
        ),
    ]

    delta = WikiCompiler(object()).reduce_document_knowledge(  # type: ignore[arg-type]
        fragments,
        filename="source.pdf",
        document_id=DOCUMENT_ID,
    )

    assert {claim.object for claim in delta.claims} == {"10", "20"}
    assert all(claim.conflicting for claim in delta.claims)
