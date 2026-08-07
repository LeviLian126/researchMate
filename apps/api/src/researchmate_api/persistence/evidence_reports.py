"""Atomic report-refresh workflow persistence operations."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from researchmate_api.persistence.evidence_base import _json
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import ReportRefreshAccepted, ReportRefreshCreate
from researchmate_api.services.evidence_store import EvidenceStoreError, evidence_fingerprint


class PostgresEvidenceReportMixin:
    """Atomic report-refresh workflow persistence operations."""

    def refresh_report(
        self,
        user: CurrentUser,
        report_id: UUID,
        payload: ReportRefreshCreate,
        idempotency_key: str,
    ) -> ReportRefreshAccepted | None:
        """Create an idempotent report-refresh workflow for an owned report."""
        request_hash = evidence_fingerprint(payload)
        with self._transaction(user) as connection:
            self._lock_idempotency(connection, user.id, idempotency_key)
            report = (
                connection.execute(
                    text(
                        """
                    select r.id, r.project_id, r.revision from reports r
                    join projects p on p.id = r.project_id and p.user_id = r.user_id
                    where r.id = :id and r.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    for update of r, p
                    """
                    ),
                    {"id": report_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if report is None:
                return None
            existing = (
                connection.execute(
                    text(
                        """
                    select id, input from workflow_runs
                    where user_id = :user_id and idempotency_key = :key
                    """
                    ),
                    {"user_id": user.id, "key": idempotency_key},
                )
                .mappings()
                .one_or_none()
            )
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
                impacted = [key for key in all_sections if key in directly_affected] or all_sections
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
        """Reconstruct the accepted refresh contract for an idempotent replay."""
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
