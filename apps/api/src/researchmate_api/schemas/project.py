"""Define validated project creation and project response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Define the create-project request.
class ProjectCreate(BaseModel):
    """Validate the caller-provided name for a new project."""

    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim a project name and reject whitespace-only input."""
        name = value.strip()
        if not name:
            raise ValueError("Project name must contain visible text.")
        return name


# Define the project record response.
class ProjectRecord(BaseModel):
    """Represent owner-scoped project metadata returned by the API."""

    id: UUID
    user_id: UUID
    name: str
    kind: Literal["personal", "workspace"] = "workspace"
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
