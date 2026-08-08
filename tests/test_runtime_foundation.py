"""Verify authentication, configuration, request, and readiness foundations."""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from researchmate_api.config import Settings
from researchmate_api.main import create_app
from researchmate_api.routers.health import healthz, readyz
from researchmate_api.services.store import store


def test_production_rejects_development_auth() -> None:
    """Reject development authentication in production settings."""
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_mode="development")


def test_enabled_observability_and_web_providers_require_credentials() -> None:
    """Require credentials whenever optional managed providers are enabled."""
    with pytest.raises(ValidationError):
        Settings(app_env="test", otel_enabled=True)
    with pytest.raises(ValidationError):
        Settings(app_env="test", langfuse_enabled=True)
    with pytest.raises(ValidationError):
        Settings(app_env="test", web_search_provider="tavily")


def test_configured_cors_and_request_id_are_applied() -> None:
    """Apply the configured CORS allowlist and request identifier."""
    settings = Settings(
        app_env="local",
        auth_mode="development",
        cors_allowed_origins="https://preview.example.test, https://portfolio.example.test",
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.get(
            "/api/v1/healthz",
            headers={"Origin": "https://preview.example.test", "X-Request-ID": "req_client_1234"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://preview.example.test"
    assert response.headers["x-request-id"] == "req_client_1234"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_liveness_probe_does_not_depend_on_the_sync_thread_pool() -> None:
    """Keep liveness independent of the shared synchronous thread pool."""
    assert inspect.iscoroutinefunction(healthz)


def test_local_readiness_is_explicit_and_non_charging() -> None:
    """Report local readiness without charging managed providers."""
    with TestClient(
        create_app(
            settings=Settings(app_env="test", llm_provider="fake", embedding_provider="fake")
        )
    ) as client:
        response = client.get("/api/v1/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "environment": "test",
        "components": {
            "database": "not_required",
            "redis": "not_required",
            "worker": "not_required",
            "dispatcher": "not_required",
            "outbox": "not_required",
            "checkpoint": "not_required",
            "qdrant": "not_required",
            "object_storage": "not_required",
            "llm": "not_required",
            "web_search": "not_required",
        },
        "failed_components": [],
    }


def test_managed_readiness_requires_live_background_delivery(monkeypatch) -> None:
    """Require fresh worker and dispatcher delivery signals when managed."""

    class Result:
        def __init__(self, kind: str) -> None:
            self.kind = kind

        def scalar_one(self) -> Any:
            # boundary: scalar value from opaque SQL result.
            return 4

        def mappings(self) -> Result:
            return self

        def all(self) -> list[Any]:
            return [
                {"component": "worker", "status": "ready", "fresh": True},
                {"component": "dispatcher", "status": "ready", "fresh": True},
            ]

        def one(self) -> object:
            return {"stale_count": 0, "exhausted_count": 0}

    class Connection:
        def execute(self, statement: Any, _parameters: dict[str, Any] | None = None) -> Result:
            # boundary: opaque test double for SQLAlchemy statements/parameters.
            source = str(statement)
            if "checkpoint_migrations" in source:
                return Result("checkpoint")
            if "runtime_heartbeats" in source:
                return Result("heartbeats")
            if "outbox_events" in source:
                return Result("outbox")
            return Result("ping")

    class Engine:
        @contextmanager
        def connect(self) -> Iterator[Connection]:
            yield Connection()

    class RedisClient:
        def ping(self) -> bool:
            return True

        def close(self) -> None:
            return None

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_args, **_kwargs: RedisClient())
    settings = SimpleNamespace(
        repository_backend="postgres",
        redis_url="rediss://example.test:6379",
        runtime_heartbeat_max_age_seconds=150,
        outbox_pending_max_age_seconds=180,
        qdrant_url="https://qdrant.example.test",
        object_storage_configured=True,
        app_env="preview",
    )
    hybrid_store = SimpleNamespace(
        client=SimpleNamespace(get_collection=lambda _name: object()),
        collection="chunks",
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=settings,
                store=SimpleNamespace(engine=Engine()),
                hybrid_store=hybrid_store,
                chat_provider=object(),
                web_search=object(),
            )
        )
    )

    response = readyz(request)  # type: ignore[arg-type]
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert payload["components"]["worker"] == "ready"
    assert payload["components"]["dispatcher"] == "ready"
    assert payload["components"]["outbox"] == "ready"
    assert payload["components"]["checkpoint"] == "ready"


def test_unknown_bearer_token_fails_closed_and_uses_request_id() -> None:
    """Reject unknown bearer tokens with the request correlation identifier."""
    settings = Settings(app_env="local", auth_mode="development")

    with TestClient(create_app(settings=settings)) as client:
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer arbitrary-token", "X-Request-ID": "req_auth_1234"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "INVALID_TOKEN",
        "message": "The bearer token is not valid for the configured authentication mode.",
        "request_id": "req_auth_1234",
    }


def test_explicit_development_identity_remains_available_locally() -> None:
    """Keep the explicit local development identity available."""
    settings = Settings(app_env="local", auth_mode="development", allow_dev_auth=True)
    user_id = UUID("00000000-0000-4000-8000-000000000042")

    try:
        with TestClient(create_app(settings=settings)) as client:
            response = client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer dev:{user_id}:user:student@example.test"},
            )
        assert response.status_code == 200
        assert response.json()["id"] == str(user_id)
    finally:
        store.reset()


def test_dev_auth_rejected_when_allow_dev_auth_disabled() -> None:
    """Reject the hardcoded development tokens when ALLOW_DEV_AUTH is not set."""
    settings = Settings(app_env="local", auth_mode="development")
    user_id = UUID("00000000-0000-4000-8000-000000000042")

    try:
        with TestClient(create_app(settings=settings)) as client:
            static_response = client.get(
                "/api/v1/me",
                headers={"Authorization": "Bearer dev-user-a"},
            )
            envelope_response = client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer dev:{user_id}:user:student@example.test"},
            )
        # Both the static DEV_USERS credentials and the dev:<uuid> envelope must be
        # treated as invalid tokens when allow_dev_auth is False, even though
        # AUTH_MODE=development is set. This is the SEC-1 gate: a missing env var
        # is sufficient to deny the static developer identities at the boundary.
        assert static_response.status_code == 401
        assert static_response.json()["error"]["code"] == "INVALID_TOKEN"
        assert envelope_response.status_code == 401
        assert envelope_response.json()["error"]["code"] == "INVALID_TOKEN"
    finally:
        store.reset()


def test_allow_dev_auth_forbidden_in_protected_environments() -> None:
    """Refuse ALLOW_DEV_AUTH=true in preview or production environments."""
    with pytest.raises(ValidationError):
        Settings(app_env="preview", auth_mode="supabase", allow_dev_auth=True)
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_mode="supabase", allow_dev_auth=True)
