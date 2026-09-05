"""Validate and expose API runtime configuration at environment boundaries."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from researchmate_api.schemas.common import LIGHTWEIGHT_DOCUMENT_TOKEN_THRESHOLD_DEFAULT


class Settings(BaseSettings):
    """Validated runtime configuration shared by API boundaries and adapters."""

    app_env: Literal["local", "test", "preview", "production"] = "local"
    auth_mode: Literal["development", "supabase"] = "development"
    # Explicit opt-in gate for the hardcoded DEV_USERS bearer tokens in
    # dependencies.py. Defaults to False so that merely flipping AUTH_MODE to
    # "development" in an operator-controlled environment is never sufficient to
    # unlock the static developer credentials; operators must also set
    # ALLOW_DEV_AUTH=true on top of an already-local/test auth_mode stack.
    allow_dev_auth: bool = False
    repository_backend: Literal["memory", "postgres"] = "memory"
    database_url: str | None = None
    redis_url: str | None = None
    runtime_heartbeat_max_age_seconds: int = Field(default=150, ge=30, le=600)
    outbox_pending_max_age_seconds: int = Field(default=180, ge=30, le=1800)
    object_storage_endpoint_url: str | None = None
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_bucket: str | None = None
    object_storage_region: str = "auto"
    llm_provider: Literal["fake", "nvidia"] = "fake"
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "z-ai/glm-5.2"
    llm_temperature: float = Field(default=1.0, ge=0, le=2)
    llm_top_p: float = Field(default=1.0, gt=0, le=1)
    llm_max_tokens: int = Field(default=16_384, ge=1, le=32_768)
    llm_seed: int = 42
    llm_timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    embedding_provider: Literal["fake", "nvidia"] = "fake"
    nvidia_embedding_model: str = "nvidia/nv-embed-v1"
    embedding_dimension: int = Field(default=4096, ge=128, le=8192)
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "researchmate_chunks_v3"
    qdrant_sparse_model: str = "qdrant/bm25"
    qdrant_native_hybrid_enabled: bool = True
    qdrant_rerank_collection: str = "researchmate_chunks_v2"
    qdrant_rerank_model: str | None = None
    qdrant_rerank_model_is_free: bool = False
    qdrant_rerank_dimension: int = Field(default=96, ge=16, le=4096)
    rerank_provider_default: Literal["auto", "qdrant", "nvidia", "deterministic"] = "auto"
    rerank_config_cache_seconds: float = Field(default=5.0, ge=0, le=60)
    rerank_candidate_limit: int = Field(default=50, ge=1, le=100)
    rerank_top_n: int = Field(default=10, ge=1, le=30)
    rerank_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    nvidia_rerank_base_url: str = "https://integrate.api.nvidia.com"
    nvidia_rerank_model: str = "nvidia/llama-nemotron-rerank-1b-v2"
    chat_history_token_budget: int = Field(default=5000, ge=500, le=20000)
    chat_recent_token_budget: int = Field(default=3500, ge=500, le=15000)
    chat_summary_token_budget: int = Field(default=1500, ge=200, le=5000)
    chat_summary_trigger_tokens: int = Field(default=8000, ge=1000, le=50000)
    full_context_token_limit: int = Field(default=12000, ge=1000, le=50000)
    retrieval_evidence_token_budget: int = Field(default=8000, ge=1000, le=30000)
    langgraph_research_enabled: bool = True
    wiki_sufficiency_enabled: bool = True
    wiki_sufficiency_threshold: float = Field(default=0.80, ge=0, le=1)
    wiki_gate_candidate_limit: int = Field(default=5, ge=1, le=12)
    wiki_short_circuit_requires_fresh: bool = True
    adaptive_planner_enabled: bool = True
    adaptive_dense_weight_min: float = Field(default=0.20, ge=0, le=0.5)
    adaptive_dense_weight_max: float = Field(default=0.80, ge=0.5, le=1)
    max_retrieval_rounds: int = Field(default=2, ge=1, le=4)
    retrieval_round_candidate_limit: int = Field(default=30, ge=1, le=100)
    evidence_judge_top_n: int = Field(default=8, ge=1, le=20)
    agentic_web_routing_enabled: bool = True
    lightweight_document_token_threshold: int = Field(
        default=LIGHTWEIGHT_DOCUMENT_TOKEN_THRESHOLD_DEFAULT,
        ge=500,
        le=20000,
        description="Documents at or below this token count skip embedding and Qdrant upsert.",
    )
    ask_max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    web_search_provider: Literal["disabled", "tavily"] = "disabled"
    tavily_api_key: SecretStr | None = None
    tavily_base_url: str = "https://api.tavily.com"
    web_search_timeout_seconds: float = Field(default=30.0, gt=0, le=60)
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    access_token_issuer: str | None = None
    access_token_audience: str = "authenticated"
    supabase_url: str | None = None
    supabase_jwks_url: str | None = None
    request_id_header: str = "X-Request-ID"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    otel_enabled: bool = False
    otel_service_name: str = "researchmate-api"
    otel_exporter_otlp_traces_endpoint: str | None = None
    langfuse_enabled: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    max_upload_bytes: int = Field(default=26_214_400, ge=1, le=104_857_600)
    default_project_ttl_days: int = Field(default=7, ge=1, le=30)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured CORS allowlist as normalized origins."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def jwks_url(self) -> str | None:
        """Resolve the explicit or Supabase-derived JWKS endpoint."""
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def object_storage_configured(self) -> bool:
        """Report whether the object-storage backend is complete."""
        return all(
            (
                self.object_storage_endpoint_url,
                self.object_storage_access_key_id,
                self.object_storage_secret_access_key,
                self.object_storage_bucket,
            )
        )

    @model_validator(mode="after")
    def validate_security_boundary(self) -> Settings:
        """Reject unsafe or incomplete combinations before the API starts."""
        if self.adaptive_dense_weight_min > self.adaptive_dense_weight_max:
            raise ValueError("ADAPTIVE_DENSE_WEIGHT_MIN must not exceed ADAPTIVE_DENSE_WEIGHT_MAX")
        if (
            self.chat_recent_token_budget + self.chat_summary_token_budget
            > self.chat_history_token_budget
        ):
            raise ValueError(
                " ".join(
                    (
                        "CHAT_RECENT_TOKEN_BUDGET plus CHAT_SUMMARY_TOKEN_BUDGET must not exceed",
                        "CHAT_HISTORY_TOKEN_BUDGET",
                    )
                )
            )
        if self.app_env in {"preview", "production"} and self.auth_mode != "supabase":
            raise ValueError("preview and production must use Supabase JWT authentication")
        if self.allow_dev_auth and self.app_env in {"preview", "production"}:
            raise ValueError(
                "ALLOW_DEV_AUTH=true is not permitted in preview or production environments"
            )
        if self.auth_mode == "supabase":
            if not self.access_token_issuer:
                raise ValueError("ACCESS_TOKEN_ISSUER is required for Supabase authentication")
            if not self.jwks_url:
                raise ValueError("SUPABASE_URL or SUPABASE_JWKS_URL is required")
        if self.repository_backend == "postgres" and not self.database_url:
            raise ValueError("DATABASE_URL is required when REPOSITORY_BACKEND=postgres")
        if self.llm_provider == "nvidia" and self.nvidia_api_key is None:
            raise ValueError("NVIDIA_API_KEY is required when LLM_PROVIDER=nvidia")
        if self.web_search_provider == "tavily" and self.tavily_api_key is None:
            raise ValueError("TAVILY_API_KEY is required when WEB_SEARCH_PROVIDER=tavily")
        if self.otel_enabled and not self.otel_exporter_otlp_traces_endpoint:
            raise ValueError(
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is required when OTEL_ENABLED=true"
            )
        if self.langfuse_enabled and (
            self.langfuse_public_key is None or self.langfuse_secret_key is None
        ):
            raise ValueError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required when LANGFUSE_ENABLED=true"
            )
        if self.app_env in {"preview", "production"}:
            if self.repository_backend != "postgres":
                raise ValueError("preview and production must use the PostgreSQL repository")
            if not self.database_url:
                raise ValueError("preview and production require DATABASE_URL")
            if not self.redis_url:
                raise ValueError("preview and production require REDIS_URL")
            if not self.object_storage_configured:
                raise ValueError(
                    "preview and production require complete S3-compatible object storage configuration"
                )
            if self.llm_provider != "nvidia" or self.nvidia_api_key is None:
                raise ValueError(
                    "preview and production require the configured NVIDIA LLM provider"
                )
            if self.embedding_provider != "nvidia" or self.embedding_dimension != 4096:
                raise ValueError(
                    "preview and production require the 4096-dimension NVIDIA embedding provider"
                )
            if not self.qdrant_url or self.qdrant_api_key is None:
                raise ValueError("preview and production require Qdrant Cloud configuration")
            if self.web_search_provider != "tavily" or self.tavily_api_key is None:
                raise ValueError("preview and production require Tavily web search")
            if not self.langfuse_enabled:
                raise ValueError("preview and production require LANGFUSE_ENABLED=true")
        if not self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one explicit origin")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-cached validated settings instance."""
    return Settings()
