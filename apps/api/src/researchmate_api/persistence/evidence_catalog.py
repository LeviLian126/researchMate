"""Read-only claim, report, pipeline, and evaluation-dataset projections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    ClaimListResponse,
    ClaimRelationListResponse,
    ClaimRelationSummary,
    ClaimSummary,
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
    PipelineVersionListResponse,
    PipelineVersionSummary,
    ReportDetail,
    ReportListResponse,
    ReportSectionRecord,
    ReportSummary,
)


class PostgresEvidenceCatalogMixin:
    """Read-only claim, report, pipeline, and evaluation-dataset projections."""

    def list_claims(self, user: CurrentUser, project_id: UUID) -> ClaimListResponse:
        """List bounded claim summaries and aggregate evidence counts for one owner project."""
        with self._transaction(user) as connection:
            rows = (
                connection.execute(
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
  and exists (
    select 1 from projects p
    where p.id = c.project_id and p.user_id = :user_id
      and p.status = 'active' and p.deleted_at is null
  )
                    group by c.id order by c.created_at desc limit 200
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .mappings()
                .all()
            )
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
        """List bounded claim relations whose endpoints belong to one owner project."""
        with self._transaction(user) as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select r.source_claim_id, r.target_claim_id, r.relation, r.confidence,
                      r.rationale_summary, source.text as source_text, target.text as target_text
                    from claim_relations r
                    join claims source on source.id = r.source_claim_id
                    join claims target on target.id = r.target_claim_id
                    where source.user_id = :user_id and target.user_id = :user_id
                      and source.project_id = :project_id and target.project_id = :project_id
  and exists (
    select 1 from projects p
    where p.id = :project_id and p.user_id = :user_id
      and p.status = 'active' and p.deleted_at is null
  )
                    order by r.created_at desc limit 300
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .mappings()
                .all()
            )
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
        """List bounded report summaries for one owner project."""
        with self._transaction(user) as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select r.id, r.source_run_id, r.title, r.status, r.revision,
                      r.validation_status, r.generated_at,
                      count(s.id) filter (where s.validation_status <> 'passed')
                        as affected_section_count
                    from reports r left join report_sections s on s.report_id = r.id
                    where r.project_id = :project_id and r.user_id = :user_id
  and exists (
    select 1 from projects p
    where p.id = :project_id and p.user_id = :user_id
      and p.status = 'active' and p.deleted_at is null
  )
                    group by r.id order by r.revision desc limit 100
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .mappings()
                .all()
            )
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
        """Read one owner-scoped report with its ordered sections."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id,source_run_id,title,status,revision,validation_status,generated_at
                    from reports where id=:report_id and user_id=:user_id
                    """
                    ),
                    {"report_id": report_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            sections = (
                connection.execute(
                    text(
                        """
                    select id,section_key,position,heading,body_markdown,evidence_snapshot,
                      validation_status
                    from report_sections where report_id=:report_id order by position
                    """
                    ),
                    {"report_id": report_id},
                )
                .mappings()
                .all()
            )
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
        """List the pipeline versions visible to the current user."""
        with self._transaction(user) as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select id,name,version,configuration,code_sha,accepted_at
                    from pipeline_versions
                    where status='accepted'
                    order by accepted_at desc nulls last,name,version desc
                    """
                    ),
                    {},
                )
                .mappings()
                .all()
            )
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
        """List evaluation datasets visible under the user role boundary."""
        with self._transaction(user) as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select d.id,d.project_id,d.name,d.version,d.description,count(c.id) case_count
                    from evaluation_datasets d
                    left join evaluation_cases c on c.dataset_id=d.id
                    where d.user_id=:user_id and d.status='frozen'
                      and (:project_id is null or d.project_id=:project_id)
  and (:project_id is null or exists (
    select 1 from projects p
    where p.id = :project_id and p.user_id = :user_id
      and p.status = 'active' and p.deleted_at is null
  ))
                    group by d.id order by d.name,d.version desc
                    """
                    ),
                    {"user_id": user.id, "project_id": project_id},
                )
                .mappings()
                .all()
            )
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
