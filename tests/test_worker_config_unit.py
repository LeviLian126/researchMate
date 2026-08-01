"""Verify worker configuration projection and shared provider compatibility."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.llm import NvidiaChatProvider
from researchmate_api.services.object_storage import S3CompatibleObjectStorage
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.web_search import TavilyWebSearchProvider
from researchmate_worker import tasks
from researchmate_worker.config import psycopg_database_url


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        ("postgres://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
        ("postgresql://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
        ("postgresql+psycopg://user:pass@host/db", "postgresql+psycopg://user:pass@host/db"),
    ],
)
def test_worker_database_urls_select_psycopg3(database_url: str, expected: str) -> None:
    """Keep legacy PostgreSQL URLs on the psycopg3 SQLAlchemy dialect."""
    assert psycopg_database_url(database_url) == expected


def test_worker_settings_accept_the_shared_qdrant_rerank_projection_contract() -> None:
    """Expose rerank settings consistently to worker-owned adapters."""
    settings = tasks.WorkerSettings(
        app_env="test",
        qdrant_rerank_collection="project-rerank",
        qdrant_rerank_model="free/model",
        qdrant_rerank_model_is_free=True,
        qdrant_rerank_dimension=96,
    )

    assert settings.qdrant_rerank_collection == "project-rerank"
    assert settings.qdrant_rerank_model == "free/model"
    assert settings.qdrant_rerank_model_is_free is True


def test_worker_settings_construct_every_shared_provider_adapter() -> None:
    """Catch API/worker config drift before a worker task reaches managed state."""
    settings = tasks.WorkerSettings(
        app_env="test",
        embedding_provider="nvidia",
        llm_provider="nvidia",
        nvidia_api_key=SecretStr("fake-nvidia"),
        qdrant_url="https://qdrant.example.test",
        qdrant_api_key=SecretStr("fake-qdrant"),
        web_search_provider="tavily",
        tavily_api_key=SecretStr("fake-tavily"),
        object_storage_endpoint_url="https://objects.example.test",
        object_storage_access_key_id=SecretStr("fake-access"),
        object_storage_secret_access_key=SecretStr("fake-secret"),
        object_storage_bucket="researchmate-test",
    )
    client = SimpleNamespace()
    embedding = NvidiaEmbeddingProvider(settings, client=client)  # type: ignore[arg-type]

    NvidiaChatProvider(settings, client=client)  # type: ignore[arg-type]
    TavilyWebSearchProvider(settings, client=client)  # type: ignore[arg-type]
    S3CompatibleObjectStorage(settings, client=client)  # type: ignore[arg-type]
    QdrantHybridStore(settings, embedding, client=client)  # type: ignore[arg-type]
