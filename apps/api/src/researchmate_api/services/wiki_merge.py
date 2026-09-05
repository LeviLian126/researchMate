"""Plan and apply deterministic project-level canonical Wiki mutations."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from researchmate_api.schemas.common import (
    WIKI_CANONICAL_TOKEN_OVERLAP,
    WIKI_MAX_SUMMARY_LENGTH,
    SourceType,
)
from researchmate_api.services._store_models import WikiPage
from researchmate_api.services.retrieval import bm25_candidates, tokenize
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.wiki_knowledge import (
    DocumentKnowledgeDelta,
    KnowledgeClaim,
    KnowledgeEntity,
    KnowledgeRelation,
    WikiMutation,
    WikiMutationAction,
)


def normalize_wiki_name(value: str) -> str:
    """Normalize a title or alias for deterministic exact canonical matching."""
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def _exact_matches(names: list[str], pages: list[WikiPage]) -> list[WikiPage]:
    """Return deterministic title or alias matches, including legacy duplicates."""
    normalized_names = {normalize_wiki_name(name) for name in names}
    matches = [
        page
        for page in pages
        if normalized_names & {normalize_wiki_name(name) for name in [page.title, *page.aliases]}
    ]
    if len(matches) > 1:
        first_names = {
            normalize_wiki_name(name) for name in [matches[0].title, *matches[0].aliases]
        }
        if any(normalize_wiki_name(page.title) not in first_names for page in matches[1:]):
            raise ValueError("AMBIGUOUS_CANONICAL_ALIASES")
    return sorted(matches, key=lambda page: (page.created_at, str(page.id)))


def _candidate_page(names: list[str], pages: list[WikiPage]) -> WikiPage | None:
    """Resolve one unambiguous BM25-ranked lexical candidate or fail closed."""
    query = " ".join(names)
    query_tokens = set(tokenize(query))
    if len(query_tokens) < 2:
        return None
    eligible: list[WikiPage] = []
    chunks: list[ChunkEntry] = []
    for page in pages:
        if page.page_type == "document_overview":
            continue
        candidate_tokens = set(tokenize(" ".join([page.title, *page.aliases])))
        overlap = query_tokens & candidate_tokens
        smaller = min(len(query_tokens), len(candidate_tokens))
        if smaller < 2 or len(overlap) / smaller < WIKI_CANONICAL_TOKEN_OVERLAP:
            continue
        eligible.append(page)
        chunks.append(
            ChunkEntry(
                id=page.id,
                user_id=page.user_id,
                project_id=page.project_id,
                document_id=page.document_id,
                source_type=SourceType.LOCAL_DOC,
                source_title=page.title,
                text=" ".join(page.aliases),
                has_vector=False,
            )
        )
    ranked = bm25_candidates(chunks, query, limit=len(chunks))
    if not ranked:
        return None
    if len(ranked) > 1:
        raise ValueError("AMBIGUOUS_CANONICAL_CANDIDATES")
    eligible_by_id = {page.id: page for page in eligible}
    return eligible_by_id[ranked[0].chunk.id]


def plan_wiki_mutations(
    delta: DocumentKnowledgeDelta,
    existing_pages: list[WikiPage],
) -> list[WikiMutation]:
    """Classify delta knowledge as CREATE, UPDATE, LINK, or CONFLICT."""
    page_by_name: dict[str, WikiPage] = {}
    for page in existing_pages:
        for name in [page.title, *page.aliases]:
            page_by_name.setdefault(normalize_wiki_name(name), page)

    entities = _entities_with_claim_subjects(delta)
    mutations: list[WikiMutation] = []
    for entity in entities:
        names = [entity.name, *entity.aliases]
        exact_matches = _exact_matches(
            names, [page for page in existing_pages if page.page_type != "document_overview"]
        )
        existing = exact_matches[0] if exact_matches else _candidate_page(names, existing_pages)
        merged_page_ids = [page.id for page in exact_matches[1:]]
        canonical_title = existing.title if existing is not None else entity.name
        incoming_aliases = [
            value
            for value in names
            if normalize_wiki_name(value) != normalize_wiki_name(canonical_title)
        ]
        entity_names = {normalize_wiki_name(value) for value in names}
        claims = [
            claim.model_copy(update={"subject": canonical_title})
            for claim in delta.claims
            if normalize_wiki_name(claim.subject) in entity_names
        ]
        links = _canonical_links(entity_names, delta, page_by_name)
        relations = [
            relation
            for relation in delta.relations
            if normalize_wiki_name(relation.source) in entity_names
            or normalize_wiki_name(relation.target) in entity_names
        ]
        source_ids = _unique_ids(
            [
                *entity.source_chunk_ids,
                *(source_id for claim in claims for source_id in claim.source_chunk_ids),
                *(
                    source_id
                    for relation in delta.relations
                    if normalize_wiki_name(relation.source) in entity_names
                    or normalize_wiki_name(relation.target) in entity_names
                    for source_id in relation.source_chunk_ids
                ),
            ]
        )
        if existing is None:
            action = WikiMutationAction.CREATE
        else:
            conflicts = _conflicting_keys(existing, claims)
            if conflicts:
                action = WikiMutationAction.CONFLICT
                claims = [
                    claim.model_copy(update={"conflicting": _claim_key(claim) in conflicts})
                    for claim in claims
                ]
            elif (
                _has_new_claims(existing, claims)
                or set(incoming_aliases) - set(existing.aliases)
                or merged_page_ids
            ):
                action = WikiMutationAction.UPDATE
            elif set(links) - set(existing.links) or _merge_relations(
                [KnowledgeRelation.model_validate(item) for item in existing.relations], relations
            ) != [KnowledgeRelation.model_validate(item) for item in existing.relations]:
                action = WikiMutationAction.LINK
            elif set(source_ids) - set(existing.source_chunk_ids):
                action = WikiMutationAction.UPDATE
            else:
                continue
        mutations.append(
            WikiMutation(
                action=action,
                canonical_title=canonical_title,
                target_page_id=existing.id if existing is not None else None,
                merged_page_ids=merged_page_ids,
                summary=delta.summary,
                aliases=_unique_text([*incoming_aliases, *(existing.aliases if existing else [])]),
                claims=claims,
                relations=relations,
                links=links,
                source_chunk_ids=source_ids,
            )
        )
    return _coalesce_mutations(mutations)


def apply_wiki_mutations(
    mutations: list[WikiMutation],
    existing_pages: list[WikiPage],
    *,
    user_id: UUID,
    project_id: UUID,
    document_id: UUID,
    generation: int,
) -> list[WikiPage]:
    """Return only created or updated pages named by the mutation plan."""
    existing_by_id = {page.id: page for page in existing_pages}
    affected: list[WikiPage] = []
    now = datetime.now(UTC)
    for mutation in mutations:
        existing = (
            existing_by_id.get(mutation.target_page_id)
            if mutation.target_page_id is not None
            else None
        )
        merged_existing = _merge_existing_pages(existing, mutation.merged_page_ids, existing_by_id)
        old_claims = (
            [
                _claim_from_dict(item).model_copy(update={"subject": mutation.canonical_title})
                for item in merged_existing.claims
            ]
            if merged_existing
            else []
        )
        claims = _merge_claims(old_claims, mutation.claims)
        relations = _merge_relations(
            [
                KnowledgeRelation.model_validate(item)
                for item in (merged_existing.relations if merged_existing else [])
            ],
            mutation.relations,
        )
        aliases = _unique_text(
            [*(merged_existing.aliases if merged_existing else []), *mutation.aliases]
        )
        links = _unique_text([*(merged_existing.links if merged_existing else []), *mutation.links])
        source_ids = _unique_ids(
            [
                *(merged_existing.source_chunk_ids if merged_existing else []),
                *mutation.source_chunk_ids,
            ]
        )
        legacy_content = (
            merged_existing.content
            if merged_existing and not merged_existing.summary and not merged_existing.claims
            else ""
        )
        summary = _merge_summary(
            merged_existing.summary if merged_existing else "",
            legacy_content,
            mutation.summary,
            mutation.canonical_title,
        )
        legacy_notes = _unique_text(
            [
                *(merged_existing.legacy_content if merged_existing else []),
                legacy_content,
            ]
        )
        content = _render_page(summary, claims, relations, links)
        if legacy_notes:
            content += "\n\n## Legacy source notes\n\n" + "\n\n".join(legacy_notes)
        affected.append(
            WikiPage(
                id=merged_existing.id if merged_existing else uuid4(),
                user_id=user_id,
                project_id=project_id,
                document_id=merged_existing.document_id if merged_existing else document_id,
                title=mutation.canonical_title,
                page_type=merged_existing.page_type if merged_existing else "concept",
                summary=summary,
                content=content,
                legacy_content=legacy_notes,
                aliases=aliases,
                links=links,
                claims=[claim.model_dump(mode="json") for claim in claims],
                relations=[relation.model_dump(mode="json") for relation in relations],
                source_chunk_ids=source_ids,
                references=_merge_references(
                    merged_existing.references if merged_existing else [], claims, relations
                ),
                generation=generation,
                created_at=merged_existing.created_at if merged_existing else now,
                updated_at=now,
            )
        )
    return affected


def _entities_with_claim_subjects(delta: DocumentKnowledgeDelta) -> list[KnowledgeEntity]:
    entities = list(delta.entities)
    known = {
        normalize_wiki_name(name) for entity in entities for name in [entity.name, *entity.aliases]
    }
    for claim in delta.claims:
        normalized = normalize_wiki_name(claim.subject)
        if normalized not in known:
            entities.append(
                KnowledgeEntity(name=claim.subject, source_chunk_ids=claim.source_chunk_ids)
            )
            known.add(normalized)
    return entities


def _canonical_links(
    entity_names: set[str],
    delta: DocumentKnowledgeDelta,
    page_by_name: dict[str, WikiPage],
) -> list[str]:
    links: list[str] = []
    for relation in delta.relations:
        source = normalize_wiki_name(relation.source)
        target = normalize_wiki_name(relation.target)
        if source in entity_names:
            target_page = page_by_name.get(target)
            links.append(target_page.title if target_page is not None else relation.target)
        if target in entity_names:
            source_page = page_by_name.get(source)
            links.append(source_page.title if source_page is not None else relation.source)
    return _unique_text(links)


def _claim_key(claim: KnowledgeClaim) -> tuple[str, str]:
    return normalize_wiki_name(claim.subject), normalize_wiki_name(claim.predicate)


def _conflicting_keys(existing: WikiPage, incoming: list[KnowledgeClaim]) -> set[tuple[str, str]]:
    old = [
        _claim_from_dict(item).model_copy(update={"subject": existing.title})
        for item in existing.claims
    ]
    old_by_key = {_claim_key(claim): claim.object.casefold().strip() for claim in old}
    return {
        _claim_key(claim)
        for claim in incoming
        if _claim_key(claim) in old_by_key
        and old_by_key[_claim_key(claim)] != claim.object.casefold().strip()
    }


def _has_new_claims(existing: WikiPage, incoming: list[KnowledgeClaim]) -> bool:
    old = [
        _claim_from_dict(item).model_copy(update={"subject": existing.title})
        for item in existing.claims
    ]
    old_by_value = {
        (
            *_claim_key(claim),
            claim.object.casefold().strip(),
            tuple(sorted(claim.qualifiers.items())),
        ): set(claim.source_chunk_ids)
        for claim in old
    }
    for claim in incoming:
        key = (
            *_claim_key(claim),
            claim.object.casefold().strip(),
            tuple(sorted(claim.qualifiers.items())),
        )
        if key not in old_by_value or not set(claim.source_chunk_ids) <= old_by_value[key]:
            return True
    return False


def _merge_claims(
    old: list[KnowledgeClaim], incoming: list[KnowledgeClaim]
) -> list[KnowledgeClaim]:
    merged: dict[tuple[str, str, str, tuple[tuple[str, str], ...]], KnowledgeClaim] = {}
    for claim in [*old, *incoming]:
        key = (
            *_claim_key(claim),
            claim.object.casefold().strip(),
            tuple(sorted(claim.qualifiers.items())),
        )
        prior = merged.get(key)
        if prior is None:
            merged[key] = claim
        else:
            merged[key] = prior.model_copy(
                update={
                    "source_chunk_ids": _unique_ids(
                        [*prior.source_chunk_ids, *claim.source_chunk_ids]
                    ),
                    "conflicting": prior.conflicting or claim.conflicting,
                }
            )
    value_counts: dict[tuple[str, str], set[str]] = {}
    for claim in merged.values():
        value_counts.setdefault(_claim_key(claim), set()).add(claim.object.casefold().strip())
    return [
        claim.model_copy(
            update={"conflicting": claim.conflicting or len(value_counts[_claim_key(claim)]) > 1}
        )
        for claim in merged.values()
    ]


def _merge_relations(
    old: list[KnowledgeRelation], incoming: list[KnowledgeRelation]
) -> list[KnowledgeRelation]:
    """Merge typed relations while retaining all source provenance."""
    merged: dict[tuple[str, str, str], KnowledgeRelation] = {}
    for relation in [*old, *incoming]:
        key = (
            normalize_wiki_name(relation.source),
            normalize_wiki_name(relation.relation),
            normalize_wiki_name(relation.target),
        )
        prior = merged.get(key)
        if prior is None:
            merged[key] = relation
        else:
            merged[key] = prior.model_copy(
                update={
                    "source_chunk_ids": _unique_ids(
                        [*prior.source_chunk_ids, *relation.source_chunk_ids]
                    )
                }
            )
    return list(merged.values())


def _claim_from_dict(value: dict[str, object]) -> KnowledgeClaim:
    return KnowledgeClaim.model_validate(value)


def _render_page(
    summary: str,
    claims: list[KnowledgeClaim],
    relations: list[KnowledgeRelation],
    links: list[str],
) -> str:
    lines = [summary.strip()]
    if claims:
        lines.extend(["", "## Claims"])
        for claim in claims:
            marker = " [conflict]" if claim.conflicting else ""
            lines.append(f"- {claim.subject} — {claim.predicate}: {claim.object}{marker}")
    if relations:
        lines.extend(["", "## Relations"])
        lines.extend(
            f"- {relation.source} — {relation.relation} → [[{relation.target}]]"
            for relation in relations
        )
    if links:
        lines.extend(["", "## Related", *[f"- [[{link}]]" for link in links]])
    return "\n".join(lines).strip()


def _merge_references(
    existing: list[dict[str, object]],
    claims: list[KnowledgeClaim],
    relations: list[KnowledgeRelation],
) -> list[dict[str, object]]:
    references = list(existing)
    seen = {str(item.get("chunk_id")) for item in references}
    for item in [*claims, *relations]:
        for chunk_id in item.source_chunk_ids:
            if str(chunk_id) not in seen:
                references.append({"chunk_id": str(chunk_id)})
                seen.add(str(chunk_id))
    return references


def _merge_summary(*values: str) -> str:
    """Combine distinct summaries and bound the durable page summary."""
    merged = "\n\n".join(_unique_text([value.strip() for value in values]))
    return merged[:WIKI_MAX_SUMMARY_LENGTH].rstrip()


def _merge_existing_pages(
    primary: WikiPage | None,
    merged_page_ids: list[UUID],
    pages_by_id: dict[UUID, WikiPage],
) -> WikiPage | None:
    """Fold legacy duplicate pages into the selected canonical page."""
    if primary is None or not merged_page_ids:
        return primary
    duplicates = [pages_by_id[page_id] for page_id in merged_page_ids if page_id in pages_by_id]
    claims = [item for page in [primary, *duplicates] for item in page.claims]
    relations = [item for page in [primary, *duplicates] for item in page.relations]
    legacy_contents = [
        page.content for page in [primary, *duplicates] if not page.summary and not page.claims
    ]
    return WikiPage(
        id=primary.id,
        user_id=primary.user_id,
        project_id=primary.project_id,
        document_id=primary.document_id,
        title=primary.title,
        page_type=primary.page_type,
        content=primary.content,
        summary=_merge_summary(
            *(page.summary for page in [primary, *duplicates]), *legacy_contents
        ),
        aliases=_unique_text(
            [
                *(page.title for page in duplicates),
                *(alias for page in [primary, *duplicates] for alias in page.aliases),
            ]
        ),
        links=_unique_text([link for page in [primary, *duplicates] for link in page.links]),
        claims=claims,
        relations=relations,
        legacy_content=_unique_text(
            [
                *(note for page in [primary, *duplicates] for note in page.legacy_content),
                *legacy_contents,
            ]
        ),
        source_chunk_ids=_unique_ids(
            [source_id for page in [primary, *duplicates] for source_id in page.source_chunk_ids]
        ),
        references=[reference for page in [primary, *duplicates] for reference in page.references],
        generation=max(page.generation for page in [primary, *duplicates]),
        created_at=min(page.created_at for page in [primary, *duplicates]),
        updated_at=max(page.updated_at for page in [primary, *duplicates]),
    )


def _coalesce_mutations(mutations: list[WikiMutation]) -> list[WikiMutation]:
    """Collapse all changes for one canonical target into one durable write."""
    grouped: dict[tuple[str, str], WikiMutation] = {}
    action_priority = {
        WikiMutationAction.CREATE: 0,
        WikiMutationAction.LINK: 1,
        WikiMutationAction.UPDATE: 2,
        WikiMutationAction.CONFLICT: 3,
    }
    for mutation in mutations:
        key = (
            "id" if mutation.target_page_id is not None else "title",
            str(mutation.target_page_id)
            if mutation.target_page_id is not None
            else normalize_wiki_name(mutation.canonical_title),
        )
        prior = grouped.get(key)
        if prior is None:
            grouped[key] = mutation
            continue
        action = (
            mutation.action
            if action_priority[mutation.action] > action_priority[prior.action]
            else prior.action
        )
        grouped[key] = prior.model_copy(
            update={
                "action": action,
                "merged_page_ids": _unique_ids([*prior.merged_page_ids, *mutation.merged_page_ids]),
                "summary": _merge_summary(prior.summary, mutation.summary),
                "aliases": _unique_text([*prior.aliases, *mutation.aliases]),
                "claims": _merge_claims(prior.claims, mutation.claims),
                "relations": _merge_relations(prior.relations, mutation.relations),
                "links": _unique_text([*prior.links, *mutation.links]),
                "source_chunk_ids": _unique_ids(
                    [*prior.source_chunk_ids, *mutation.source_chunk_ids]
                ),
            }
        )
    return list(grouped.values())


def _unique_ids(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


def _unique_text(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.strip()))
