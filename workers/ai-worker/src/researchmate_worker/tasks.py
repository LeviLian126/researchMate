"""Register stable Celery task names and enforce bounded retry and lease behavior."""

from __future__ import annotations

import os
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from researchmate_api.services.evidence_generation import EvidenceGenerationError
from researchmate_api.services.llm import ProviderRequestError
from researchmate_api.services.qdrant_store import (
    VectorStoreRequestError,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from researchmate_worker.budget import WorkflowBudgetExceeded
from researchmate_worker.celery_app import celery_app
from researchmate_worker.config import WorkerSettings, psycopg_database_url
from researchmate_worker.deletion import (
    DocumentDeletionEvent,
    ProjectDeletionEvent,
)
from researchmate_worker.evaluation import (
    EvaluationRuntimeError,
)
from researchmate_worker.evidence_graph import build_evidence_graph
from researchmate_worker.ingestion import (
    IngestionEvent,
    IngestionFailure,
)
from researchmate_worker.task_builders import (
    EvaluationTaskEvent,
    FaultSimulationTaskEvent,
    WorkflowTaskEvent,
    build_deletion_service,
    build_evaluation_runner,
    build_fault_simulation_service,
    build_ingestion_service,
    build_project_deletion_service,
    build_workflow_domain,
)
from researchmate_worker.workflow_runtime import (
    WorkflowRuntimeError,
)


def _bootstrap_failure_engine(database_url: str) -> Engine:
    """Build a short-lived engine for one-shot bootstrap-failure markers.

    INFRA-4: these engines run a single UPDATE and Dispose. Pinning pool_size and
    max_overflow keeps the short-lived engine from ever opening the default 5+10
    connections against the Supabase free-tier ceiling even under failure storms.
    pool_recycle=300 matches the API/repository engines for connection-health parity.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=2,
        max_overflow=3,
    )


def _mark_workflow_bootstrap_failed(settings: WorkerSettings, run_id: UUID, code: str) -> None:
    if not settings.database_url:
        return
    # INFRA-4: even one-shot bootstrap-failure markers get a bounded pool so the
    # short-lived engine does not open the default 5+10 connections against Supabase.
    engine = _bootstrap_failure_engine(psycopg_database_url(settings.database_url))
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                update workflow_runs set status='failed',error_code=:code,completed_at=now(),
                  lease_owner=null,lease_expires_at=null
                where id=:run_id and status not in ('succeeded','cancelled')
                """
            ),
            {"run_id": run_id, "code": code[:120]},
        )


def _mark_job_bootstrap_failed(settings: WorkerSettings | None, job_id: UUID, code: str) -> None:
    """Make a task-construction failure terminal so an explicit retry can recover it."""
    database_url = settings.database_url if settings is not None else os.getenv("DATABASE_URL")
    if not database_url:
        return
    # INFRA-4: bootstrap-failure markers are one-shot, but still get a bounded pool so
    # the engine never opens the default 5+10 connections against Supabase free tier.
    engine = _bootstrap_failure_engine(psycopg_database_url(database_url))
    with engine.begin() as connection:
        failed = (
            connection.execute(
                text(
                    """
                update jobs
                set status='failed', error_message=:code, completed_at=now(),
                  lease_owner=null, lease_expires_at=null, updated_at=now()
                where id=:job_id and (
                  status='pending'
                  or (status='running' and lease_expires_at < now())
                )
                returning type, document_id
                """
                ),
                {"job_id": job_id, "code": code[:120]},
            )
            .mappings()
            .one_or_none()
        )
        if failed is None:
            return
        if failed["type"] == "parse_and_index_document" and failed["document_id"] is not None:
            connection.execute(
                text(
                    """
                    update documents set status='failed', error_message=:code, updated_at=now()
                    where id=:document_id and status in ('uploaded','parsing','parsed','indexing')
                    """
                ),
                {"document_id": failed["document_id"], "code": code[:120]},
            )
        if failed["type"] in {"delete_document", "delete_project"}:
            connection.execute(
                text(
                    """
                    update deletion_jobs set status='failed', error_message=:code,
                      completed_at=now()
                    where id=:job_id and status in ('pending','running')
                    """
                ),
                {"job_id": job_id, "code": code[:120]},
            )


def _mark_fault_exercise_failed(
    settings: WorkerSettings | None, exercise_id: UUID, code: str
) -> None:
    """Make a fault-simulation failure terminal so an explicit retry can recover it."""
    database_url = settings.database_url if settings is not None else os.getenv("DATABASE_URL")
    if not database_url:
        return
    # INFRA-4: bootstrap-failure markers are one-shot, but still get a bounded pool so
    # the engine never opens the default 5+10 connections against Supabase free tier.
    engine = _bootstrap_failure_engine(psycopg_database_url(database_url))
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                update fault_exercises set status='failed', last_error_code=:code,
                  completed_at=now(), lease_owner=null, lease_expires_at=null
                where id=:exercise_id and status in ('pending','running')
                """
            ),
            {"exercise_id": exercise_id, "code": code[:120]},
        )


def _mark_evaluation_run_failed(settings: WorkerSettings | None, run_id: UUID, code: str) -> None:
    """Make an evaluation-run failure terminal so an explicit retry can recover it."""
    database_url = settings.database_url if settings is not None else os.getenv("DATABASE_URL")
    if not database_url:
        return
    # INFRA-4: bootstrap-failure markers are one-shot, but still get a bounded pool so
    # the engine never opens the default 5+10 connections against Supabase free tier.
    engine = _bootstrap_failure_engine(psycopg_database_url(database_url))
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                update evaluation_runs set status='failed', error_code=:code,
                  completed_at=now(), lease_owner=null, lease_expires_at=null
                where id=:run_id and status in ('pending','running')
                """
            ),
            {"run_id": run_id, "code": code[:120]},
        )


@celery_app.task(bind=True, name="researchmate.ingest_document", max_retries=5)
def ingest_document(self, event: dict[str, str]) -> str:
    """Validate an outbox payload and execute one lease-protected ingestion delivery."""
    payload = IngestionEvent.model_validate(event)
    try:
        settings = WorkerSettings()
    except Exception:
        _mark_job_bootstrap_failed(None, payload.job_id, "WORKER_CONFIG_INVALID")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        service = build_ingestion_service()
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "INGESTION_BOOTSTRAP_FAILED")
        raise
    try:
        return service.handle(payload, worker_id=worker_id)
    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "INGESTION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.delete_document", max_retries=5)
def delete_document(self, event: dict[str, str]) -> str:
    """Execute one validated document-deletion delivery under a worker lease."""
    payload = DocumentDeletionEvent.model_validate(event)
    try:
        settings = WorkerSettings()
    except Exception:
        _mark_job_bootstrap_failed(None, payload.job_id, "WORKER_CONFIG_INVALID")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        service = build_deletion_service()
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "DELETION_BOOTSTRAP_FAILED")
        raise
    try:
        return service.handle(payload, worker_id=worker_id)
    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "DELETION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.delete_project", max_retries=8)
def delete_project(self, event: dict[str, str]) -> str:
    """Execute one validated project-deletion delivery under a worker lease."""
    payload = ProjectDeletionEvent.model_validate(event)
    try:
        settings = WorkerSettings()
    except Exception:
        _mark_job_bootstrap_failed(None, payload.job_id, "WORKER_CONFIG_INVALID")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        service = build_project_deletion_service()
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "PROJECT_DELETION_BOOTSTRAP_FAILED")
        raise
    try:
        return service.handle(payload, worker_id=worker_id)
    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "PROJECT_DELETION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.run_workflow", max_retries=5)
def run_workflow(self, event: dict[str, str]) -> str:
    """Resume or start one checkpointed evidence workflow delivery."""
    payload = WorkflowTaskEvent.model_validate(event)
    settings = WorkerSettings()
    try:
        domain = build_workflow_domain(settings)
    except Exception:
        _mark_workflow_bootstrap_failed(settings, payload.run_id, "WORKFLOW_BOOTSTRAP_FAILED")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    if not domain.claim_delivery(payload.run_id, worker_id, settings.workflow_lease_seconds):
        return "duplicate_or_not_runnable"
    domain.bind_run(payload.run_id)
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        from langgraph.types import Command
    except ImportError as exc:
        domain.mark_failed(payload.run_id, "LANGGRAPH_NOT_INSTALLED")
        raise WorkflowRuntimeError("LANGGRAPH_NOT_INSTALLED") from exc
    checkpoint_url = str(settings.database_url).replace("postgresql+psycopg://", "postgresql://")
    try:
        with PostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
            strict_checkpointer = PostgresSaver(
                checkpointer.conn,
                checkpointer.pipe,
                serde=JsonPlusSerializer(pickle_fallback=False),
            )
            graph = build_evidence_graph(domain, strict_checkpointer)
            config: RunnableConfig = {"configurable": {"thread_id": str(payload.run_id)}}
            if payload.decision_id is not None:
                resume_value = domain.resume_value(payload.decision_id, payload.run_id)
                result = graph.invoke(Command(resume=resume_value), config=config)
            elif strict_checkpointer.get_tuple(config) is not None:
                result = graph.invoke(None, config=config)
            else:
                if payload.user_id is None:
                    raise WorkflowRuntimeError("WORKFLOW_USER_MISSING")
                initial = domain.initial_state(payload.run_id, payload.user_id)
                result = graph.invoke(initial, config=config)
        if isinstance(result, dict) and result.get("__interrupt__"):
            domain.release_delivery(payload.run_id, worker_id)
            return "waiting_human"
        domain.release_delivery(payload.run_id, worker_id)
        return "succeeded"
    except (
        ProviderRequestError,
        VectorStoreRequestError,
        WorkflowRuntimeError,
        WorkflowBudgetExceeded,
    ) as exc:
        retryable = bool(getattr(exc, "retryable", False))
        if retryable and int(self.request.retries) < 4:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            domain.record_retry(payload.run_id, getattr(exc, "code", str(exc)), countdown)
            domain.release_delivery(payload.run_id, worker_id)
            raise self.retry(
                exc=WorkflowRuntimeError(str(exc), retryable=True), countdown=countdown
            )
        domain.mark_failed(payload.run_id, getattr(exc, "code", "WORKFLOW_PROVIDER_FAILED"))
        raise
    except EvidenceGenerationError as exc:
        domain.mark_failed(payload.run_id, "WORKFLOW_OUTPUT_INVALID")
        raise WorkflowRuntimeError("WORKFLOW_OUTPUT_INVALID") from exc
    except Exception:
        domain.mark_failed(payload.run_id, "WORKFLOW_RUNTIME_FAILED")
        raise


@celery_app.task(bind=True, name="researchmate.run_evaluation", max_retries=3)
def run_evaluation(self, event: dict[str, str]) -> str:
    """Execute one lease-protected evaluation run with bounded retries."""
    payload = EvaluationTaskEvent.model_validate(event)
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        return build_evaluation_runner(WorkerSettings()).run(
            payload.evaluation_run_id,
            worker_id=worker_id,
        )
    except EvaluationRuntimeError as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(
                exc=EvaluationRuntimeError(exc.code, retryable=True),
                countdown=countdown,
            )
        raise
    except Exception:
        _mark_evaluation_run_failed(None, payload.evaluation_run_id, "EVALUATION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.run_fault_simulation", max_retries=3)
def run_fault_simulation(self, event: dict[str, str]) -> str:
    """Execute one claimed reliability exercise for operator evidence."""
    payload = FaultSimulationTaskEvent.model_validate(event)
    try:
        settings = WorkerSettings()
    except Exception:
        _mark_fault_exercise_failed(None, payload.exercise_id, "WORKER_CONFIG_INVALID")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        return build_fault_simulation_service(settings).run(
            payload.exercise_id,
            worker_id=worker_id,
        )
    except Exception:
        _mark_fault_exercise_failed(
            settings, payload.exercise_id, "FAULT_SIMULATION_INTERNAL_ERROR"
        )
        raise
