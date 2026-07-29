from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 定义创建项目请求。
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Project name must contain visible text.")
        return name


# 定义项目记录响应。
class ProjectRecord(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    kind: Literal["personal", "workspace"] = "workspace"
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
