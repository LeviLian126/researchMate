"""Expose the workflow runtime contract while focused mixins own distinct responsibilities."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from researchmate_api.services.evidence_generation import (
    ExtractedClaim,
    build_research_plan,
    extract_claims,
    reconcile_claims,
    synthesize_report,
)

from researchmate_worker.evidence_graph import EvidenceWorkflowState
from researchmate_worker.workflow_core import (
    SqlEvidenceWorkflowDomain as _SqlEvidenceWorkflowDomain,
)
from researchmate_worker.workflow_models import WorkflowPipelineConfig, WorkflowRuntimeError


class SqlEvidenceWorkflowDomain(_SqlEvidenceWorkflowDomain):
    """Keep the historical import and monkeypatch seam for workflow orchestration clients."""

    def synthesize(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Preserve the public synthesis seam used by orchestration tests and clients."""
        run_id = UUID(state.get("run_id", ""))
        self._node_started(run_id, "synthesize", 70)
        claims = [ExtractedClaim.model_validate(claim) for claim in state.get("claims", [])]
        required_keys = (
            state.get("impacted_section_keys")
            if state.get("run_kind") == "report_refresh"
            else None
        )
        report = synthesize_report(
            self.provider,
            state.get("research_goal", ""),
            claims,
            required_section_keys=required_keys,
        )
        self._node_completed(run_id, "synthesize", 85, {"sections": len(report.sections)})
        return {"report": report.model_dump(mode="json")}


__all__ = [
    "SqlEvidenceWorkflowDomain",
    "WorkflowPipelineConfig",
    "WorkflowRuntimeError",
    "build_research_plan",
    "extract_claims",
    "reconcile_claims",
    "synthesize_report",
]
