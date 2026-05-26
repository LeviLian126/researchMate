from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from researchmate_api.schemas.common import Citation, SourceMode, SourceSummary


# 定义 Ask API 请求体。
class AskRequest(BaseModel):
    project_id: UUID
    message: str = Field(min_length=1, max_length=8000)
    selected_mode: SourceMode = SourceMode.AUTO

    model_config = ConfigDict(use_enum_values=True)


# 定义结构化回答中的单条 claim。
class Claim(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=1200)
    citation_ids: list[UUID] = Field(default_factory=list, max_length=12)


# 定义 LLM 必须输出的可溯源回答结构。
class GroundedAnswer(BaseModel):
    mode: SourceMode
    sources: SourceSummary
    answer: str = Field(min_length=1, max_length=16000)
    claims: list[Claim] = Field(default_factory=list, max_length=80)
    citations: list[Citation] = Field(default_factory=list, max_length=80)

    model_config = ConfigDict(use_enum_values=True)


# 定义 Ask API 响应体。
class AskResponse(BaseModel):
    run_id: UUID
    answer: str = Field(min_length=1, max_length=16000)
    mode: SourceMode
    sources: SourceSummary
    citations: list[Citation] = Field(default_factory=list, max_length=80)
    trace_id: UUID
    validation_status: Literal["passed", "failed", "retrying"]

    model_config = ConfigDict(use_enum_values=True)

