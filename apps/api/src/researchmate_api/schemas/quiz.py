from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import Citation, Difficulty, SourceMode, SourceSummary


# 定义 Quiz API 请求体。
class QuizRequest(BaseModel):
    project_id: UUID
    prompt: str = Field(default="/quiz", min_length=1, max_length=4000)
    selected_mode: SourceMode = SourceMode.LOCAL_ONLY
    single_choice_count: int = Field(default=5, ge=0, le=20)
    short_answer_count: int = Field(default=3, ge=0, le=20)

    model_config = ConfigDict(use_enum_values=True)


# 定义单道测验题结构。
class QuizQuestion(BaseModel):
    id: UUID
    type: Literal["single_choice", "short_answer"]
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
    id: UUID
    mode: SourceMode
    sources: SourceSummary
    questions: list[QuizQuestion] = Field(min_length=1, max_length=40)

    model_config = ConfigDict(use_enum_values=True)


# 定义 Quiz API 响应体。
class QuizResponse(BaseModel):
    quiz_set: QuizSet
    run_id: UUID
    trace_id: UUID
    validation_status: Literal["passed", "failed", "retrying"]


# 定义 Quiz 历史响应。
class QuizHistoryResponse(BaseModel):
    project_id: UUID
    quiz_sets: list[QuizSet] = Field(default_factory=list, max_length=100)
