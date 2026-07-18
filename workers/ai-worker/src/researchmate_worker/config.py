from pathlib import Path
from decimal import Decimal
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
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
    parser_pipeline_version: str = "docling-v1"
    workflow_pipeline_version: str = "evidence-v1"
    workflow_lease_seconds: int = Field(default=900, ge=120, le=1800)
    workflow_call_budget_reservation_usd: Decimal = Field(
        default=Decimal("0.250000"), gt=0, le=5
    )
    workflow_max_prompt_tokens: int = Field(default=32768, ge=1024, le=131072)
    nvidia_input_cost_per_million_usd: Decimal | None = Field(default=None, gt=0)
    nvidia_output_cost_per_million_usd: Decimal | None = Field(default=None, gt=0)
    langgraph_strict_msgpack: bool = True
    parser_max_pages: int = Field(default=300, ge=1, le=1000)
    docling_artifacts_path: Path | None = None
    max_upload_bytes: int = Field(default=26_214_400, ge=1, le=104_857_600)
    r2_account_id: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = None
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
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "researchmate_chunks"
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
    def r2_endpoint_url(self) -> str | None:
        if not self.r2_account_id:
            return None
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def r2_configured(self) -> bool:
        return all(
            (
                self.r2_account_id,
                self.r2_access_key_id,
                self.r2_secret_access_key,
                self.r2_bucket,
            )
        )

    @property
    def uses_generic_object_storage(self) -> bool:
        return any(
            (
                self.object_storage_endpoint_url,
                self.object_storage_access_key_id,
                self.object_storage_secret_access_key,
                self.object_storage_bucket,
            )
        )

    @property
    def object_storage_endpoint_url_resolved(self) -> str | None:
        return self.object_storage_endpoint_url if self.uses_generic_object_storage else self.r2_endpoint_url

    @property
    def object_storage_access_key_id_resolved(self) -> SecretStr | None:
        return self.object_storage_access_key_id if self.uses_generic_object_storage else self.r2_access_key_id

    @property
    def object_storage_secret_access_key_resolved(self) -> SecretStr | None:
        return self.object_storage_secret_access_key if self.uses_generic_object_storage else self.r2_secret_access_key

    @property
    def object_storage_bucket_resolved(self) -> str | None:
        return self.object_storage_bucket if self.uses_generic_object_storage else self.r2_bucket

    @property
    def object_storage_configured(self) -> bool:
        return all(
            (
                self.object_storage_endpoint_url_resolved,
                self.object_storage_access_key_id_resolved,
                self.object_storage_secret_access_key_resolved,
                self.object_storage_bucket_resolved,
            )
        )

    @model_validator(mode="after")
    def validate_remote_runtime(self) -> "WorkerSettings":
        if self.app_env in {"preview", "production"}:
            if not self.database_url:
                raise ValueError("preview and production workers require DATABASE_URL")
            if not self.redis_url:
                raise ValueError("preview and production workers require REDIS_URL")
            if not self.object_storage_configured:
                raise ValueError("preview and production workers require S3-compatible object storage")
            if self.embedding_provider != "nvidia" or self.nvidia_api_key is None:
                raise ValueError("preview and production workers require NVIDIA embeddings")
            if self.llm_provider != "nvidia":
                raise ValueError("preview and production workers require NVIDIA chat")
            if (
                self.nvidia_input_cost_per_million_usd is None
                or self.nvidia_output_cost_per_million_usd is None
            ):
                raise ValueError("preview and production workers require explicit NVIDIA token prices")
            worst_case = (
                Decimal(self.workflow_max_prompt_tokens)
                * self.nvidia_input_cost_per_million_usd
                + Decimal(self.llm_max_tokens)
                * self.nvidia_output_cost_per_million_usd
            ) / Decimal(1_000_000)
            if self.workflow_call_budget_reservation_usd < worst_case:
                raise ValueError(
                    "WORKFLOW_CALL_BUDGET_RESERVATION_USD must cover the configured token ceiling"
                )
            if self.embedding_dimension != 4096:
                raise ValueError("NVIDIA nv-embed-v1 must use 4096 dimensions")
            if not self.qdrant_url or self.qdrant_api_key is None:
                raise ValueError("preview and production workers require Qdrant")
            if self.web_search_provider != "tavily" or self.tavily_api_key is None:
                raise ValueError("preview and production workers require Tavily web search")
            if self.docling_artifacts_path is None:
                raise ValueError("preview and production workers require offline Docling artifacts")
            if not self.langgraph_strict_msgpack:
                raise ValueError("preview and production workers require strict LangGraph serialization")
            if not self.langfuse_enabled or self.langfuse_public_key is None or self.langfuse_secret_key is None:
                raise ValueError("preview and production workers require Langfuse credentials")
        return self
