"""Bind workflow providers and own run initialization plus delivery lease transitions."""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.web_search import (
    TavilyWebSearchProvider,
)
from sqlalchemy import Engine, text

from researchmate_worker.evidence_graph import EvidenceWorkflowState
from researchmate_worker.workflow_commit import WorkflowCommitMixin
from researchmate_worker.workflow_events import WorkflowEventsMixin
from researchmate_worker.workflow_execution import WorkflowExecutionMixin
from researchmate_worker.workflow_models import WorkflowPipelineConfig, WorkflowRuntimeError


class SqlEvidenceWorkflowDomain(WorkflowExecutionMixin, WorkflowCommitMixin, WorkflowEventsMixin):
    """Coordinate workflow core while preserving lease, retry, and ownership rules."""

    def __init__(
        self,
        *,
        engine: Engine,
        provider: ChatProvider,
        vector_store: QdrantHybridStore,
        pipeline_version: str,
        web_search: TavilyWebSearchProvider | None = None,
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.vector_store = vector_store
        self.pipeline_version = pipeline_version
        self.web_search = web_search

    def bind_run(self, run_id: UUID) -> None:
        """Attach run context to providers that support usage attribution."""
        binder = getattr(self.provider, "bind_run", None)
        if binder is not None:
            binder(run_id)

    def initial_state(self, run_id: UUID, user_id: UUID) -> EvidenceWorkflowState:
        """Validate ownership and pipeline configuration before starting a run."""
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select r.id,r.user_id,r.project_id,r.kind,r.input,r.pipeline_version_id,
                      v.configuration
                    from workflow_runs r join pipeline_versions v on v.id=r.pipeline_version_id
                    where r.id=:run_id and r.user_id=:user_id
                      and r.kind in ('evidence_review','report_refresh') and v.status='accepted'
                    """
                    ),
                    {"run_id": run_id, "user_id": user_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise WorkflowRuntimeError("RUN_NOT_FOUND")
            connection.execute(
                text(
                    """
                    update workflow_runs set status='running',started_at=coalesce(started_at,now()),
                      error_code=null where id=:run_id and status in ('pending','running')
                    """
                ),
                {"run_id": run_id},
            )
            self._event(
                connection,
                run_id,
                "workflow",
                "run_status_changed",
                "running",
                {"progress": 1},
            )
            run_input = row["input"]
            try:
                pipeline = WorkflowPipelineConfig.model_validate(row["configuration"])
            except ValidationError as exc:
                raise WorkflowRuntimeError("PIPELINE_CONFIGURATION_INVALID") from exc
            if getattr(self.provider, "model", pipeline.model) != pipeline.model:
                raise WorkflowRuntimeError("PIPELINE_MODEL_NOT_CONFIGURED")
            if pipeline.evidence_prompt_version != "evidence-review-v1":
                raise WorkflowRuntimeError("PIPELINE_PROMPT_NOT_SUPPORTED")
            source_scope = run_input.get("source_scope") or {}
            impacted_sections: list[str] = []
            research_goal = run_input.get("research_goal")
            if row["kind"] == "report_refresh":
                base_report_id = run_input.get("report_id")
                if not base_report_id:
                    raise WorkflowRuntimeError("REPORT_REFRESH_INPUT_INVALID")
                base = connection.execute(
                    text(
                        """
                        select title from reports
                        where id=:report_id and user_id=:user_id and project_id=:project_id
                        """
                    ),
                    {
                        "report_id": UUID(base_report_id),
                        "user_id": user_id,
                        "project_id": row["project_id"],
                    },
                ).scalar_one_or_none()
                if base is None:
                    raise WorkflowRuntimeError("REPORT_NOT_FOUND")
                requested = set(run_input.get("impacted_section_keys") or [])
                available = list(
                    connection.execute(
                        text(
                            """
                            select section_key from report_sections
                            where report_id=:report_id order by position
                            """
                        ),
                        {"report_id": UUID(base_report_id)},
                    ).scalars()
                )
                impacted_sections = [key for key in available if key in requested]
                if not impacted_sections or len(impacted_sections) != len(requested):
                    raise WorkflowRuntimeError("REPORT_SECTIONS_INVALID")
                research_goal = (
                    f"Incrementally refresh report '{base}' for these exact sections: "
                    + ", ".join(impacted_sections)
                )
        return EvidenceWorkflowState(
            run_id=str(run_id),
            user_id=str(user_id),
            project_id=str(row["project_id"]),
            research_goal=research_goal or "Refresh the affected report evidence.",
            review_policy=run_input.get("review_policy", "strict"),
            run_kind=row["kind"],
            base_report_id=str(run_input.get("report_id") or ""),
            impacted_section_keys=impacted_sections,
            changed_document_ids=list(run_input.get("changed_document_ids") or []),
            selected_document_ids=list(source_scope.get("document_ids") or []),
            allow_web=bool(source_scope.get("allow_web", False)),
            retrieval_limit=pipeline.retrieval_limit,
            pipeline_model=pipeline.model,
            evidence_prompt_version=pipeline.evidence_prompt_version,
            pipeline_version_ref=str(row["pipeline_version_id"]),
            evidence_batches=[],
        )

    def claim_delivery(self, run_id: UUID, worker_id: str, lease_seconds: int) -> bool:
        """Acquire one expiring workflow delivery lease; duplicate Celery deliveries are no-ops."""

        with self.engine.begin() as connection:
            claimed = connection.execute(
                text(
                    """
                    update workflow_runs set
                      lease_owner=:worker_id,
                      lease_expires_at=now() + make_interval(secs => :lease_seconds),
                      delivery_attempts=delivery_attempts + 1
                    where id=:run_id
                      and status in ('pending','running')
                      and (lease_expires_at is null or lease_expires_at < now()
                           or lease_owner=:worker_id)
                    returning id
                    """
                ),
                {
                    "run_id": run_id,
                    "worker_id": worker_id[:200],
                    "lease_seconds": lease_seconds,
                },
            ).one_or_none()
        return claimed is not None

    def release_delivery(self, run_id: UUID, worker_id: str) -> None:
        """Release only the lease held by the current worker delivery."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update workflow_runs set lease_owner=null,lease_expires_at=null
                    where id=:run_id and lease_owner=:worker_id
                    """
                ),
                {"run_id": run_id, "worker_id": worker_id[:200]},
            )

    def record_retry(self, run_id: UUID, code: str, countdown: int) -> None:
        """Record bounded retry intent without marking the run terminal."""
        with self.engine.begin() as connection:
            self._event(
                connection,
                run_id,
                "workflow",
                "retry_scheduled",
                "pending",
                {"error_code": code[:120], "countdown_seconds": countdown},
            )
