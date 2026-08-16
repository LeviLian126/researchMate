"""Define answer-feedback review and immutable evaluation-promotion contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import (
    MAX_ANSWER_LENGTH,
    MAX_FEEDBACK_COMMENT_LENGTH,
    MAX_MESSAGE_LENGTH,
    SourceType,
)

FeedbackRating = Literal["helpful", "not_helpful"]
FeedbackCategory = Literal[
    "incorrect_answer",
    "incorrect_citation",
    "missing_context",
    "irrelevant",
    "unsafe",
    "other",
]


def feedback_source_type(value: object, document_id: object = None) -> SourceType:
    """Normalize trusted provenance while remaining compatible with legacy traces."""
    if value == SourceType.LOCAL_DOC or value == SourceType.LOCAL_DOC.value:
        return SourceType.LOCAL_DOC
    if value == SourceType.WEB_PAGE or value == SourceType.WEB_PAGE.value:
        return SourceType.WEB_PAGE
    return SourceType.LOCAL_DOC if document_id else SourceType.WEB_PAGE


class FeedbackEvidence(BaseModel):
    """Expose one bounded retrieved candidate for explicit reviewer selection."""

    chunk_id: UUID
    source_type: SourceType
    source_title: str | None = Field(default=None, max_length=300)
    page_no: int | None = Field(default=None, ge=1)
    excerpt: str | None = Field(default=None, max_length=240)


@dataclass(frozen=True)
class FeedbackSourceContext:
    """Carry trusted persisted Ask context into the local feedback adapter."""

    ask_run_id: UUID
    user_id: UUID
    project_id: UUID
    conversation_id: UUID
    question: str
    answer: str
    citation_chunk_ids: list[UUID]
    retrieved_chunk_ids: list[UUID]
    retrieved_evidence: list[FeedbackEvidence]


class AnswerFeedbackUpsert(BaseModel):
    """Validate one replaceable rating for an owned answer run."""

    rating: FeedbackRating
    category: FeedbackCategory | None = None
    comment: str | None = Field(default=None, max_length=MAX_FEEDBACK_COMMENT_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_optional_comment(self) -> AnswerFeedbackUpsert:
        """Trim optional comments and remove empty values before persistence."""
        if self.comment is not None:
            self.comment = self.comment.strip() or None
        return self


class AnswerFeedbackRecord(BaseModel):
    """Expose bounded feedback context for the owner and developer review flow."""

    feedback_id: UUID
    ask_run_id: UUID
    project_id: UUID
    conversation_id: UUID
    rating: FeedbackRating
    category: FeedbackCategory | None = None
    comment: str | None = Field(default=None, max_length=MAX_FEEDBACK_COMMENT_LENGTH)
    question: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_LENGTH)
    citation_chunk_ids: list[UUID] = Field(default_factory=list, max_length=80)
    retrieved_chunk_ids: list[UUID] = Field(default_factory=list, max_length=80)
    retrieved_evidence: list[FeedbackEvidence] = Field(default_factory=list, max_length=80)
    status: Literal["new", "promoted"]
    promoted_case_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class AnswerFeedbackListResponse(BaseModel):
    """Wrap a bounded developer review queue."""

    items: list[AnswerFeedbackRecord] = Field(default_factory=list, max_length=100)


class FeedbackPromotionCreate(BaseModel):
    """Require a reviewer-selected evidence set before creating a regression case."""

    expected_chunk_ids: list[UUID] = Field(min_length=1, max_length=80)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_duplicate_evidence(self) -> FeedbackPromotionCreate:
        """Keep promoted relevance judgments deterministic and non-redundant."""
        if len(set(self.expected_chunk_ids)) != len(self.expected_chunk_ids):
            raise ValueError("expected_chunk_ids must be unique")
        return self


class FeedbackPromotionResult(BaseModel):
    """Return the immutable evaluation dataset version created by promotion."""

    dataset_id: UUID
    dataset_version: int = Field(ge=1)
    dataset_status: Literal["frozen"] = "frozen"
    case_id: UUID
    evaluation_run_id: UUID
    evaluation_status: Literal["pending"] = "pending"
    evaluation_status_url: str
