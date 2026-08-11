"""Define conversation metadata, messages, and runtime rerank contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchmate_api.schemas.common import MAX_CONVERSATION_MESSAGE_LENGTH, Citation


class ConversationSummary(BaseModel):
    """Represent conversation metadata in owner-scoped listings."""

    id: UUID
    project_id: UUID
    title: str = Field(min_length=1, max_length=120)
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Wrap a bounded conversation listing."""

    items: list[ConversationSummary] = Field(default_factory=list, max_length=100)


class ConversationCreate(BaseModel):
    """Validate a request to create a named conversation."""

    title: str = Field(default="New chat", min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim the title and reject whitespace-only values."""
        title = value.strip()
        if not title:
            raise ValueError("Conversation title must contain visible text.")
        return title


class ConversationUpdate(BaseModel):
    """Validate a request to rename an existing conversation."""

    title: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim the replacement title and require visible text."""
        title = value.strip()
        if not title:
            raise ValueError("Conversation title must contain visible text.")
        return title


class ConversationMessage(BaseModel):
    """Represent a persisted user or assistant conversation message."""

    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CONVERSATION_MESSAGE_LENGTH)
    citations: list[Citation] = Field(default_factory=list, max_length=80)
    ask_run_id: UUID | None = None
    feedback_rating: Literal["helpful", "not_helpful"] | None = None
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    """Wrap bounded chronological messages for one conversation."""

    conversation_id: UUID
    messages: list[ConversationMessage] = Field(default_factory=list, max_length=200)


class RuntimeRerankConfig(BaseModel):
    """Expose the versioned rerank provider selected at runtime."""

    provider: Literal["auto", "qdrant", "nvidia", "deterministic"]
    version: int = Field(ge=1)
    updated_at: datetime
    updated_by: UUID | None = None


class RuntimeRerankConfigUpdate(BaseModel):
    """Validate an optimistic update to the runtime rerank provider."""

    provider: Literal["auto", "qdrant", "nvidia", "deterministic"]
    expected_version: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")
