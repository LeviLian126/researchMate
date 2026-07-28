from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchmate_api.schemas.common import Citation


class ConversationSummary(BaseModel):
    id: UUID
    project_id: UUID
    title: str = Field(min_length=1, max_length=120)
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary] = Field(default_factory=list, max_length=100)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Conversation title must contain visible text.")
        return title


class ConversationMessage(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)
    citations: list[Citation] = Field(default_factory=list, max_length=80)
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    conversation_id: UUID
    messages: list[ConversationMessage] = Field(default_factory=list, max_length=200)


class RuntimeRerankConfig(BaseModel):
    provider: Literal["auto", "qdrant", "nvidia", "deterministic"]
    version: int = Field(ge=1)
    updated_at: datetime
    updated_by: UUID | None = None


class RuntimeRerankConfigUpdate(BaseModel):
    provider: Literal["auto", "qdrant", "nvidia", "deterministic"]
    expected_version: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")
