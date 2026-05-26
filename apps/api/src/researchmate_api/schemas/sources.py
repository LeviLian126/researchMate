from uuid import UUID

from pydantic import BaseModel, Field

from researchmate_api.schemas.common import Citation, SourceSummary


# 定义 Sources panel 响应。
class RunSourcesResponse(BaseModel):
    run_id: UUID
    summary: SourceSummary
    citations: list[Citation] = Field(default_factory=list, max_length=120)

