"""Verify deterministic canonical Wiki mutation planning and application."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.services._store_models import WikiPage
from researchmate_api.services.wiki_knowledge import (
    DocumentKnowledgeDelta,
    KnowledgeClaim,
    KnowledgeEntity,
    KnowledgeRelation,
    WikiMutationAction,
)
from researchmate_api.services.wiki_merge import apply_wiki_mutations, plan_wiki_mutations

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("20000000-0000-4000-8000-000000000001")
DOCUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
OLD_CHUNK_ID = UUID("40000000-0000-4000-8000-000000000001")
NEW_CHUNK_ID = UUID("40000000-0000-4000-8000-000000000002")


def _claim(value: str, chunk_id: UUID = NEW_CHUNK_ID) -> KnowledgeClaim:
    return KnowledgeClaim(
        subject="Hybrid Retrieval",
        predicate="backend",
        object=value,
        source_chunk_ids=[chunk_id],
    )


def _existing_page() -> WikiPage:
    old_claim = _claim("Postgres", OLD_CHUNK_ID)
    return WikiPage(
        id=UUID("50000000-0000-4000-8000-000000000001"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Hybrid Search",
        page_type="concept",
        summary="Combines retrieval modes.",
        content="Old content",
        aliases=["Hybrid Retrieval"],
        claims=[old_claim.model_dump(mode="json")],
        source_chunk_ids=[OLD_CHUNK_ID],
    )


def _delta(*, claim_value: str = "Postgres") -> DocumentKnowledgeDelta:
    return DocumentKnowledgeDelta(
        document_id=DOCUMENT_ID,
        title="New source",
        summary="Hybrid retrieval combines lexical and semantic evidence.",
        entities=[
            KnowledgeEntity(
                name="Qdrant Hybrid Search",
                aliases=["Hybrid Retrieval"],
                source_chunk_ids=[NEW_CHUNK_ID],
            ),
            KnowledgeEntity(name="Reranking", source_chunk_ids=[NEW_CHUNK_ID]),
        ],
        claims=[_claim(claim_value)],
        relations=[
            KnowledgeRelation(
                source="Hybrid Retrieval",
                relation="uses",
                target="Reranking",
                source_chunk_ids=[NEW_CHUNK_ID],
            )
        ],
        source_chunk_ids=[NEW_CHUNK_ID],
    )


def test_alias_resolution_updates_existing_page_and_creates_only_new_concept() -> None:
    existing = _existing_page()

    mutations = plan_wiki_mutations(_delta(), [existing])

    assert [mutation.action for mutation in mutations] == [
        WikiMutationAction.UPDATE,
        WikiMutationAction.CREATE,
    ]
    assert mutations[0].target_page_id == existing.id
    assert mutations[0].canonical_title == "Hybrid Search"


def test_incremental_apply_preserves_identity_and_merges_provenance_idempotently() -> None:
    existing = _existing_page()
    mutations = plan_wiki_mutations(_delta(), [existing])

    first = apply_wiki_mutations(
        mutations,
        [existing],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )
    replay = apply_wiki_mutations(
        plan_wiki_mutations(_delta(), first),
        first,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    updated = first[0]
    assert updated.id == existing.id
    assert updated.source_chunk_ids == [OLD_CHUNK_ID, NEW_CHUNK_ID]
    assert len(updated.claims) == 1
    assert replay == []


def test_conflicting_claim_preserves_old_and_new_claim_provenance() -> None:
    existing = _existing_page()
    mutations = plan_wiki_mutations(_delta(claim_value="Qdrant"), [existing])

    assert mutations[0].action is WikiMutationAction.CONFLICT
    pages = apply_wiki_mutations(
        mutations,
        [existing],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )
    claims = pages[0].claims
    assert {claim["object"] for claim in claims} == {"Postgres", "Qdrant"}
    assert {
        UUID(str(source_id)) for claim in claims for source_id in claim["source_chunk_ids"]
    } == {
        OLD_CHUNK_ID,
        NEW_CHUNK_ID,
    }
    assert "[conflict]" in pages[0].content


def test_only_affected_pages_are_returned() -> None:
    existing = _existing_page()
    unrelated = WikiPage(
        id=UUID("50000000-0000-4000-8000-000000000002"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Unrelated",
        page_type="concept",
        content="Untouched",
        source_chunk_ids=[OLD_CHUNK_ID],
    )

    mutations = plan_wiki_mutations(_delta(), [existing, unrelated])
    affected = apply_wiki_mutations(
        mutations,
        [existing, unrelated],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert unrelated.id not in {page.id for page in affected}


def test_relation_only_change_is_classified_as_link() -> None:
    existing = _existing_page()
    delta = DocumentKnowledgeDelta(
        document_id=DOCUMENT_ID,
        title="Relation source",
        entities=[
            KnowledgeEntity(
                name="Hybrid Search",
                aliases=["Hybrid Retrieval"],
                source_chunk_ids=[OLD_CHUNK_ID],
            )
        ],
        relations=[
            KnowledgeRelation(
                source="Hybrid Retrieval",
                relation="uses",
                target="Reranking",
                source_chunk_ids=[NEW_CHUNK_ID],
            )
        ],
        source_chunk_ids=[NEW_CHUNK_ID],
    )

    mutations = plan_wiki_mutations(delta, [existing])

    assert len(mutations) == 1
    assert mutations[0].action is WikiMutationAction.LINK


def test_candidate_resolution_reuses_unaliased_canonical_page() -> None:
    existing = _existing_page()
    existing.aliases = []
    delta = DocumentKnowledgeDelta(
        document_id=DOCUMENT_ID,
        title="Candidate source",
        entities=[
            KnowledgeEntity(
                name="Qdrant Hybrid Search",
                source_chunk_ids=[NEW_CHUNK_ID],
            )
        ],
        source_chunk_ids=[NEW_CHUNK_ID],
    )

    mutations = plan_wiki_mutations(delta, [existing])

    assert len(mutations) == 1
    assert mutations[0].target_page_id == existing.id
    assert mutations[0].action is WikiMutationAction.UPDATE


def test_legacy_page_content_survives_first_structured_update() -> None:
    existing = _existing_page()
    existing.summary = ""
    existing.claims = []
    existing.content = "Legacy fact that must remain available."

    pages = apply_wiki_mutations(
        plan_wiki_mutations(_delta(), [existing]),
        [existing],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert "Legacy fact that must remain available." in pages[0].content
    assert "Hybrid retrieval combines lexical and semantic evidence." in pages[0].content


def test_duplicate_exact_pages_are_folded_into_one_canonical_page() -> None:
    primary = _existing_page()
    duplicate = WikiPage(
        id=UUID("50000000-0000-4000-8000-000000000003"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Hybrid Retrieval",
        page_type="concept",
        content="Duplicate knowledge",
        aliases=["Hybrid Search"],
        source_chunk_ids=[NEW_CHUNK_ID],
    )

    mutations = plan_wiki_mutations(_delta(), [primary, duplicate])
    pages = apply_wiki_mutations(
        mutations,
        [primary, duplicate],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert mutations[0].merged_page_ids == [duplicate.id]
    assert len([page for page in pages if page.title == "Hybrid Search"]) == 1
    assert NEW_CHUNK_ID in pages[0].source_chunk_ids


def test_summary_and_typed_relation_are_rendered_and_persisted() -> None:
    pages = apply_wiki_mutations(
        plan_wiki_mutations(_delta(), [_existing_page()]),
        [_existing_page()],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert "Hybrid retrieval combines lexical and semantic evidence." in pages[0].summary
    assert pages[0].relations[0]["relation"] == "uses"
    assert "Hybrid Retrieval — uses → [[Reranking]]" in pages[0].content


def test_alias_entities_coalesce_to_one_canonical_write_without_losing_claims() -> None:
    delta = DocumentKnowledgeDelta(
        document_id=DOCUMENT_ID,
        title="Alias source",
        entities=[
            KnowledgeEntity(name="Hybrid Search", source_chunk_ids=[NEW_CHUNK_ID]),
            KnowledgeEntity(name="Hybrid Retrieval", source_chunk_ids=[NEW_CHUNK_ID]),
        ],
        claims=[
            KnowledgeClaim(
                subject="Hybrid Search",
                predicate="claim-a",
                object="A",
                source_chunk_ids=[NEW_CHUNK_ID],
            ),
            KnowledgeClaim(
                subject="Hybrid Retrieval",
                predicate="claim-b",
                object="B",
                source_chunk_ids=[NEW_CHUNK_ID],
            ),
        ],
        source_chunk_ids=[NEW_CHUNK_ID],
    )

    mutations = plan_wiki_mutations(delta, [_existing_page()])
    pages = apply_wiki_mutations(
        mutations,
        [_existing_page()],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert len(mutations) == 1
    assert len(pages) == 1
    assert {claim["predicate"] for claim in pages[0].claims} >= {"claim-a", "claim-b"}


def test_duplicate_legacy_content_is_preserved_before_duplicate_row_deletion() -> None:
    primary = _existing_page()
    duplicate = WikiPage(
        id=UUID("50000000-0000-4000-8000-000000000004"),
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        title="Hybrid Retrieval",
        page_type="concept",
        content="Unique legacy detail from the duplicate page.",
        aliases=["Hybrid Search"],
        source_chunk_ids=[NEW_CHUNK_ID],
    )

    pages = apply_wiki_mutations(
        plan_wiki_mutations(_delta(), [primary, duplicate]),
        [primary, duplicate],
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        generation=2,
    )

    assert "Combines retrieval modes." in pages[0].content
    assert "Unique legacy detail from the duplicate page." in pages[0].content
