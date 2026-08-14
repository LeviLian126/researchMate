"""Validate task events and construct provider-backed worker services at process boundaries."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from uuid import UUID

from pydantic import BaseModel
from researchmate_api.config import Settings
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.llm import NvidiaChatProvider, ProviderConfigurationError
from researchmate_api.services.object_storage import S3CompatibleObjectStorage
from researchmate_api.services.qdrant_store import (
    QdrantHybridStore,
)
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.web_search import TavilyWebSearchProvider
from researchmate_api.services.wiki_compiler import WikiCompiler, wiki_pages_to_chunks
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from researchmate_worker.budget import BudgetedChatProvider
from researchmate_worker.config import WorkerSettings, psycopg_database_url
from researchmate_worker.deletion import (
    DocumentDeletionService,
    ProjectDeletionService,
    SqlDeletionStore,
    SqlProjectDeletionStore,
)
from researchmate_worker.evaluation import (
    EvaluationRunner,
    QdrantCaseExecutor,
    RagasFaithfulnessScorer,
)
from researchmate_worker.fault_simulation import FaultSimulationService
from researchmate_worker.ingestion import (
    DocumentIngestionService,
    SqlIngestionStore,
)
from researchmate_worker.ingestion_models import WikiCompiler as WikiCompilerProtocol
from researchmate_worker.parsing import DoclingDocumentParser
from researchmate_worker.workflow_runtime import (
    SqlEvidenceWorkflowDomain,
)


class WorkerWikiCompiler:
    """Adapt the API WikiCompiler to the worker WikiCompiler protocol.

    The API-level WikiCompiler returns WikiPage objects; the worker protocol
    returns ChunkEntry objects so the ingestion store can persist them via
    the existing replace_content path without schema changes.
    """

    def __init__(self, provider: NvidiaChatProvider) -> None:
        self._compiler = WikiCompiler(provider)

    def compile(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]:
        """Compile chunks into wiki-page chunks via the LLM compiler."""
        pages = self._compiler.compile(
            chunks,
            filename=filename,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )
        return wiki_pages_to_chunks(pages)

    def compile_overview(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]:
        """Compile overview wiki-page chunks for a long document via the LLM compiler."""
        pages = self._compiler.compile_overview(
            chunks,
            filename=filename,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )
        return wiki_pages_to_chunks(pages)


def _worker_engine(database_url: str) -> Engine:
    """Build a worker task engine with a bounded, recycled connection pool.

    INFRA-4: every worker build_* helper opens its own engine. Without an explicit pool
    ceiling, each engine defaults to pool_size=5 + max_overflow=10 against Supabase free
    tier Postgres, which has a tight (~20-60) connection limit. Pinning every engine to
    2+3 keeps the combined worker + dispatcher + heartbeat + API footprint inside the
    ceiling, and pool_recycle=300 matches the API repository engines for health parity.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=2,
        max_overflow=3,
    )


class WorkflowTaskEvent(BaseModel):
    """Validate the durable identifiers accepted by the workflowtask task."""

    run_id: UUID
    user_id: UUID | None = None
    decision_id: UUID | None = None


class EvaluationTaskEvent(BaseModel):
    """Validate the durable identifiers accepted by the evaluationtask task."""

    evaluation_run_id: UUID
    user_id: UUID | None = None


class FaultSimulationTaskEvent(BaseModel):
    """Validate the durable identifiers accepted by the faultsimulationtask task."""

    exercise_id: UUID
    requested_by: UUID


@lru_cache
def build_ingestion_service() -> DocumentIngestionService:
    """Construct the managed adapters required by document ingestion."""
    settings = WorkerSettings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required to execute ingestion tasks")
    if not settings.object_storage_configured:
        raise RuntimeError("S3-compatible object storage is required to execute ingestion tasks")
    if settings.embedding_provider != "nvidia" or settings.nvidia_api_key is None:
        raise RuntimeError("NVIDIA embeddings are required to execute ingestion tasks")
    if not settings.qdrant_url:
        raise RuntimeError("Qdrant is required to execute ingestion tasks")
    api_settings = Settings.model_validate(settings.model_dump())
    engine = _worker_engine(psycopg_database_url(settings.database_url))
    embedding = NvidiaEmbeddingProvider(api_settings)
    vector_projection = QdrantHybridStore(
        api_settings,
        embedding,
    )
    wiki_compiler: WikiCompilerProtocol | None = None
    if settings.llm_provider == "nvidia" and settings.nvidia_api_key is not None:
        try:
            chat_provider = NvidiaChatProvider(api_settings)
            wiki_compiler = WorkerWikiCompiler(chat_provider)
        except ProviderConfigurationError:
            wiki_compiler = None
    return DocumentIngestionService(
        store=SqlIngestionStore(engine),
        # type: ignore[arg-type] — WorkerSettings duck-types Settings fields; pydantic
        # accepts it at runtime but the distinct class trips pyright's strict arg-type.
        object_reader=S3CompatibleObjectStorage(settings),  # type: ignore[arg-type]
        parser=DoclingDocumentParser(
            max_file_size=settings.max_upload_bytes,
            max_num_pages=settings.parser_max_pages,
            artifacts_path=settings.docling_artifacts_path,
            pdf_backend=settings.pdf_parser_backend,
        ),
        vector_projection=vector_projection,
        pipeline_version=(f"{settings.parser_pipeline_version}-{settings.pdf_parser_backend}"),
        lease_seconds=settings.ingestion_lease_seconds,
        max_attempts=settings.ingestion_max_attempts,
        max_upload_bytes=settings.max_upload_bytes,
        lightweight_token_threshold=settings.lightweight_document_token_threshold,
        wiki_compiler=wiki_compiler,
    )


@lru_cache
def build_deletion_service() -> DocumentDeletionService:
    """Construct adapters for recoverable single-document deletion."""
    settings = WorkerSettings()
    if (
        not settings.database_url
        or not settings.object_storage_configured
        or not settings.qdrant_url
    ):
        raise RuntimeError(
            "Database, S3-compatible object storage, and Qdrant are required for deletion tasks"
        )
    engine = _worker_engine(psycopg_database_url(settings.database_url))
    # type: ignore[arg-type] — WorkerSettings duck-types Settings fields; pyright sees the distinct class.
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    vector_store = QdrantHybridStore(settings, embedding)  # type: ignore[arg-type]
    return DocumentDeletionService(
        store=SqlDeletionStore(engine),
        object_storage=S3CompatibleObjectStorage(settings),  # type: ignore[arg-type]
        vector_store=vector_store,
        lease_seconds=settings.ingestion_lease_seconds,
        max_attempts=settings.ingestion_max_attempts,
    )


@lru_cache
def build_project_deletion_service() -> ProjectDeletionService:
    """Construct adapters for recoverable project-wide deletion."""
    settings = WorkerSettings()
    if (
        not settings.database_url
        or not settings.object_storage_configured
        or not settings.qdrant_url
    ):
        raise RuntimeError(
            "Database, S3-compatible object storage, and Qdrant are required for deletion tasks"
        )
    engine = _worker_engine(psycopg_database_url(settings.database_url))
    # type: ignore[arg-type] — WorkerSettings duck-types Settings fields; pyright sees the distinct class.
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    vector_store = QdrantHybridStore(settings, embedding)  # type: ignore[arg-type]
    return ProjectDeletionService(
        store=SqlProjectDeletionStore(engine),
        object_storage=S3CompatibleObjectStorage(settings),  # type: ignore[arg-type]
        vector_store=vector_store,
        lease_seconds=settings.ingestion_lease_seconds,
        max_attempts=settings.ingestion_max_attempts,
    )


def build_workflow_domain(settings: WorkerSettings) -> SqlEvidenceWorkflowDomain:
    """Construct the evidence workflow domain with budgeted providers."""
    if not settings.database_url or not settings.qdrant_url:
        raise RuntimeError("Database and Qdrant are required for workflow tasks")
    if (
        settings.nvidia_api_key is None
        or settings.embedding_provider != "nvidia"
        or settings.llm_provider != "nvidia"
    ):
        raise RuntimeError("NVIDIA chat and embedding providers are required for workflow tasks")
    engine = _worker_engine(psycopg_database_url(settings.database_url))
    # type: ignore[arg-type] — WorkerSettings duck-types Settings fields; pyright sees the distinct class.
    embedding = NvidiaEmbeddingProvider(settings)  # type: ignore[arg-type]
    provider = BudgetedChatProvider(
        NvidiaChatProvider(settings),  # type: ignore[arg-type]
        engine,
        reservation_usd=settings.workflow_call_budget_reservation_usd,
        input_price_per_million_usd=Decimal(0),
        output_price_per_million_usd=Decimal(0),
        max_prompt_tokens=settings.workflow_max_prompt_tokens,
    )
    return SqlEvidenceWorkflowDomain(
        engine=engine,
        provider=provider,
        # type: ignore[arg-type] — WorkerSettings duck-types Settings; pydantic accepts it at runtime.
        vector_store=QdrantHybridStore(settings, embedding),  # type: ignore[arg-type]
        pipeline_version=settings.workflow_pipeline_version,
        web_search=(
            TavilyWebSearchProvider(settings)  # type: ignore[arg-type]
            if settings.web_search_provider == "tavily"
            else None
        ),
    )


def build_evaluation_runner(settings: WorkerSettings) -> EvaluationRunner:
    """Construct the evaluation runner and its optional judge boundary."""
    if not settings.database_url or not settings.qdrant_url or settings.nvidia_api_key is None:
        raise RuntimeError("Database, Qdrant, and NVIDIA are required for evaluation tasks")
    engine = _worker_engine(psycopg_database_url(settings.database_url))
    # type: ignore[arg-type] — WorkerSettings duck-types Settings fields; pyright sees the distinct class.
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
    """Construct the database-backed reliability exercise service."""
    if not settings.database_url:
        raise RuntimeError("Database is required for reliability simulations")
    return FaultSimulationService(_worker_engine(psycopg_database_url(settings.database_url)))
