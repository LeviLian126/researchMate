"""Define validated knowledge deltas and incremental Wiki mutation contracts."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import (
    WIKI_MAX_ALIASES,
    WIKI_MAX_CLAIM_PART_LENGTH,
    WIKI_MAX_CLAIMS,
    WIKI_MAX_DELTA_SOURCE_CHUNKS,
    WIKI_MAX_ENTITIES,
    WIKI_MAX_RELATIONS,
    WIKI_MAX_SUMMARY_LENGTH,
    WIKI_MAX_TITLE_LENGTH,
)


class KnowledgeEntity(BaseModel):
    """Represent one document entity and its observed aliases."""

    name: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    aliases: list[str] = Field(default_factory=list, max_length=WIKI_MAX_ALIASES)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)

    model_config = ConfigDict(extra="forbid")


class KnowledgeClaim(BaseModel):
    """Represent one provenance-bound subject-predicate-object statement."""

    subject: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    predicate: str = Field(min_length=1, max_length=WIKI_MAX_CLAIM_PART_LENGTH)
    object: str = Field(min_length=1, max_length=WIKI_MAX_CLAIM_PART_LENGTH)
    qualifiers: dict[str, str] = Field(default_factory=dict)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)
    conflicting: bool = False

    model_config = ConfigDict(extra="forbid")


class KnowledgeRelation(BaseModel):
    """Represent one directed relationship between named entities."""

    source: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    relation: str = Field(min_length=1, max_length=WIKI_MAX_CLAIM_PART_LENGTH)
    target: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)

    model_config = ConfigDict(extra="forbid")


class KnowledgeFragment(BaseModel):
    """Carry local knowledge extracted from one bounded source group."""

    section_context: str = Field(default="", max_length=WIKI_MAX_SUMMARY_LENGTH)
    entities: list[KnowledgeEntity] = Field(default_factory=list, max_length=WIKI_MAX_ENTITIES)
    claims: list[KnowledgeClaim] = Field(default_factory=list, max_length=WIKI_MAX_CLAIMS)
    relations: list[KnowledgeRelation] = Field(default_factory=list, max_length=WIKI_MAX_RELATIONS)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_item_provenance(self) -> KnowledgeFragment:
        """Reject knowledge items whose provenance escapes the fragment source set."""
        allowed = set(self.source_chunk_ids)
        items = [*self.entities, *self.claims, *self.relations]
        if any(not set(item.source_chunk_ids) <= allowed for item in items):
            raise ValueError("knowledge item provenance must belong to the fragment")
        return self


class DocumentKnowledgeDelta(BaseModel):
    """Represent document-wide canonical knowledge before project Wiki alignment."""

    document_id: UUID
    title: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    summary: str = Field(default="", max_length=WIKI_MAX_SUMMARY_LENGTH)
    argument_flow: list[str] = Field(default_factory=list, max_length=WIKI_MAX_ENTITIES)
    entities: list[KnowledgeEntity] = Field(default_factory=list, max_length=WIKI_MAX_ENTITIES)
    claims: list[KnowledgeClaim] = Field(default_factory=list, max_length=WIKI_MAX_CLAIMS)
    relations: list[KnowledgeRelation] = Field(default_factory=list, max_length=WIKI_MAX_RELATIONS)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)

    model_config = ConfigDict(extra="forbid")


class WikiMutationAction(StrEnum):
    """Name the only durable incremental Wiki mutation outcomes."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    LINK = "LINK"
    CONFLICT = "CONFLICT"


class WikiMutation(BaseModel):
    """Describe one affected canonical page without touching unrelated pages."""

    action: WikiMutationAction
    canonical_title: str = Field(min_length=1, max_length=WIKI_MAX_TITLE_LENGTH)
    target_page_id: UUID | None = None
    merged_page_ids: list[UUID] = Field(default_factory=list, max_length=WIKI_MAX_ENTITIES)
    summary: str = Field(default="", max_length=WIKI_MAX_SUMMARY_LENGTH)
    aliases: list[str] = Field(default_factory=list, max_length=WIKI_MAX_ALIASES)
    claims: list[KnowledgeClaim] = Field(default_factory=list, max_length=WIKI_MAX_CLAIMS)
    relations: list[KnowledgeRelation] = Field(default_factory=list, max_length=WIKI_MAX_RELATIONS)
    links: list[str] = Field(default_factory=list, max_length=WIKI_MAX_RELATIONS)
    source_chunk_ids: list[UUID] = Field(min_length=1, max_length=WIKI_MAX_DELTA_SOURCE_CHUNKS)

    model_config = ConfigDict(extra="forbid")
