"""Define the source-panel response contract for a completed run."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from researchmate_api.schemas.common import Citation, SourceSummary


# Define the Sources panel response.
class RunSourcesResponse(BaseModel):
    """Return source counts and validated citations for one run."""

    run_id: UUID
    summary: SourceSummary
    citations: list[Citation] = Field(default_factory=list, max_length=120)
