from __future__ import annotations

import asyncio
import json
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from researchmate_api.dependencies import (
    get_current_user,
    get_evidence_store,
    get_store,
    raise_api_error,
    require_admin,
)
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
    WorkflowRunRecord,
)
from researchmate_api.services.evidence_store import EvidenceRepository, EvidenceStoreError
from researchmate_api.services.store import ResearchMateRepository


router = APIRouter()
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")


def _idempotency(value: str | None) -> str:
    if value is None or not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "IDEMPOTENCY_KEY_REQUIRED",
            "A stable 8-160 character Idempotency-Key is required.",
        )
    return value


def _store_call(callback):
    try:
        return callback()
    except EvidenceStoreError as exc:
        raise_api_error(exc.status_code, exc.code, exc.code.replace("_", " ").title())


def _require_project(
    repository: ResearchMateRepository, user: CurrentUser, project_id: UUID
) -> None:
    if repository.get_project(user, project_id) is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")


@router.post("/research-runs", response_model=ResearchRunAccepted, status_code=202)
def create_research_run(
    payload: ResearchRunCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ResearchRunAccepted:
    _require_project(repository, user, payload.project_id)
    return _store_call(
        lambda: evidence.create_research_run(user, payload, _idempotency(idempotency_key))
    )


@router.get("/runs/{run_id}", response_model=WorkflowRunRecord)
def get_workflow_run(
    run_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> WorkflowRunRecord:
    run = evidence.get_run(user, run_id)
    if run is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "RUN_NOT_FOUND", "Run was not found.")
    return run


@router.get("/runs/{run_id}/events")
def stream_run_events(
    run_id: UUID,
    request: Request,
    after_sequence: int = Query(default=-1, ge=-1),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> StreamingResponse:
    if last_event_id is not None:
        try:
            after_sequence = max(after_sequence, int(last_event_id))
        except ValueError:
            raise_api_error(422, "INVALID_EVENT_CURSOR", "Last-Event-ID must be an integer.")
    if evidence.get_run(user, run_id) is None:
        raise_api_error(404, "RUN_NOT_FOUND", "Run was not found.")

    async def generate():
        cursor = after_sequence
        idle_cycles = 0
        while not await request.is_disconnected() and idle_cycles < 15:
            events = evidence.list_run_events(user, run_id, cursor) or []
            if events:
                idle_cycles = 0
                for event in events:
                    cursor = event.sequence
                    data = event.model_dump(mode="json")
                    yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {json.dumps(data)}\n\n"
                    if event.status in {"succeeded", "failed"} and event.node_key == "workflow":
                        return
            else:
                idle_cycles += 1
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/decisions", response_model=HumanDecisionAccepted, status_code=202)
def create_human_decision(
    run_id: UUID,
    payload: HumanDecisionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> HumanDecisionAccepted:
    decision = _store_call(
        lambda: evidence.create_decision(
            user, run_id, payload, _idempotency(idempotency_key)
        )
    )
    if decision is None:
        raise_api_error(404, "RUN_NOT_FOUND", "Run was not found.")
    return decision


@router.get("/projects/{project_id}/claims", response_model=ClaimListResponse)
def list_claims(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ClaimListResponse:
    _require_project(repository, user, project_id)
    return evidence.list_claims(user, project_id)


@router.get(
    "/projects/{project_id}/claim-relations", response_model=ClaimRelationListResponse
)
def list_claim_relations(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ClaimRelationListResponse:
    _require_project(repository, user, project_id)
    return evidence.list_claim_relations(user, project_id)


@router.get("/projects/{project_id}/reports", response_model=ReportListResponse)
def list_reports(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ReportListResponse:
    _require_project(repository, user, project_id)
    return evidence.list_reports(user, project_id)


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ReportDetail:
    report = evidence.get_report(user, report_id)
    if report is None:
        raise_api_error(404, "REPORT_NOT_FOUND", "Report was not found.")
    return report


@router.get("/pipeline-versions", response_model=PipelineVersionListResponse)
def list_pipeline_versions(
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> PipelineVersionListResponse:
    return evidence.list_pipeline_versions(user)


@router.get("/evaluation-datasets", response_model=EvaluationDatasetListResponse)
def list_evaluation_datasets(
    project_id: UUID | None = Query(default=None),
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> EvaluationDatasetListResponse:
    return evidence.list_evaluation_datasets(user, project_id)


@router.post("/reports/{report_id}/refresh", response_model=ReportRefreshAccepted, status_code=202)
def refresh_report(
    report_id: UUID,
    payload: ReportRefreshCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ReportRefreshAccepted:
    response = _store_call(
        lambda: evidence.refresh_report(
            user, report_id, payload, _idempotency(idempotency_key)
        )
    )
    if response is None:
        raise_api_error(404, "REPORT_NOT_FOUND", "Report was not found.")
    return response


@router.post("/evaluation-runs", response_model=EvaluationRunAccepted, status_code=202)
def create_evaluation_run(
    payload: EvaluationRunCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> EvaluationRunAccepted:
    return _store_call(
        lambda: evidence.create_evaluation_run(user, payload, _idempotency(idempotency_key))
    )


@router.get("/evaluation-runs/{evaluation_run_id}", response_model=EvaluationRunRecord)
def get_evaluation_run(
    evaluation_run_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> EvaluationRunRecord:
    run = evidence.get_evaluation_run(user, evaluation_run_id)
    if run is None:
        raise_api_error(404, "EVALUATION_RUN_NOT_FOUND", "Evaluation run was not found.")
    return run


@router.get("/dev/reliability", response_model=ReliabilityResponse)
def reliability(
    window_hours: int = Query(default=24, ge=1, le=168),
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> ReliabilityResponse:
    return evidence.reliability(user, window_hours)


@router.post("/dev/fault-scenarios", response_model=FaultScenarioAccepted, status_code=202)
def create_fault_scenario(
    payload: FaultScenarioCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> FaultScenarioAccepted:
    if request.app.state.settings.app_env not in {"local", "test", "preview"}:
        raise_api_error(404, "NOT_FOUND", "Resource was not found.")
    return _store_call(
        lambda: evidence.create_fault_scenario(user, payload, _idempotency(idempotency_key))
    )


@router.get("/dev/fault-scenarios/{exercise_id}", response_model=FaultScenarioRecord)
def get_fault_scenario(
    exercise_id: UUID,
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> FaultScenarioRecord:
    record = _store_call(lambda: evidence.get_fault_scenario(user, exercise_id))
    if record is None:
        raise_api_error(404, "FAULT_EXERCISE_NOT_FOUND", "Fault exercise was not found.")
    return record
