from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import create_engine, text

from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.evidence_generation import EvidenceGenerationError
from researchmate_api.services.llm import NvidiaChatProvider, ProviderRequestError
from researchmate_api.services.object_storage import S3CompatibleObjectStorage
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.qdrant_store import VectorStoreRequestError
from researchmate_api.services.web_search import TavilyWebSearchProvider
from researchmate_worker.celery_app import celery_app
from researchmate_worker.budget import BudgetedChatProvider, WorkflowBudgetExceeded
from researchmate_worker.config import WorkerSettings
from researchmate_worker.deletion import (
    DocumentDeletionEvent,
    DocumentDeletionService,
    SqlDeletionStore,
)
from researchmate_worker.ingestion import (
    DocumentIngestionService,
    IngestionEvent,
    IngestionFailure,
    SqlIngestionStore,
)
from researchmate_worker.evidence_graph import build_evidence_graph
from researchmate_worker.evaluation import (
    EvaluationRuntimeError,
    EvaluationRunner,
    QdrantCaseExecutor,
    RagasFaithfulnessScorer,
)
from researchmate_worker.fault_simulation import FaultSimulationService
from researchmate_worker.parsing import DoclingDocumentParser
from researchmate_worker.workflow_runtime import SqlEvidenceWorkflowDomain, WorkflowRuntimeError


class WorkflowTaskEvent(BaseModel):
    run_id: UUID
    user_id: UUID | None = None
    decision_id: UUID | None = None


class EvaluationTaskEvent(BaseModel):
    evaluation_run_id: UUID
    user_id: UUID | None = None


class FaultSimulationTaskEvent(BaseModel):
    exercise_id: UUID
    requested_by: UUID


@lru_cache
def build_ingestion_service() -> DocumentIngestionService:
    settings = WorkerSettings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required to execute ingestion tasks")
    if not settings.object_storage_configured:
        raise RuntimeError("S3-compatible object storage is required to execute ingestion tasks")
    if settings.embedding_provider != "nvidia" or settings.nvidia_api_key is None:
        raise RuntimeError("NVIDIA embeddings are required to execute ingestion tasks")
    if not settings.qdrant_url:
        raise RuntimeError("Qdrant is required to execute ingestion tasks")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    vector_projection = QdrantHybridStore(  # type: ignore[arg-type]
        settings,
        embedding,
    )
    return DocumentIngestionService(
        store=SqlIngestionStore(engine),
        object_reader=S3CompatibleObjectStorage(settings),  # type: ignore[arg-type]
        parser=DoclingDocumentParser(
            max_file_size=settings.max_upload_bytes,
            max_num_pages=settings.parser_max_pages,
            artifacts_path=settings.docling_artifacts_path,
        ),
        vector_projection=vector_projection,
        pipeline_version=settings.parser_pipeline_version,
        lease_seconds=settings.ingestion_lease_seconds,
        max_attempts=settings.ingestion_max_attempts,
        max_upload_bytes=settings.max_upload_bytes,
    )


@lru_cache
def build_deletion_service() -> DocumentDeletionService:
    settings = WorkerSettings()
    if not settings.database_url or not settings.object_storage_configured or not settings.qdrant_url:
        raise RuntimeError("Database, S3-compatible object storage, and Qdrant are required for deletion tasks")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    vector_store = QdrantHybridStore(settings, embedding)  # type: ignore[arg-type]
    return DocumentDeletionService(
        store=SqlDeletionStore(engine),
        object_storage=S3CompatibleObjectStorage(settings),  # type: ignore[arg-type]
        vector_store=vector_store,
        lease_seconds=settings.ingestion_lease_seconds,
        max_attempts=settings.ingestion_max_attempts,
    )


def build_workflow_domain(settings: WorkerSettings) -> SqlEvidenceWorkflowDomain:
    if not settings.database_url or not settings.qdrant_url:
        raise RuntimeError("Database and Qdrant are required for workflow tasks")
    if (
        settings.nvidia_api_key is None
        or settings.embedding_provider != "nvidia"
        or settings.llm_provider != "nvidia"
    ):
        raise RuntimeError("NVIDIA chat and embedding providers are required for workflow tasks")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    provider = BudgetedChatProvider(
        NvidiaChatProvider(settings),  # type: ignore[arg-type]
        engine,
        reservation_usd=settings.workflow_call_budget_reservation_usd,
        input_price_per_million_usd=(
            settings.nvidia_input_cost_per_million_usd or settings.workflow_call_budget_reservation_usd
        ),
        output_price_per_million_usd=(
            settings.nvidia_output_cost_per_million_usd or settings.workflow_call_budget_reservation_usd
        ),
        max_prompt_tokens=settings.workflow_max_prompt_tokens,
    )
    return SqlEvidenceWorkflowDomain(
        engine=engine,
        provider=provider,
        vector_store=QdrantHybridStore(settings, embedding),  # type: ignore[arg-type]
        pipeline_version=settings.workflow_pipeline_version,
        web_search=(
            TavilyWebSearchProvider(settings)  # type: ignore[arg-type]
            if settings.web_search_provider == "tavily"
            else None
        ),
    )


def build_evaluation_runner(settings: WorkerSettings) -> EvaluationRunner:
    if not settings.database_url or not settings.qdrant_url or settings.nvidia_api_key is None:
        raise RuntimeError("Database, Qdrant, and NVIDIA are required for evaluation tasks")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    provider = NvidiaChatProvider(settings)  # type: ignore[arg-type]
    return EvaluationRunner(
        engine=engine,
        executor=QdrantCaseExecutor(
            engine,
            QdrantHybridStore(settings, embedding),  # type: ignore[arg-type]
            provider,
        ),
        faithfulness=RagasFaithfulnessScorer(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key.get_secret_value(),
            model=settings.nvidia_model,
        ),
    )


def build_fault_simulation_service(settings: WorkerSettings) -> FaultSimulationService:
    if not settings.database_url:
        raise RuntimeError("Database is required for reliability simulations")
    return FaultSimulationService(create_engine(settings.database_url, pool_pre_ping=True))


def _mark_workflow_bootstrap_failed(settings: WorkerSettings, run_id: UUID, code: str) -> None:
    if not settings.database_url:
        return
    engine = create_engine(settings.database_url, pool_pre_ping=True)
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


@celery_app.task(bind=True, name="researchmate.ingest_document", max_retries=5)
def ingest_document(self, event: dict[str, str]) -> str:
    """Validate an outbox payload and execute one lease-protected ingestion delivery."""
    payload = IngestionEvent.model_validate(event)
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        return build_ingestion_service().handle(payload, worker_id=worker_id)
    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise


@celery_app.task(bind=True, name="researchmate.delete_document", max_retries=5)
def delete_document(self, event: dict[str, str]) -> str:
    payload = DocumentDeletionEvent.model_validate(event)
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        return build_deletion_service().handle(payload, worker_id=worker_id)
    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise


@celery_app.task(bind=True, name="researchmate.run_workflow", max_retries=5)
def run_workflow(self, event: dict[str, str]) -> str:
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
            config = {"configurable": {"thread_id": str(payload.run_id)}}
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
            raise self.retry(exc=WorkflowRuntimeError(str(exc), retryable=True), countdown=countdown)
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


@celery_app.task(bind=True, name="researchmate.run_fault_simulation", max_retries=3)
def run_fault_simulation(self, event: dict[str, str]) -> str:
    payload = FaultSimulationTaskEvent.model_validate(event)
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    return build_fault_simulation_service(WorkerSettings()).run(
        payload.exercise_id,
        worker_id=worker_id,
    )
