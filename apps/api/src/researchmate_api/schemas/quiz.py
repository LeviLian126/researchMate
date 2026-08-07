"""Define source-backed Quiz request, question, coverage, and history contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import MAX_TEXT_LENGTH, Citation, Difficulty, SourceSummary


# Define the Quiz API request body.
class QuizRequest(BaseModel):
    """Separate generation instructions from optional topic retrieval semantics."""

    project_id: UUID
    prompt: str = Field(default="Generate a quiz from my documents.", min_length=1, max_length=4000)
    topic_query: str | None = Field(default=None, min_length=1, max_length=1000)
    resource_scope: Literal["all_ready_documents", "topic"] = "all_ready_documents"
    single_choice_count: int = Field(default=3, ge=0, le=20)
    fill_blank_count: int = Field(default=2, ge=0, le=20)
    subjective_count: int = Field(default=2, ge=0, le=20)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_question_total(self) -> QuizRequest:
        """Keep the requested quiz inside the response and provider bounds."""
        total = self.single_choice_count + self.fill_blank_count + self.subjective_count
        if not 1 <= total <= 40:
            raise ValueError("quiz question count must be between 1 and 40")
        if self.resource_scope == "topic" and not self.topic_query:
            raise ValueError("topic_query is required when resource_scope is topic")
        return self


# Define the structure for a single quiz question.
class QuizQuestion(BaseModel):
    """Represent one validated question and its source citations."""

    id: UUID
    type: Literal["single_choice", "fill_blank", "subjective"]
    question: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    options: list[str] | None = Field(default=None, max_length=4)
    answer: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    explanation: str = Field(min_length=1, max_length=2000)
    difficulty: Difficulty = Difficulty.MEDIUM
    source_citations: list[Citation] = Field(default_factory=list, max_length=12)

    model_config = ConfigDict(use_enum_values=True)

    # Validate that single-choice questions contain exactly four options.
    @model_validator(mode="after")
    def validate_single_choice_options(self) -> QuizQuestion:
        if self.type == "single_choice" and (self.options is None or len(self.options) != 4):
            raise ValueError("single_choice questions require exactly 4 options")
        return self


# Define the QuizSet structured output.
class QuizSet(BaseModel):
    """Group one generated set of source-backed questions."""

    id: UUID
    sources: SourceSummary
    questions: list[QuizQuestion] = Field(min_length=1, max_length=40)

    model_config = ConfigDict(use_enum_values=True)


# Define the Quiz API response body.
class QuizCoverage(BaseModel):
    """Report how much of the available document set entered generation context."""

    documents_available: int = Field(ge=0)
    documents_covered: int = Field(ge=0)
    chunks_selected: int = Field(ge=0, le=50)
    truncated: bool = False


class QuizResponse(BaseModel):
    """Return a generated quiz with durable identifiers and honest coverage."""

    quiz_set: QuizSet
    run_id: UUID
    trace_id: UUID
    validation_status: Literal["passed", "failed", "retrying"]
    coverage: QuizCoverage


# Define the Quiz history response.
class QuizHistoryResponse(BaseModel):
    """Return bounded saved Quiz sets for one owned workspace."""

    project_id: UUID
    quiz_sets: list[QuizSet] = Field(default_factory=list, max_length=100)
