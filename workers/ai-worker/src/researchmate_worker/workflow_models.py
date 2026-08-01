"""Define stable workflow runtime configuration and normalized failure semantics."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class WorkflowRuntimeError(RuntimeError):
    """Expose a stable worker failure code without leaking provider details."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class WorkflowPipelineConfig(BaseModel):
    """Validate the versioned runtime choices used by this worker path."""

    retrieval_limit: int = Field(default=12, ge=1, le=50)
    model: str = Field(min_length=1, max_length=200)
    evidence_prompt_version: str = Field(pattern=r"^evidence-review-v[0-9]+$")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
