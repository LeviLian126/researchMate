"""Validate worker-only environment settings and managed-service requirements."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from researchmate_api.schemas.common import LIGHTWEIGHT_DOCUMENT_TOKEN_THRESHOLD_DEFAULT


def psycopg_database_url(database_url: str) -> str:
    """Force SQLAlchemy to use the installed psycopg v3 driver."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class WorkerSettings(BaseSettings):
    """Validate worker configuration before any managed dependency is constructed."""

    app_env: Literal["local", "test", "preview", "production"] = "local"
    database_url: str | None = None
    redis_url: str | None = None
    ingestion_queue: str = "ingestion"
    worker_soft_time_limit_seconds: int = 840
    worker_time_limit_seconds: int = 900
    outbox_batch_size: int = 50
    outbox_max_attempts: int = 8
    runtime_heartbeat_seconds: int = Field(default=30, ge=10, le=120)
    ingestion_lease_seconds: int = Field(default=1200, ge=60, le=3600)
    ingestion_max_attempts: int = Field(default=5, ge=1, le=10)
    lightweight_document_token_threshold: int = Field(
        default=LIGHTWEIGHT_DOCUMENT_TOKEN_THRESHOLD_DEFAULT,
        ge=500,
        le=20000,
        description="Documents at or below this token count skip embedding and Qdrant upsert.",
    )
    parser_pipeline_version: str = "resource-aware-v4"
    workflow_pipeline_version: str = "evidence-v1"
    workflow_lease_seconds: int = Field(default=900, ge=120, le=1800)
    workflow_call_budget_reservation_usd: Decimal = Field(default=Decimal("0.050000"), gt=0, le=5)
    workflow_max_prompt_tokens: int = Field(default=32768, ge=1024, le=131072)
    langgraph_strict_msgpack: bool = True
    parser_max_pages: int = Field(default=300, ge=1, le=1000)
    pdf_parser_backend: Literal["pdfium", "pypdf", "docling"] = "pdfium"
    docling_artifacts_path: Path | None = None
    max_upload_bytes: int = Field(default=26_214_400, ge=1, le=104_857_600)
    object_storage_endpoint_url: str | None = None
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_bucket: str | None = None
    object_storage_region: str = "auto"
    embedding_provider: Literal["fake", "nvidia"] = "fake"
    llm_provider: Literal["fake", "nvidia"] = "fake"
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "z-ai/glm-5.2"
    llm_temperature: float = Field(default=1.0, ge=0, le=2)
    llm_top_p: float = Field(default=1.0, gt=0, le=1)
    llm_max_tokens: int = Field(default=16_384, ge=1, le=32_768)
    llm_seed: int = 42
    nvidia_embedding_model: str = "nvidia/nv-embed-v1"
    embedding_dimension: int = Field(default=4096, ge=128, le=8192)
    llm_timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    wiki_compilation_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=60,
        description="Bound optional Wiki enrichment so it cannot delay document readiness.",
    )
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "researchmate_chunks_v3"
    qdrant_sparse_model: str = "qdrant/bm25"
    qdrant_native_hybrid_enabled: bool = True
    qdrant_rerank_collection: str = "researchmate_chunks_v2"
    qdrant_rerank_model: str | None = None
    qdrant_rerank_model_is_free: bool = False
    qdrant_rerank_dimension: int = Field(default=96, ge=16, le=4096)
    web_search_provider: Literal["disabled", "tavily"] = "disabled"
    tavily_api_key: SecretStr | None = None
    tavily_base_url: str = "https://api.tavily.com"
    web_search_timeout_seconds: float = Field(default=30.0, gt=0, le=60)
    langfuse_enabled: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def object_storage_configured(self) -> bool:
        return all(
            (
                self.object_storage_endpoint_url,
                self.object_storage_access_key_id,
                self.object_storage_secret_access_key,
                self.object_storage_bucket,
            )
        )

    @model_validator(mode="after")
    def validate_remote_runtime(self) -> WorkerSettings:
        if self.app_env in {"preview", "production"}:
            if not self.database_url:
                raise ValueError("preview and production workers require DATABASE_URL")
            if not self.redis_url:
                raise ValueError("preview and production workers require REDIS_URL")
            if not self.object_storage_configured:
                raise ValueError(
                    "preview and production workers require S3-compatible object storage"
                )
            if self.embedding_provider != "nvidia" or self.nvidia_api_key is None:
                raise ValueError("preview and production workers require NVIDIA embeddings")
            if self.llm_provider != "nvidia":
                raise ValueError("preview and production workers require NVIDIA chat")
            if self.embedding_dimension != 4096:
                raise ValueError("NVIDIA nv-embed-v1 must use 4096 dimensions")
            if not self.qdrant_url or self.qdrant_api_key is None:
                raise ValueError("preview and production workers require Qdrant")
            if self.web_search_provider != "tavily" or self.tavily_api_key is None:
                raise ValueError("preview and production workers require Tavily web search")
            if self.pdf_parser_backend == "docling" and self.docling_artifacts_path is None:
                raise ValueError("preview and production workers require offline Docling artifacts")
            if not self.langgraph_strict_msgpack:
                raise ValueError(
                    "preview and production workers require strict LangGraph serialization"
                )
            if (
                not self.langfuse_enabled
                or self.langfuse_public_key is None
                or self.langfuse_secret_key is None
            ):
                raise ValueError("preview and production workers require Langfuse credentials")
        return self
