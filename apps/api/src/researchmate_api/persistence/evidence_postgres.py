from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from researchmate_api.persistence.postgres import _psycopg_url
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    ClaimListResponse,
    ClaimRelationListResponse,
    ClaimRelationSummary,
    ClaimSummary,
    EvaluationRunAccepted,
    EvaluationRunCreate,
    EvaluationRunRecord,
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
    FaultScenarioAccepted,
    FaultScenarioCreate,
    FaultScenarioRecord,
    HumanDecisionAccepted,
    HumanDecisionCreate,
    ReliabilityResponse,
    ReportListResponse,
    ReportDetail,
    ReportSectionRecord,
    ReportRefreshAccepted,
    ReportRefreshCreate,
    ReportSummary,
    PipelineVersionListResponse,
    PipelineVersionSummary,
    ResearchRunAccepted,
    ResearchRunCreate,
    RunEventRecord,
    WorkflowRunRecord,
)
from researchmate_api.services.evidence_store import EvidenceStoreError, _fingerprint


DEFAULT_EVALUATION_BUDGET_USD = Decimal("1.000000")


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def _progress(status: str, safe_payload: dict | None) -> int:
    if safe_payload and isinstance(safe_payload.get("progress"), int):
        return max(0, min(100, safe_payload["progress"]))
    return {
        "pending": 0,
        "running": 25,
        "waiting_human": 65,
        "succeeded": 100,
        "failed": 100,
        "cancelled": 100,
    }.get(status, 0)


class PostgresEvidenceRepository:
    """Durable evidence-review repository; all reads enforce explicit owner predicates."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @classmethod
    def from_database_url(cls, database_url: str) -> PostgresEvidenceRepository:
        return cls(
            create_engine(
                _psycopg_url(database_url),
                pool_pre_ping=True,
                pool_recycle=300,
                future=True,
            )
        )

    @contextmanager
    def _transaction(self, user: CurrentUser | None = None) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            if user is not None:
                connection.execute(
                    text("select set_config('request.jwt.claim.sub', :user_id, true)"),
                    {"user_id": str(user.id)},
                )
            yield connection

    def create_research_run(
        self, user: CurrentUser, payload: ResearchRunCreate, idempotency_key: str
    ) -> ResearchRunAccepted:
        request_hash = _fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = connection.execute(
                text(
                    """
                    select id, input, created_at from workflow_runs
                    where user_id = :user_id and idempotency_key = :idempotency_key
                    for update
                    """
                ),
                {"user_id": user.id, "idempotency_key": idempotency_key},
            ).mappings().one_or_none()
            if existing is not None:
                if existing["input"].get("request_hash") != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return self._accepted_run(existing["id"], existing["created_at"])
            allowed = connection.execute(
                text(
                    """
                    select 1 from projects p join pipeline_versions v on v.id = :pipeline_id
                    where p.id = :project_id and p.user_id = :user_id
                      and p.deleted_at is null and v.status = 'accepted'
                    """
                ),
                {
                    "project_id": payload.project_id,
                    "user_id": user.id,
                    "pipeline_id": payload.pipeline_version_id,
                },
            ).one_or_none()
            if allowed is None:
                raise EvidenceStoreError("PIPELINE_NOT_ACCEPTED")
            selected_document_ids = list(payload.source_scope.document_ids)
            if selected_document_ids:
                ready_count = connection.execute(
                    text(
                        """
                        select count(*) from documents
                        where id=any(:document_ids) and user_id=:user_id
                          and project_id=:project_id and status='ready' and deleted_at is null
                        """
                    ),
                    {
                        "document_ids": selected_document_ids,
                        "user_id": user.id,
                        "project_id": payload.project_id,
                    },
                ).scalar_one()
                if ready_count != len(selected_document_ids):
                    raise EvidenceStoreError("SOURCE_DOCUMENT_NOT_READY")
            elif not payload.source_scope.allow_web:
                has_ready_document = connection.execute(
                    text(
                        """
                        select 1 from documents
                        where user_id=:user_id and project_id=:project_id
                          and status='ready' and deleted_at is null limit 1
                        """
                    ),
                    {"user_id": user.id, "project_id": payload.project_id},
                ).one_or_none()
                if has_ready_document is None:
                    raise EvidenceStoreError("SOURCE_SCOPE_EMPTY")
            run_id, created_at = uuid4(), datetime.now(UTC)
            run_input = {**payload.model_dump(mode="json"), "request_hash": request_hash}
            connection.execute(
                text(
                    """
                    insert into workflow_runs (
                      id, user_id, project_id, pipeline_version_id, kind, status,
                      idempotency_key, checkpoint_ref, input, budget_limit_usd, created_at
                    ) values (
                      :id, :user_id, :project_id, :pipeline_id, 'evidence_review', 'pending',
                      :idempotency_key, :checkpoint_ref, cast(:input as jsonb), :budget_limit, :created_at
                    )
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": payload.project_id,
                    "pipeline_id": payload.pipeline_version_id,
                    "idempotency_key": idempotency_key,
                    "checkpoint_ref": str(run_id),
                    "input": _json(run_input),
                    "budget_limit": payload.max_cost_usd or Decimal("1.000000"),
                    "created_at": created_at,
                },
            )
            self._append_event(
                connection,
                run_id,
                node_key="workflow",
                event_type="run_status_changed",
                status="pending",
                safe_payload={"status": "pending", "progress": 0},
            )
            self._append_outbox(
                connection,
                aggregate_type="workflow_run",
                aggregate_id=run_id,
                event_type="workflow.run.requested",
                payload={"run_id": str(run_id), "user_id": str(user.id)},
                idempotency_key=f"workflow:{run_id}:start:v1",
            )
            return self._accepted_run(run_id, created_at)

    @staticmethod
    def _accepted_run(run_id: UUID, created_at: datetime) -> ResearchRunAccepted:
        return ResearchRunAccepted(
            run_id=run_id,
            status_url=f"/api/v1/runs/{run_id}",
            events_url=f"/api/v1/runs/{run_id}/events",
            created_at=created_at,
        )

    def get_run(self, user: CurrentUser, run_id: UUID) -> WorkflowRunRecord | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select r.id, r.project_id, r.pipeline_version_id, r.kind, r.status,
                      r.output, r.error_code, r.created_at, r.started_at, r.completed_at,
                      e.node_key as current_node, e.safe_payload
                    from workflow_runs r
                    left join lateral (
                      select node_key, safe_payload from run_events
                      where run_id = r.id order by sequence desc limit 1
                    ) e on true
                    where r.id = :run_id and r.user_id = :user_id
                    """
                ),
                {"run_id": run_id, "user_id": user.id},
            ).mappings().one_or_none()
        if row is None:
            return None
        return WorkflowRunRecord(
            run_id=row["id"],
            project_id=row["project_id"],
            pipeline_version_id=row["pipeline_version_id"],
            kind=row["kind"],
            status=row["status"],
            progress=_progress(row["status"], row["safe_payload"]),
            current_node=row["current_node"],
            review_required=row["status"] == "waiting_human",
            output=row["output"],
            error_code=row["error_code"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def list_run_events(
        self, user: CurrentUser, run_id: UUID, after_sequence: int
    ) -> list[RunEventRecord] | None:
        with self._transaction(user) as connection:
            owned = connection.execute(
                text("select 1 from workflow_runs where id = :id and user_id = :user_id"),
                {"id": run_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = connection.execute(
                text(
                    """
                    select id as event_id, sequence, node_key, event_type, attempt, status,
                      safe_payload, latency_ms, created_at
                    from run_events where run_id = :run_id and sequence > :after_sequence
                    order by sequence limit 500
                    """
                ),
                {"run_id": run_id, "after_sequence": after_sequence},
            ).mappings().all()
        return [RunEventRecord.model_validate(dict(row)) for row in rows]

    def create_decision(
        self,
        user: CurrentUser,
        run_id: UUID,
        payload: HumanDecisionCreate,
        idempotency_key: str,
    ) -> HumanDecisionAccepted | None:
        with self._transaction(user) as connection:
            run = connection.execute(
                text(
                    """
                    select id, status from workflow_runs
                    where id = :id and user_id = :user_id for update
                    """
                ),
                {"id": run_id, "user_id": user.id},
            ).mappings().one_or_none()
            if run is None:
                return None
            existing = connection.execute(
                text(
                    """
                    select id, decision, final_payload from human_decisions
                    where run_id = :run_id and interrupt_key = :interrupt_key
                    """
                ),
                {"run_id": run_id, "interrupt_key": payload.interrupt_key},
            ).mappings().one_or_none()
            final_payload = payload.edited_payload if payload.decision == "edit" else None
            if existing is not None:
                if existing["decision"] != payload.decision or existing["final_payload"] != final_payload:
                    raise EvidenceStoreError("INTERRUPT_ALREADY_RESOLVED")
                return self._accepted_decision(existing["id"], run_id)
            if run["status"] != "waiting_human":
                raise EvidenceStoreError("RUN_NOT_WAITING")
            proposed = connection.execute(
                text(
                    """
                    select id, safe_payload from run_events
                    where run_id = :run_id and event_type = 'human_requested'
                      and safe_payload ->> 'interrupt_key' = :interrupt_key
                    order by sequence desc limit 1
                    """
                ),
                {"run_id": run_id, "interrupt_key": payload.interrupt_key},
            ).mappings().one_or_none()
            if proposed is None:
                raise EvidenceStoreError("INTERRUPT_NOT_FOUND")
            decision_id = uuid4()
            connection.execute(
                text(
                    """
                    insert into human_decisions (
                      id, run_id, event_id, user_id, interrupt_key, decision,
                      proposed_payload, final_payload, reason
                    ) values (
                      :id, :run_id, :event_id, :user_id, :interrupt_key, :decision,
                      cast(:proposed as jsonb), cast(:final as jsonb), :reason
                    )
                    """
                ),
                {
                    "id": decision_id,
                    "run_id": run_id,
                    "event_id": proposed["id"],
                    "user_id": user.id,
                    "interrupt_key": payload.interrupt_key,
                    "decision": payload.decision,
                    "proposed": _json(proposed["safe_payload"]),
                    "final": _json(final_payload) if final_payload is not None else None,
                    "reason": payload.reason,
                },
            )
            connection.execute(
                text("update workflow_runs set status = 'pending' where id = :id"),
                {"id": run_id},
            )
            self._append_event(
                connection,
                run_id,
                node_key="human_review",
                event_type="human_resolved",
                status="succeeded",
                safe_payload={
                    "interrupt_key": payload.interrupt_key,
                    "decision": payload.decision,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="workflow_run",
                aggregate_id=run_id,
                event_type="workflow.resume.requested",
                payload={
                    "run_id": str(run_id),
                    "user_id": str(user.id),
                    "decision_id": str(decision_id),
                },
                idempotency_key=f"workflow:{run_id}:decision:{payload.interrupt_key}",
            )
            return self._accepted_decision(decision_id, run_id)

    @staticmethod
    def _accepted_decision(decision_id: UUID, run_id: UUID) -> HumanDecisionAccepted:
        return HumanDecisionAccepted(
            decision_id=decision_id,
            run_id=run_id,
            resume_status_url=f"/api/v1/runs/{run_id}",
        )

    def list_claims(self, user: CurrentUser, project_id: UUID) -> ClaimListResponse:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select c.id, c.text, c.stance, c.confidence, c.review_status,
                      c.source_version,
                      count(distinct ce.citation_id) as evidence_count,
                      count(distinct crs.target_claim_id) filter (where crs.relation = 'supports')
                        as support_count,
                      count(distinct crc.target_claim_id) filter (where crc.relation = 'contradicts')
                        as contradiction_count,
                      count(distinct crd.target_claim_id) filter (where crd.relation = 'duplicates')
                        as duplicate_count
                    from claims c
                    left join claim_evidence ce on ce.claim_id = c.id
                    left join claim_relations crs on crs.source_claim_id = c.id
                    left join claim_relations crc on crc.source_claim_id = c.id
                    left join claim_relations crd on crd.source_claim_id = c.id
                    where c.project_id = :project_id and c.user_id = :user_id
                    group by c.id order by c.created_at desc limit 200
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().all()
        return ClaimListResponse(
            items=[
                ClaimSummary(
                    claim_id=row["id"],
                    text=row["text"],
                    stance=row["stance"],
                    confidence=float(row["confidence"]),
                    review_status=row["review_status"],
                    evidence_count=int(row["evidence_count"]),
                    support_count=int(row["support_count"]),
                    contradiction_count=int(row["contradiction_count"]),
                    duplicate_count=int(row["duplicate_count"]),
                    source_version=row["source_version"],
                )
                for row in rows
            ]
        )

    def list_claim_relations(
        self, user: CurrentUser, project_id: UUID
    ) -> ClaimRelationListResponse:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select r.source_claim_id, r.target_claim_id, r.relation, r.confidence,
                      r.rationale_summary, source.text as source_text, target.text as target_text
                    from claim_relations r
                    join claims source on source.id = r.source_claim_id
                    join claims target on target.id = r.target_claim_id
                    where source.user_id = :user_id and target.user_id = :user_id
                      and source.project_id = :project_id and target.project_id = :project_id
                    order by r.created_at desc limit 300
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().all()
        return ClaimRelationListResponse(
            items=[
                ClaimRelationSummary(
                    source_claim_id=row["source_claim_id"],
                    target_claim_id=row["target_claim_id"],
                    relation=row["relation"],
                    confidence=float(row["confidence"]),
                    rationale_summary=row["rationale_summary"],
                    source_text=row["source_text"],
                    target_text=row["target_text"],
                )
                for row in rows
            ]
        )

    def list_reports(self, user: CurrentUser, project_id: UUID) -> ReportListResponse:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select r.id, r.source_run_id, r.title, r.status, r.revision,
                      r.validation_status, r.generated_at,
                      count(s.id) filter (where s.validation_status <> 'passed')
                        as affected_section_count
                    from reports r left join report_sections s on s.report_id = r.id
                    where r.project_id = :project_id and r.user_id = :user_id
                    group by r.id order by r.revision desc limit 100
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().all()
        return ReportListResponse(
            items=[
                ReportSummary(
                    report_id=row["id"],
                    source_run_id=row["source_run_id"],
                    title=row["title"],
                    status=row["status"],
                    revision=row["revision"],
                    validation_status=row["validation_status"],
                    affected_section_count=int(row["affected_section_count"]),
                    generated_at=row["generated_at"],
                )
                for row in rows
            ]
        )

    def get_report(self, user: CurrentUser, report_id: UUID) -> ReportDetail | None:
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id,source_run_id,title,status,revision,validation_status,generated_at
                    from reports where id=:report_id and user_id=:user_id
                    """
                ),
                {"report_id": report_id, "user_id": user.id},
            ).mappings().one_or_none()
            if row is None:
                return None
            sections = connection.execute(
                text(
                    """
                    select id,section_key,position,heading,body_markdown,evidence_snapshot,
                      validation_status
                    from report_sections where report_id=:report_id order by position
                    """
                ),
                {"report_id": report_id},
            ).mappings().all()
        affected = sum(section["validation_status"] != "passed" for section in sections)
        return ReportDetail(
            report_id=row["id"],
            source_run_id=row["source_run_id"],
            title=row["title"],
            status=row["status"],
            revision=row["revision"],
            validation_status=row["validation_status"],
            affected_section_count=affected,
            generated_at=row["generated_at"],
            sections=[
                ReportSectionRecord(
                    section_id=section["id"],
                    section_key=section["section_key"],
                    position=section["position"],
                    heading=section["heading"],
                    body_markdown=section["body_markdown"],
                    evidence_snapshot=dict(section["evidence_snapshot"]),
                    validation_status=section["validation_status"],
                )
                for section in sections
            ],
        )

    def list_pipeline_versions(self, user: CurrentUser) -> PipelineVersionListResponse:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id,name,version,configuration,code_sha,accepted_at
                    from pipeline_versions
                    where status='accepted'
                    order by accepted_at desc nulls last,name,version desc
                    """
                ),
                {},
            ).mappings().all()
        return PipelineVersionListResponse(
            items=[
                PipelineVersionSummary(
                    pipeline_version_id=row["id"],
                    name=row["name"],
                    version=row["version"],
                    configuration=dict(row["configuration"]),
                    code_sha=row["code_sha"],
                    accepted_at=row["accepted_at"],
                )
                for row in rows
            ]
        )

    def list_evaluation_datasets(
        self, user: CurrentUser, project_id: UUID | None
    ) -> EvaluationDatasetListResponse:
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select d.id,d.project_id,d.name,d.version,d.description,count(c.id) case_count
                    from evaluation_datasets d
                    left join evaluation_cases c on c.dataset_id=d.id
                    where d.user_id=:user_id and d.status='frozen'
                      and (:project_id is null or d.project_id=:project_id)
                    group by d.id order by d.name,d.version desc
                    """
                ),
                {"user_id": user.id, "project_id": project_id},
            ).mappings().all()
        return EvaluationDatasetListResponse(
            items=[
                EvaluationDatasetSummary(
                    dataset_id=row["id"],
                    project_id=row["project_id"],
                    name=row["name"],
                    version=row["version"],
                    description=row["description"],
                    case_count=int(row["case_count"]),
                )
                for row in rows
            ]
        )

    def refresh_report(
        self,
        user: CurrentUser,
        report_id: UUID,
        payload: ReportRefreshCreate,
        idempotency_key: str,
    ) -> ReportRefreshAccepted | None:
        request_hash = _fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            report = connection.execute(
                text(
                    """
                    select id, project_id, revision from reports
                    where id = :id and user_id = :user_id for update
                    """
                ),
                {"id": report_id, "user_id": user.id},
            ).mappings().one_or_none()
            if report is None:
                return None
            existing = connection.execute(
                text(
                    """
                    select id, input from workflow_runs
                    where user_id = :user_id and idempotency_key = :key
                    """
                ),
                {"user_id": user.id, "key": idempotency_key},
            ).mappings().one_or_none()
            if existing is not None:
                if existing["input"].get("request_hash") != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return self._refresh_accepted(
                    connection,
                    existing["id"],
                    report_id,
                    report["revision"],
                    payload.force_sections,
                )
            pipeline = connection.execute(
                text("select 1 from pipeline_versions where id = :id and status = 'accepted'"),
                {"id": payload.pipeline_version_id},
            ).one_or_none()
            if pipeline is None:
                raise EvidenceStoreError("PIPELINE_NOT_ACCEPTED")
            active = connection.execute(
                text(
                    """
                    select 1 from workflow_runs where kind = 'report_refresh'
                      and input ->> 'report_id' = :report_id
                      and status in ('pending','running','waiting_human')
                    """
                ),
                {"report_id": str(report_id)},
            ).one_or_none()
            if active is not None:
                raise EvidenceStoreError("REPORT_ALREADY_REFRESHING")
            all_sections = list(
                connection.execute(
                    text(
                        "select section_key from report_sections where report_id = :id order by position"
                    ),
                    {"id": report_id},
                ).scalars()
            )
            if payload.force_sections:
                requested = set(payload.force_sections)
                if len(requested) != len(payload.force_sections) or not requested <= set(
                    all_sections
                ):
                    raise EvidenceStoreError("REPORT_SECTIONS_INVALID")
                impacted = [key for key in all_sections if key in requested]
            else:
                changed_ids = list(payload.changed_document_ids)
                owned_count = connection.execute(
                    text(
                        """
                        select count(*) from documents
                        where user_id=:user_id and project_id=:project_id and id=any(:ids)
                          and status='ready'
                        """
                    ),
                    {
                        "user_id": user.id,
                        "project_id": report["project_id"],
                        "ids": changed_ids,
                    },
                ).scalar_one()
                if owned_count != len(set(changed_ids)):
                    raise EvidenceStoreError("DOCUMENT_NOT_READY")
                directly_affected = set(
                    connection.execute(
                        text(
                            """
                            select distinct rs.section_key
                            from report_sections rs
                            join lateral jsonb_array_elements_text(
                              coalesce(rs.evidence_snapshot -> 'claim_ids','[]'::jsonb)
                            ) as snapshot_claim(claim_id) on true
                            join claim_evidence ce
                              on ce.claim_id=snapshot_claim.claim_id::uuid
                            join citations c on c.id=ce.citation_id
                            where rs.report_id=:report_id and c.document_id=any(:document_ids)
                            """
                        ),
                        {"report_id": report_id, "document_ids": changed_ids},
                    ).scalars()
                )
                # A newly added document has no old citation edge. Re-evaluate every existing
                # section against only the changed-document vector filter, then preserve every
                # section that the refresh does not replace.
                impacted = [
                    key for key in all_sections if key in directly_affected
                ] or all_sections
            run_id = uuid4()
            run_input = {
                **payload.model_dump(mode="json"),
                "report_id": str(report_id),
                "impacted_section_keys": impacted,
                "request_hash": request_hash,
            }
            connection.execute(
                text(
                    """
                    insert into workflow_runs (
                      id,user_id,project_id,pipeline_version_id,kind,status,idempotency_key,
                      checkpoint_ref,input
                    ) values (
                      :id,:user_id,:project_id,:pipeline_id,'report_refresh','pending',:key,
                      :checkpoint_ref,cast(:input as jsonb)
                    )
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": report["project_id"],
                    "pipeline_id": payload.pipeline_version_id,
                    "key": idempotency_key,
                    "checkpoint_ref": str(run_id),
                    "input": _json(run_input),
                },
            )
            self._append_event(
                connection,
                run_id,
                node_key="workflow",
                event_type="run_status_changed",
                status="pending",
                safe_payload={"progress": 0, "report_id": str(report_id)},
            )
            self._append_outbox(
                connection,
                aggregate_type="workflow_run",
                aggregate_id=run_id,
                event_type="workflow.run.requested",
                payload={"run_id": str(run_id), "user_id": str(user.id)},
                idempotency_key=f"workflow:{run_id}:start:v1",
            )
            return ReportRefreshAccepted(
                run_id=run_id,
                base_revision=report["revision"],
                planned_revision=report["revision"] + 1,
                impacted_section_keys=impacted,
                events_url=f"/api/v1/runs/{run_id}/events",
            )

    @staticmethod
    def _refresh_accepted(
        connection: Connection,
        run_id: UUID,
        report_id: UUID,
        base_revision: int,
        fallback_sections: list[str],
    ) -> ReportRefreshAccepted:
        run_input = connection.execute(
            text("select input from workflow_runs where id = :id"), {"id": run_id}
        ).scalar_one()
        impacted = run_input.get("impacted_section_keys") or fallback_sections
        return ReportRefreshAccepted(
            run_id=run_id,
            base_revision=base_revision,
            planned_revision=base_revision + 1,
            impacted_section_keys=impacted,
            events_url=f"/api/v1/runs/{run_id}/events",
        )

    def create_evaluation_run(
        self, user: CurrentUser, payload: EvaluationRunCreate, idempotency_key: str
    ) -> EvaluationRunAccepted:
        request_hash = _fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = connection.execute(
                text(
                    """
                    select id, summary, budget_limit_usd from evaluation_runs
                    where user_id = :user_id and idempotency_key = :key for update
                    """
                ),
                {"user_id": user.id, "key": idempotency_key},
            ).mappings().one_or_none()
            if existing is not None:
                summary = existing["summary"] or {}
                if summary.get("request_hash") != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return EvaluationRunAccepted(
                    evaluation_run_id=existing["id"],
                    case_count=int(summary.get("case_count", 0)),
                    status_url=f"/api/v1/evaluation-runs/{existing['id']}",
                    estimated_budget_boundary=existing["budget_limit_usd"],
                )
            valid = connection.execute(
                text(
                    """
                    select d.project_id, count(c.id) as case_count
                    from evaluation_datasets d
                    join pipeline_versions v on v.id = :pipeline_id and v.status = 'accepted'
                    left join evaluation_cases c on c.dataset_id = d.id
                    where d.id = :dataset_id and d.status = 'frozen'
                      and (d.user_id = :user_id or :privileged)
                    group by d.project_id
                    """
                ),
                {
                    "dataset_id": payload.dataset_id,
                    "pipeline_id": payload.pipeline_version_id,
                    "user_id": user.id,
                    "privileged": user.role in {"developer", "admin"},
                },
            ).mappings().one_or_none()
            if valid is None:
                raise EvidenceStoreError("DATASET_NOT_FROZEN")
            run_id = uuid4()
            budget_limit = payload.max_cost_usd or DEFAULT_EVALUATION_BUDGET_USD
            summary = {
                "request_hash": request_hash,
                "case_count": int(valid["case_count"]),
                "metrics": payload.metrics,
                "max_parallelism": payload.max_parallelism,
                "max_cost_usd": str(budget_limit),
                "labels": payload.labels,
            }
            connection.execute(
                text(
                    """
                    insert into evaluation_runs (
                      id,user_id,project_id,dataset_id,pipeline_version_id,status,
                      idempotency_key,summary,budget_limit_usd
                    ) values (
                      :id,:user_id,:project_id,:dataset_id,:pipeline_id,'pending',:key,
                      cast(:summary as jsonb),:budget_limit
                    )
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user.id,
                    "project_id": valid["project_id"],
                    "dataset_id": payload.dataset_id,
                    "pipeline_id": payload.pipeline_version_id,
                    "key": idempotency_key,
                    "summary": _json(summary),
                    "budget_limit": budget_limit,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="evaluation_run",
                aggregate_id=run_id,
                event_type="evaluation.run.requested",
                payload={"evaluation_run_id": str(run_id), "user_id": str(user.id)},
                idempotency_key=f"evaluation:{run_id}:start:v1",
            )
            return EvaluationRunAccepted(
                evaluation_run_id=run_id,
                case_count=int(valid["case_count"]),
                status_url=f"/api/v1/evaluation-runs/{run_id}",
                estimated_budget_boundary=budget_limit,
            )

    def get_evaluation_run(
        self, user: CurrentUser, evaluation_run_id: UUID
    ) -> EvaluationRunRecord | None:
        privileged = user.role in {"developer", "admin"}
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id,dataset_id,pipeline_version_id,status,summary,created_at,
                      started_at,completed_at
                    from evaluation_runs
                    where id = :id and (user_id = :user_id or :privileged)
                    """
                ),
                {"id": evaluation_run_id, "user_id": user.id, "privileged": privileged},
            ).mappings().one_or_none()
            if row is None:
                return None
            scores = connection.execute(
                text(
                    """
                    select case_id,metric_name,metric_version,value,passed,details,judge_model
                    from evaluation_scores where evaluation_run_id = :id
                    order by case_id,metric_name,metric_version
                    """
                ),
                {"id": evaluation_run_id},
            ).mappings().all()
            total_cases = connection.execute(
                text("select count(*) from evaluation_cases where dataset_id = :id"),
                {"id": row["dataset_id"]},
            ).scalar_one()
            scored_cases = connection.execute(
                text(
                    "select count(distinct case_id) from evaluation_scores where evaluation_run_id = :id"
                ),
                {"id": evaluation_run_id},
            ).scalar_one()
        progress = 100 if row["status"] in {"succeeded", "failed", "cancelled"} else (
            int(scored_cases * 100 / total_cases) if total_cases else 0
        )
        return EvaluationRunRecord(
            evaluation_run_id=row["id"],
            dataset_id=row["dataset_id"],
            pipeline_version_id=row["pipeline_version_id"],
            status=row["status"],
            progress=progress,
            summary=row["summary"],
            scores=[dict(score) for score in scores],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def reliability(self, user: CurrentUser, window_hours: int) -> ReliabilityResponse:
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        with self._transaction(user) as connection:
            aggregate = connection.execute(
                text(
                    """
                    select count(distinct r.id) as run_count,
                      count(distinct r.id) filter (where r.status = 'succeeded') as succeeded,
                      count(distinct r.id) filter (where r.status = 'failed') as failed,
                      count(*) filter (where e.event_type = 'retry_scheduled') as retries,
                      percentile_cont(0.5) within group (order by e.latency_ms)
                        filter (where e.latency_ms is not null) as p50,
                      percentile_cont(0.95) within group (order by e.latency_ms)
                        filter (where e.latency_ms is not null) as p95,
                      coalesce(sum(e.input_tokens),0) as input_tokens,
                      coalesce(sum(e.output_tokens),0) as output_tokens,
                      coalesce(sum(e.cost_usd),0) as cost_usd
                    from workflow_runs r left join run_events e on e.run_id = r.id
                    where r.created_at >= now() - make_interval(hours => :hours)
                    """
                ),
                {"hours": window_hours},
            ).mappings().one()
            trace_ids = connection.execute(
                text(
                    """
                    select id from workflow_runs
                    where created_at >= now() - make_interval(hours => :hours)
                    order by created_at desc limit 10
                    """
                ),
                {"hours": window_hours},
            ).scalars().all()
        terminal = int(aggregate["succeeded"]) + int(aggregate["failed"])
        denominator = max(1, terminal)
        return ReliabilityResponse(
            window_hours=window_hours,
            run_count=int(aggregate["run_count"]),
            success_rate=int(aggregate["succeeded"]) / denominator,
            error_rate=int(aggregate["failed"]) / denominator,
            retry_count=int(aggregate["retries"]),
            p50_latency_ms=int(aggregate["p50"]) if aggregate["p50"] is not None else None,
            p95_latency_ms=int(aggregate["p95"]) if aggregate["p95"] is not None else None,
            input_tokens=int(aggregate["input_tokens"]),
            output_tokens=int(aggregate["output_tokens"]),
            cost_usd=Decimal(aggregate["cost_usd"]),
            sample_trace_ids=list(trace_ids),
        )

    def create_fault_scenario(
        self, user: CurrentUser, payload: FaultScenarioCreate, idempotency_key: str
    ) -> FaultScenarioAccepted:
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        request_hash = _fingerprint(payload)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=payload.duration_seconds)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            existing = connection.execute(
                text(
                    """
                    select id,target_run_id,expires_at,request_hash from fault_exercises
                    where requested_by=:user_id and idempotency_key=:key for update
                    """
                ),
                {"user_id": user.id, "key": idempotency_key},
            ).mappings().one_or_none()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise EvidenceStoreError("IDEMPOTENCY_KEY_REUSED")
                return FaultScenarioAccepted(
                    exercise_id=existing["id"],
                    target_run_id=existing["target_run_id"],
                    expected_recovery_state="simulation_completed_without_external_mutation",
                    status_url=f"/api/v1/dev/fault-scenarios/{existing['id']}",
                    expires_at=existing["expires_at"],
                )
            if payload.target_run_id is not None:
                target_exists = connection.execute(
                    text("select 1 from workflow_runs where id=:id"),
                    {"id": payload.target_run_id},
                ).one_or_none()
                if target_exists is None:
                    raise EvidenceStoreError("RUN_NOT_FOUND", status_code=404)
            exercise_id = uuid4()
            connection.execute(
                text(
                    """
                    insert into fault_exercises (
                      id,requested_by,target_run_id,scenario,duration_seconds,status,
                      request_hash,idempotency_key,expires_at
                    ) values (
                      :id,:user_id,:target_run_id,:scenario,:duration_seconds,'pending',
                      :request_hash,:key,:expires_at
                    )
                    """
                ),
                {
                    "id": exercise_id,
                    "user_id": user.id,
                    "target_run_id": payload.target_run_id,
                    "scenario": payload.scenario,
                    "duration_seconds": payload.duration_seconds,
                    "request_hash": request_hash,
                    "key": idempotency_key,
                    "expires_at": expires_at,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="fault_exercise",
                aggregate_id=exercise_id,
                event_type="fault.exercise.requested",
                payload={
                    **payload.model_dump(mode="json"),
                    "exercise_id": str(exercise_id),
                    "requested_by": str(user.id),
                    "expires_at": expires_at.isoformat(),
                },
                idempotency_key=f"fault:{user.id}:{idempotency_key}",
            )
        return FaultScenarioAccepted(
            exercise_id=exercise_id,
            target_run_id=payload.target_run_id,
            expected_recovery_state="simulation_completed_without_external_mutation",
            status_url=f"/api/v1/dev/fault-scenarios/{exercise_id}",
            expires_at=expires_at,
        )

    def get_fault_scenario(
        self, user: CurrentUser, exercise_id: UUID
    ) -> FaultScenarioRecord | None:
        if user.role not in {"developer", "admin"}:
            raise EvidenceStoreError("ADMIN_REQUIRED", status_code=403)
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id,scenario,target_run_id,status,attempts,expires_at,safe_result,
                      last_error_code,created_at,started_at,completed_at
                    from fault_exercises where id=:id and requested_by=:user_id
                    """
                ),
                {"id": exercise_id, "user_id": user.id},
            ).mappings().one_or_none()
        if row is None:
            return None
        return FaultScenarioRecord(
            exercise_id=row["id"],
            scenario=row["scenario"],
            target_run_id=row["target_run_id"],
            status=row["status"],
            attempts=row["attempts"],
            expires_at=row["expires_at"],
            safe_result=row["safe_result"],
            error_code=row["last_error_code"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _lock_idempotency(
        connection: Connection, user_id: UUID, idempotency_key: str
    ) -> None:
        connection.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key,2))"),
            {"key": f"{user_id}:{idempotency_key}"},
        )

    @staticmethod
    def _append_event(
        connection: Connection,
        run_id: UUID,
        *,
        node_key: str,
        event_type: str,
        status: str,
        safe_payload: dict,
        attempt: int = 1,
    ) -> None:
        connection.execute(
            text(
                """
                insert into run_events (
                  run_id,sequence,node_key,event_type,attempt,status,safe_payload
                ) values (
                  :run_id,
                  coalesce((select max(sequence)+1 from run_events where run_id=:run_id),0),
                  :node_key,:event_type,:attempt,:status,cast(:payload as jsonb)
                )
                """
            ),
            {
                "run_id": run_id,
                "node_key": node_key,
                "event_type": event_type,
                "attempt": attempt,
                "status": status,
                "payload": _json(safe_payload),
            },
        )

    @staticmethod
    def _append_outbox(
        connection: Connection,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
        idempotency_key: str,
    ) -> None:
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type,aggregate_id,event_type,payload,idempotency_key
                ) values (
                  :aggregate_type,:aggregate_id,:event_type,cast(:payload as jsonb),:key
                ) on conflict (idempotency_key) do nothing
                """
            ),
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": _json(payload),
                "key": idempotency_key,
            },
        )
