"""Define source-backed Quiz request, question, coverage, and history contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import Citation, Difficulty, SourceSummary


# 定义 Quiz API 请求体。
class QuizRequest(BaseModel):
    """Separate generation instructions from optional topic retrieval semantics."""

    project_id: UUID
    prompt: str = Field(
        default="Generate a quiz from my documents.", min_length=1, max_length=4000
    )
    topic_query: str | None = Field(default=None, min_length=1, max_length=1000)
    resource_scope: Literal["all_ready_documents", "topic"] = "all_ready_documents"
    single_choice_count: int = Field(default=3, ge=0, le=20)
    fill_blank_count: int = Field(default=2, ge=0, le=20)
    subjective_count: int = Field(default=2, ge=0, le=20)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_question_total(self) -> "QuizRequest":
        """Keep the requested quiz inside the response and provider bounds."""
        total = (
            self.single_choice_count
            + self.fill_blank_count
            + self.subjective_count
        )
        if not 1 <= total <= 40:
            raise ValueError("quiz question count must be between 1 and 40")
        if self.resource_scope == "topic" and not self.topic_query:
            raise ValueError("topic_query is required when resource_scope is topic")
        return self


# 定义单道测验题结构。
class QuizQuestion(BaseModel):
    """Represent one validated question and its source citations."""
    id: UUID
    type: Literal["single_choice", "fill_blank", "subjective"]
    question: str = Field(min_length=1, max_length=1200)
    options: list[str] | None = Field(default=None, max_length=4)
    answer: str = Field(min_length=1, max_length=1200)
    explanation: str = Field(min_length=1, max_length=2000)
    difficulty: Difficulty = Difficulty.MEDIUM
    source_citations: list[Citation] = Field(default_factory=list, max_length=12)

    model_config = ConfigDict(use_enum_values=True)

    # 校验选择题必须恰好包含四个选项。
    @model_validator(mode="after")
    def validate_single_choice_options(self) -> "QuizQuestion":
        if self.type == "single_choice" and (self.options is None or len(self.options) != 4):
            raise ValueError("single_choice questions require exactly 4 options")
        return self


# 定义 QuizSet 结构化输出。
class QuizSet(BaseModel):
    """Group one generated set of source-backed questions."""
    id: UUID
    sources: SourceSummary
    questions: list[QuizQuestion] = Field(min_length=1, max_length=40)

    model_config = ConfigDict(use_enum_values=True)


# 定义 Quiz API 响应体。
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


# 定义 Quiz 历史响应。
class QuizHistoryResponse(BaseModel):
    """Return bounded saved Quiz sets for one owned workspace."""
    project_id: UUID
    quiz_sets: list[QuizSet] = Field(default_factory=list, max_length=100)
