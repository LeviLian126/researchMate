from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


RunStatus = Literal["pending", "running", "waiting_human", "succeeded", "failed", "cancelled"]


class SourceScope(BaseModel):
    document_ids: list[UUID] = Field(default_factory=list, max_length=200)
    allow_web: bool = False

    @model_validator(mode="after")
    def reject_duplicate_documents(self) -> "SourceScope":
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        return self


class ResearchRunCreate(BaseModel):
    project_id: UUID
    research_goal: str = Field(min_length=20, max_length=12_000)
    source_scope: SourceScope = Field(default_factory=SourceScope)
    pipeline_version_id: UUID
    review_policy: Literal["strict", "balanced"] = "strict"
    max_cost_usd: Decimal | None = Field(default=None, gt=0, le=25)


class ResearchRunAccepted(BaseModel):
    run_id: UUID
    status: Literal["pending"] = "pending"
    status_url: str
    events_url: str
    created_at: datetime


class WorkflowRunRecord(BaseModel):
    run_id: UUID
    project_id: UUID
    pipeline_version_id: UUID
    kind: Literal["ask", "evidence_review", "report_refresh"]
    status: RunStatus
    progress: int = Field(ge=0, le=100)
    current_node: str | None = None
    review_required: bool = False
    output: dict[str, Any] | None = None
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunEventRecord(BaseModel):
    event_id: int
    sequence: int = Field(ge=0)
    node_key: str
    event_type: str
    attempt: int = Field(ge=0)
    status: str
    safe_payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = Field(default=None, ge=0)
    created_at: datetime


class HumanDecisionCreate(BaseModel):
    interrupt_key: str = Field(min_length=1, max_length=160)
    decision: Literal["approve", "edit", "reject"]
    edited_payload: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_edited_payload(self) -> "HumanDecisionCreate":
        if self.decision == "edit" and self.edited_payload is None:
            raise ValueError("edited_payload is required for an edit decision")
        if self.decision != "edit" and self.edited_payload is not None:
            raise ValueError("edited_payload is only valid for an edit decision")
        return self


class HumanDecisionAccepted(BaseModel):
    decision_id: UUID
    run_id: UUID
    status: Literal["accepted"] = "accepted"
    resume_status_url: str


class ClaimSummary(BaseModel):
    claim_id: UUID
    text: str
    stance: Literal["supports", "opposes", "neutral"]
    confidence: float = Field(ge=0, le=1)
    review_status: Literal["pending", "accepted", "edited", "rejected", "invalidated"]
    evidence_count: int = Field(ge=0)
    support_count: int = Field(ge=0)
    contradiction_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    source_version: int = Field(ge=1)


class ClaimListResponse(BaseModel):
    items: list[ClaimSummary]
    next_cursor: str | None = None


class ClaimRelationSummary(BaseModel):
    source_claim_id: UUID
    target_claim_id: UUID
    relation: Literal["supports", "contradicts", "duplicates"]
    confidence: float = Field(ge=0, le=1)
    rationale_summary: str | None = None
    source_text: str
    target_text: str


class ClaimRelationListResponse(BaseModel):
    items: list[ClaimRelationSummary]
    next_cursor: str | None = None


class ReportSummary(BaseModel):
    report_id: UUID
    source_run_id: UUID
    title: str
    status: Literal["draft", "review", "published", "invalidated"]
    revision: int = Field(ge=1)
    validation_status: Literal["pending", "passed", "failed", "retrying"]
    affected_section_count: int = Field(ge=0)
    generated_at: datetime | None = None


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    next_cursor: str | None = None


class ReportSectionRecord(BaseModel):
    section_id: UUID
    section_key: str
    position: int = Field(ge=0)
    heading: str
    body_markdown: str
    evidence_snapshot: dict[str, Any]
    validation_status: Literal["pending", "passed", "failed", "retrying"]


class ReportDetail(ReportSummary):
    sections: list[ReportSectionRecord]


class PipelineVersionSummary(BaseModel):
    pipeline_version_id: UUID
    name: str
    version: int = Field(ge=1)
    configuration: dict[str, Any]
    code_sha: str
    accepted_at: datetime | None = None


class PipelineVersionListResponse(BaseModel):
    items: list[PipelineVersionSummary]


class EvaluationDatasetSummary(BaseModel):
    dataset_id: UUID
    project_id: UUID | None = None
    name: str
    version: int = Field(ge=1)
    description: str | None = None
    case_count: int = Field(ge=0)


class EvaluationDatasetListResponse(BaseModel):
    items: list[EvaluationDatasetSummary]


class ReportRefreshCreate(BaseModel):
    changed_document_ids: list[UUID] = Field(default_factory=list, max_length=200)
    force_sections: list[str] = Field(default_factory=list, max_length=100)
    pipeline_version_id: UUID

    @model_validator(mode="after")
    def require_change(self) -> "ReportRefreshCreate":
        if not self.changed_document_ids and not self.force_sections:
            raise ValueError("at least one changed document or forced section is required")
        return self


class ReportRefreshAccepted(BaseModel):
    run_id: UUID
    base_revision: int
    planned_revision: int
    impacted_section_keys: list[str]
    events_url: str


class EvaluationRunCreate(BaseModel):
    dataset_id: UUID
    pipeline_version_id: UUID
    metrics: list[
        Literal["schema_valid", "citation_precision", "evidence_recall", "faithfulness"]
    ] = Field(min_length=1, max_length=4)
    max_parallelism: int = Field(default=4, ge=1, le=20)
    max_cost_usd: Decimal | None = Field(default=None, gt=0, le=25)
    labels: list[str] = Field(default_factory=list, max_length=20)


class EvaluationRunAccepted(BaseModel):
    evaluation_run_id: UUID
    case_count: int = Field(ge=0)
    status_url: str
    estimated_budget_boundary: Decimal | None = None


class EvaluationRunRecord(BaseModel):
    evaluation_run_id: UUID
    dataset_id: UUID
    pipeline_version_id: UUID
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    progress: int = Field(ge=0, le=100)
    summary: dict[str, Any] | None = None
    scores: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ReliabilityResponse(BaseModel):
    window_hours: int
    run_count: int
    success_rate: float = Field(ge=0, le=1)
    error_rate: float = Field(ge=0, le=1)
    retry_count: int = Field(ge=0)
    p50_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: Decimal = Decimal("0")
    sample_trace_ids: list[UUID] = Field(default_factory=list)


class FaultScenarioCreate(BaseModel):
    scenario: Literal["llm_timeout", "qdrant_unavailable", "worker_interrupt", "r2_failure"]
    target_run_id: UUID | None = None
    duration_seconds: int = Field(ge=1, le=60)


class FaultScenarioAccepted(BaseModel):
    exercise_id: UUID
    target_run_id: UUID | None = None
    expected_recovery_state: str
    status_url: str
    expires_at: datetime


class FaultScenarioRecord(BaseModel):
    exercise_id: UUID
    scenario: Literal["llm_timeout", "qdrant_unavailable", "worker_interrupt", "r2_failure"]
    target_run_id: UUID | None = None
    status: Literal["pending", "running", "succeeded", "failed"]
    attempts: int = Field(ge=0)
    expires_at: datetime
    safe_result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
