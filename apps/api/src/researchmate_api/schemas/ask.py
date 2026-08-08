"""Define the unified Ask request, grounded proposal, and response contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from researchmate_api.schemas.common import (
    MAX_ANSWER_LENGTH,
    MAX_FALLBACK_REASON_LENGTH,
    MAX_ID_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_TEXT_LENGTH,
    Citation,
    SourceSummary,
)


# Define the Ask API request body.
class AskRequest(BaseModel):
    """Accept one bounded chat intent and optional evidence boundaries."""

    project_id: UUID
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    web_enabled: bool = False

    model_config = ConfigDict(extra="forbid")


# Define a single claim inside a structured answer.
class Claim(BaseModel):
    """Represent one answer claim and its server-issued citation identifiers."""

    id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    citation_ids: list[UUID] = Field(default_factory=list, max_length=12)


# Define the traceable grounded-answer structure that the LLM must output.
class GroundedAnswer(BaseModel):
    """Validate a provider answer against the grounded response contract."""

    sources: SourceSummary
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_LENGTH)
    claims: list[Claim] = Field(default_factory=list, max_length=80)
    citations: list[Citation] = Field(default_factory=list, max_length=80)

    model_config = ConfigDict(use_enum_values=True)


# Define the Ask API response body.
class AskResponse(BaseModel):
    """Return persisted Ask identifiers, evidence, and explicit degradation state."""

    run_id: UUID
    conversation_id: UUID
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_LENGTH)
    sources: SourceSummary
    citations: list[Citation] = Field(default_factory=list, max_length=80)
    trace_id: UUID
    validation_status: Literal["passed", "failed", "retrying"]
    rerank_degraded: bool = False
    retrieval_degraded: bool = False
    summary_degraded: bool = False
    fallback_reason: str | None = Field(default=None, max_length=MAX_FALLBACK_REASON_LENGTH)

    model_config = ConfigDict(use_enum_values=True)
