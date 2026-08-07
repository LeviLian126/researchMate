"""Define evidence persistence contracts and a deterministic local repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    ClaimListResponse,
    ClaimRelationListResponse,
    EvaluationDatasetListResponse,
    EvaluationRunAccepted,
    EvaluationRunCreate,
    EvaluationRunRecord,
    FaultScenarioAccepted,
    FaultScenarioCreate,
    FaultScenarioRecord,
    HumanDecisionAccepted,
    HumanDecisionCreate,
    PipelineVersionListResponse,
    ReliabilityResponse,
    ReportDetail,
    ReportListResponse,
    ReportRefreshAccepted,
    ReportRefreshCreate,
    ResearchRunAccepted,
    ResearchRunCreate,
    RunEventRecord,
    WorkflowRunRecord,
)
from researchmate_api.services.evidence_faults import (
    EvidenceStoreError,
    FaultScenarioStoreMixin,
    evidence_fingerprint,
)


class EvidenceRepository(Protocol):
    """Define owner-scoped persistence operations for evidence workflows."""

    def create_research_run(
        self, user: CurrentUser, payload: ResearchRunCreate, idempotency_key: str
    ) -> ResearchRunAccepted: ...

    def get_run(self, user: CurrentUser, run_id: UUID) -> WorkflowRunRecord | None: ...

    def list_run_events(
        self, user: CurrentUser, run_id: UUID, after_sequence: int
    ) -> list[RunEventRecord] | None: ...

    def create_decision(
        self,
        user: CurrentUser,
        run_id: UUID,
        payload: HumanDecisionCreate,
        idempotency_key: str,
    ) -> HumanDecisionAccepted | None: ...

    def list_claims(self, user: CurrentUser, project_id: UUID) -> ClaimListResponse: ...

    def list_claim_relations(
        self, user: CurrentUser, project_id: UUID
    ) -> ClaimRelationListResponse: ...

    def list_reports(self, user: CurrentUser, project_id: UUID) -> ReportListResponse: ...

    def get_report(self, user: CurrentUser, report_id: UUID) -> ReportDetail | None: ...

    def list_pipeline_versions(self, user: CurrentUser) -> PipelineVersionListResponse: ...

    def list_evaluation_datasets(
        self, user: CurrentUser, project_id: UUID | None
    ) -> EvaluationDatasetListResponse: ...

    def refresh_report(
        self,
        user: CurrentUser,
        report_id: UUID,
        payload: ReportRefreshCreate,
        idempotency_key: str,
    ) -> ReportRefreshAccepted | None: ...

    def create_evaluation_run(
        self, user: CurrentUser, payload: EvaluationRunCreate, idempotency_key: str
    ) -> EvaluationRunAccepted: ...

    def get_evaluation_run(
        self, user: CurrentUser, evaluation_run_id: UUID
    ) -> EvaluationRunRecord | None: ...

    def reliability(self, user: CurrentUser, window_hours: int) -> ReliabilityResponse: ...

    def create_fault_scenario(
        self, user: CurrentUser, payload: FaultScenarioCreate, idempotency_key: str
    ) -> FaultScenarioAccepted: ...

    def get_fault_scenario(
        self, user: CurrentUser, exercise_id: UUID
    ) -> FaultScenarioRecord | None: ...


class InMemoryEvidenceRepository(FaultScenarioStoreMixin):
    """Deterministic local repository; distributed execution remains an explicit adapter boundary."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.runs: dict[UUID, tuple[UUID, WorkflowRunRecord]] = {}
        self.events: dict[UUID, list[RunEventRecord]] = {}
        self.decisions: dict[tuple[UUID, str], tuple[str, HumanDecisionAccepted]] = {}
        self.idempotency: dict[tuple[UUID, str], tuple[str, object]] = {}
        self.evaluations: dict[UUID, tuple[UUID, EvaluationRunRecord]] = {}
        self.faults: dict[UUID, tuple[UUID, FaultScenarioRecord]] = {}

    def create_research_run(
        self, user: CurrentUser, payload: ResearchRunCreate, idempotency_key: str
    ) -> ResearchRunAccepted:
        """Create or replay an idempotent caller-owned research run."""
        fingerprint = evidence_fingerprint(payload)
        key = (user.id, idempotency_key)
        with self.lock:
            existing = self.idempotency.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return existing[1]  # type: ignore[return-value]
            run_id, created_at = uuid4(), datetime.now(UTC)
            accepted = ResearchRunAccepted(
                run_id=run_id,
                status_url=f"/api/v1/runs/{run_id}",
                events_url=f"/api/v1/runs/{run_id}/events",
                created_at=created_at,
            )
            self.runs[run_id] = (
                user.id,
                WorkflowRunRecord(
                    run_id=run_id,
                    project_id=payload.project_id,
                    pipeline_version_id=payload.pipeline_version_id,
                    kind="evidence_review",
                    status="pending",
                    progress=0,
                    current_node=None,
                    review_required=False,
                    created_at=created_at,
                ),
            )
            self.events[run_id] = [
                RunEventRecord(
                    event_id=1,
                    sequence=0,
                    node_key="workflow",
                    event_type="run_status_changed",
                    attempt=0,
                    status="pending",
                    safe_payload={"status": "pending"},
                    created_at=created_at,
                )
            ]
            self.idempotency[key] = (fingerprint, accepted)
            return accepted

    def get_run(self, user: CurrentUser, run_id: UUID) -> WorkflowRunRecord | None:
        """Return a defensive copy of a caller-owned workflow run."""
        with self.lock:
            value = self.runs.get(run_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None

    def list_run_events(
        self, user: CurrentUser, run_id: UUID, after_sequence: int
    ) -> list[RunEventRecord] | None:
        """List resumable events after a sequence for a caller-owned run."""
        if self.get_run(user, run_id) is None:
            return None
        with self.lock:
            return [
                event.model_copy(deep=True)
                for event in self.events.get(run_id, [])
                if event.sequence > after_sequence
            ]

    def create_decision(
        self,
        user: CurrentUser,
        run_id: UUID,
        payload: HumanDecisionCreate,
        idempotency_key: str,
    ) -> HumanDecisionAccepted | None:
        """Persist one idempotent decision for a waiting caller-owned run."""
        with self.lock:
            owned = self.runs.get(run_id)
            if not owned or owned[0] != user.id:
                return None
            if owned[1].status != "waiting_human":
                raise EvidenceStoreError("RUN_NOT_WAITING")
            # The caller-supplied idempotency_key is the dedup contract; interrupt_key
            # identifies the review node but must not replace header-based deduplication.
            key = (run_id, idempotency_key)
            fingerprint = evidence_fingerprint(payload)
            existing = self.decisions.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise EvidenceStoreError("INTERRUPT_ALREADY_RESOLVED")
                return existing[1]
            accepted = HumanDecisionAccepted(
                decision_id=uuid4(),
                run_id=run_id,
                resume_status_url=f"/api/v1/runs/{run_id}",
            )
            self.decisions[key] = (fingerprint, accepted)
            owned[1].status = "pending"
            owned[1].review_required = False
            return accepted

    def list_claims(self, user: CurrentUser, project_id: UUID) -> ClaimListResponse:
        """Return the local repository's claim listing for a project."""
        return ClaimListResponse(items=[])

    def list_claim_relations(
        self, user: CurrentUser, project_id: UUID
    ) -> ClaimRelationListResponse:
        """Return the local repository's claim-relation listing."""
        return ClaimRelationListResponse(items=[])

    def list_reports(self, user: CurrentUser, project_id: UUID) -> ReportListResponse:
        """Return the local repository's report listing."""
        return ReportListResponse(items=[])

    def get_report(self, user: CurrentUser, report_id: UUID) -> ReportDetail | None:
        """Return no report because the local adapter does not persist reports."""
        return None

    def list_pipeline_versions(self, user: CurrentUser) -> PipelineVersionListResponse:
        """Return pipeline versions available in the local adapter."""
        return PipelineVersionListResponse(items=[])

    def list_evaluation_datasets(
        self, user: CurrentUser, project_id: UUID | None
    ) -> EvaluationDatasetListResponse:
        """Return evaluation datasets available in the local adapter."""
        return EvaluationDatasetListResponse(items=[])

    def refresh_report(
        self,
        user: CurrentUser,
        report_id: UUID,
        payload: ReportRefreshCreate,
        idempotency_key: str,
    ) -> ReportRefreshAccepted | None:
        """Return no refresh because local report persistence is unsupported."""
        return None

    def create_evaluation_run(
        self, user: CurrentUser, payload: EvaluationRunCreate, idempotency_key: str
    ) -> EvaluationRunAccepted:
        """Create or replay an idempotent caller-owned evaluation run."""
        fingerprint = evidence_fingerprint(payload)
        key = (user.id, idempotency_key)
        with self.lock:
            existing = self.idempotency.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return existing[1]  # type: ignore[return-value]
            run_id, created_at = uuid4(), datetime.now(UTC)
            accepted = EvaluationRunAccepted(
                evaluation_run_id=run_id,
                case_count=0,
                status_url=f"/api/v1/evaluation-runs/{run_id}",
                estimated_budget_boundary=payload.max_cost_usd,
            )
            self.evaluations[run_id] = (
                user.id,
                EvaluationRunRecord(
                    evaluation_run_id=run_id,
                    dataset_id=payload.dataset_id,
                    pipeline_version_id=payload.pipeline_version_id,
                    status="pending",
                    progress=0,
                    created_at=created_at,
                ),
            )
            self.idempotency[key] = (fingerprint, accepted)
            return accepted

    def get_evaluation_run(
        self, user: CurrentUser, evaluation_run_id: UUID
    ) -> EvaluationRunRecord | None:
        """Return a defensive copy of a caller-owned evaluation run."""
        with self.lock:
            value = self.evaluations.get(evaluation_run_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None

    def reliability(self, user: CurrentUser, window_hours: int) -> ReliabilityResponse:
        """Aggregate local workflow outcomes for the requested owner."""
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        with self.lock:
            records = [
                record
                for owner, record in self.runs.values()
                if owner == user.id and record.created_at >= cutoff
            ]
        terminal = [record for record in records if record.status in {"succeeded", "failed"}]
        succeeded = sum(record.status == "succeeded" for record in terminal)
        failed = sum(record.status == "failed" for record in terminal)
        denominator = max(1, len(terminal))
        return ReliabilityResponse(
            window_hours=window_hours,
            run_count=len(records),
            success_rate=succeeded / denominator,
            error_rate=failed / denominator,
            retry_count=0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal(0),
        )
