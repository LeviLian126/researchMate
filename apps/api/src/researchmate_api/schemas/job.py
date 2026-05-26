from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from researchmate_api.schemas.common import JobStatus


# 定义异步任务响应。
class JobRecord(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    document_id: UUID | None = None
    type: str = Field(min_length=2, max_length=80)
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(use_enum_values=True)

