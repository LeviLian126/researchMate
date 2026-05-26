from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# 定义创建项目请求。
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


# 定义项目记录响应。
class ProjectRecord(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

