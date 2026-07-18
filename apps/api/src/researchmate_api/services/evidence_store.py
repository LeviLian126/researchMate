from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    ClaimListResponse,
    ClaimRelationListResponse,
    EvaluationRunAccepted,
    EvaluationRunCreate,
    EvaluationRunRecord,
    EvaluationDatasetListResponse,
    FaultScenarioAccepted,
    FaultScenarioCreate,
    FaultScenarioRecord,
    HumanDecisionAccepted,
    HumanDecisionCreate,
    ReliabilityResponse,
    ReportListResponse,
    ReportDetail,
    PipelineVersionListResponse,
    ReportRefreshAccepted,
    ReportRefreshCreate,
    ResearchRunAccepted,
    ResearchRunCreate,
    RunEventRecord,
    WorkflowRunRecord,
)


class EvidenceStoreError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class EvidenceRepository(Protocol):
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


def _fingerprint(payload: object) -> str:
    if hasattr(payload, "model_dump"):
        value = payload.model_dump(mode="json")
    else:
        value = payload
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class InMemoryEvidenceRepository:
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
        fingerprint = _fingerprint(payload)
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
        with self.lock:
            value = self.runs.get(run_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None

    def list_run_events(
        self, user: CurrentUser, run_id: UUID, after_sequence: int
    ) -> list[RunEventRecord] | None:
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
        with self.lock:
            owned = self.runs.get(run_id)
            if not owned or owned[0] != user.id:
                return None
            if owned[1].status != "waiting_human":
                raise EvidenceStoreError("RUN_NOT_WAITING")
            key = (run_id, payload.interrupt_key)
            fingerprint = _fingerprint(payload)
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
        return ClaimListResponse(items=[])

    def list_claim_relations(
        self, user: CurrentUser, project_id: UUID
    ) -> ClaimRelationListResponse:
        return ClaimRelationListResponse(items=[])

    def list_reports(self, user: CurrentUser, project_id: UUID) -> ReportListResponse:
        return ReportListResponse(items=[])

    def get_report(self, user: CurrentUser, report_id: UUID) -> ReportDetail | None:
        return None

    def list_pipeline_versions(self, user: CurrentUser) -> PipelineVersionListResponse:
        return PipelineVersionListResponse(items=[])

    def list_evaluation_datasets(
        self, user: CurrentUser, project_id: UUID | None
    ) -> EvaluationDatasetListResponse:
        return EvaluationDatasetListResponse(items=[])

    def refresh_report(
        self,
        user: CurrentUser,
        report_id: UUID,
        payload: ReportRefreshCreate,
        idempotency_key: str,
    ) -> ReportRefreshAccepted | None:
        return None

    def create_evaluation_run(
        self, user: CurrentUser, payload: EvaluationRunCreate, idempotency_key: str
    ) -> EvaluationRunAccepted:
        fingerprint = _fingerprint(payload)
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
        with self.lock:
            value = self.evaluations.get(evaluation_run_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None

    def reliability(self, user: CurrentUser, window_hours: int) -> ReliabilityResponse:
        with self.lock:
            records = [record for owner, record in self.runs.values() if owner == user.id]
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
            cost_usd=Decimal("0"),
        )

    def create_fault_scenario(
        self, user: CurrentUser, payload: FaultScenarioCreate, idempotency_key: str
    ) -> FaultScenarioAccepted:
        fingerprint = _fingerprint(payload)
        key = (user.id, idempotency_key)
        now = datetime.now(UTC)
        with self.lock:
            existing = self.idempotency.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return existing[1]  # type: ignore[return-value]
            exercise_id = uuid4()
            expires_at = now + timedelta(seconds=payload.duration_seconds)
            accepted = FaultScenarioAccepted(
                exercise_id=exercise_id,
                target_run_id=payload.target_run_id,
                expected_recovery_state="simulation_completed_without_external_mutation",
                status_url=f"/api/v1/dev/fault-scenarios/{exercise_id}",
                expires_at=expires_at,
            )
            self.faults[exercise_id] = (
                user.id,
                FaultScenarioRecord(
                    exercise_id=exercise_id,
                    scenario=payload.scenario,
                    target_run_id=payload.target_run_id,
                    status="pending",
                    attempts=0,
                    expires_at=expires_at,
                    created_at=now,
                ),
            )
            self.idempotency[key] = (fingerprint, accepted)
            return accepted

    def get_fault_scenario(
        self, user: CurrentUser, exercise_id: UUID
    ) -> FaultScenarioRecord | None:
        with self.lock:
            value = self.faults.get(exercise_id)
            return value[1].model_copy(deep=True) if value and value[0] == user.id else None
