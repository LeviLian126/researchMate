"""Define redacted developer-trace contracts for privileged diagnostics."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from researchmate_api.schemas.common import ExecutionPlan


# Define the redacted tool-call summary.
class ToolCallTrace(BaseModel):
    """Summarize a tool call without exposing raw sensitive payloads."""

    id: UUID
    tool_name: str = Field(min_length=2, max_length=120)
    input_summary: dict
    output_summary: dict | None = None
    status: str
    latency_ms: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, max_length=500)


# Define the admin-visible Developer Trace.
class DeveloperTrace(BaseModel):
    """Aggregate privacy-bounded execution diagnostics for administrators."""

    trace_id: UUID
    user_id: UUID
    project_id: UUID
    run_id: UUID
    execution_plan: ExecutionPlan
    router_reason: str = Field(max_length=2000)
    retrieved_chunks: list[dict] = Field(default_factory=list, max_length=80)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list, max_length=40)
    validation_result: dict
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict | None = None
    errors: list[str] = Field(default_factory=list, max_length=20)
    created_at: datetime
