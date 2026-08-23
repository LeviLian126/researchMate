"""Define redacted developer-trace contracts for privileged diagnostics."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from researchmate_api.schemas.common import (
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_ERRORS_SUMMARY,
    MAX_RETRIEVED_CHUNKS_SUMMARY,
    MAX_ROUTER_REASON_LENGTH,
    MAX_TOOL_CALLS_SUMMARY,
    MAX_TOOL_NAME_LENGTH,
    MIN_LATENCY_MS,
    ExecutionPlan,
)


# Define the redacted tool-call summary.
class ToolCallTrace(BaseModel):
    """Summarize a tool call without exposing raw sensitive payloads."""

    id: UUID
    tool_name: str = Field(min_length=2, max_length=MAX_TOOL_NAME_LENGTH)
    input_summary: dict
    output_summary: dict | None = None
    status: str
    latency_ms: int | None = Field(default=None, ge=MIN_LATENCY_MS)
    error_message: str | None = Field(default=None, max_length=MAX_ERROR_MESSAGE_LENGTH)


# Define the admin-visible Developer Trace.
class DeveloperTrace(BaseModel):
    """Aggregate privacy-bounded execution diagnostics for administrators."""

    trace_id: UUID
    user_id: UUID
    project_id: UUID
    run_id: UUID
    execution_plan: ExecutionPlan
    router_reason: str = Field(max_length=MAX_ROUTER_REASON_LENGTH)
    retrieved_chunks: list[dict] = Field(
        default_factory=list, max_length=MAX_RETRIEVED_CHUNKS_SUMMARY
    )
    tool_calls: list[ToolCallTrace] = Field(default_factory=list, max_length=MAX_TOOL_CALLS_SUMMARY)
    validation_result: dict
    latency_ms: int | None = Field(default=None, ge=MIN_LATENCY_MS)
    token_usage: dict | None = None
    errors: list[str] = Field(default_factory=list, max_length=MAX_ERRORS_SUMMARY)
    created_at: datetime
