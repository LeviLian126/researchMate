from contextlib import AbstractContextManager
from inspect import getsource
from typing import Any
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from researchmate_api.config import Settings

pytest.importorskip("sqlalchemy", reason="PostgreSQL adapter dependencies are not installed")

from researchmate_api.persistence.postgres import (
    PostgresResearchMateRepository,
    _psycopg_url,
)
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import UploadUrlRequest
from researchmate_api.services.object_storage import StoredObjectMetadata, UploadVerificationError


class EmptyResult:
    def mappings(self) -> "EmptyResult":
        return self

    def one_or_none(self) -> None:
        return None


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement: Any, parameters: dict[str, Any]) -> EmptyResult:
        self.calls.append((str(statement), parameters))
        return EmptyResult()


class ConnectionContext(AbstractContextManager[RecordingConnection]):
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    def __enter__(self) -> RecordingConnection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        return None


class RecordingEngine:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def begin(self) -> ConnectionContext:
        return ConnectionContext(self.connection)


def test_postgres_urls_select_the_installed_psycopg3_driver() -> None:
    assert _psycopg_url("postgres://user:pass@host/db").startswith("postgresql+psycopg://")
    assert _psycopg_url("postgresql://user:pass@host/db").startswith("postgresql+psycopg://")


def test_preview_requires_postgres_and_database_url() -> None:
    auth = {
        "app_env": "preview",
        "auth_mode": "supabase",
        "access_token_issuer": "https://example.test/auth/v1",
        "supabase_url": "https://example.test",
        "llm_provider": "nvidia",
        "nvidia_api_key": SecretStr("fake-key"),
        "embedding_provider": "nvidia",
        "embedding_dimension": 4096,
        "qdrant_url": "https://qdrant.example.test",
        "qdrant_api_key": SecretStr("fake-key"),
        "web_search_provider": "tavily",
        "tavily_api_key": SecretStr("fake-key"),
        "langfuse_enabled": True,
        "langfuse_public_key": SecretStr("fake-key"),
        "langfuse_secret_key": SecretStr("fake-key"),
        "r2_account_id": "account",
        "r2_access_key_id": SecretStr("access"),
        "r2_secret_access_key": SecretStr("secret"),
        "r2_bucket": "bucket",
        "redis_url": "rediss://example.test:6379",
    }
    with pytest.raises(ValidationError):
        Settings(**auth, repository_backend="memory")
    with pytest.raises(ValidationError):
        Settings(**auth, repository_backend="postgres")

    settings = Settings(
        **auth,
        repository_backend="postgres",
        database_url="postgresql://user:pass@host/db",
    )
    assert settings.repository_backend == "postgres"


def test_resource_lookup_sets_rls_subject_and_owner_predicate_without_a_database() -> None:
    engine = RecordingEngine()
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]
    user = CurrentUser(id=UUID("00000000-0000-4000-8000-000000000042"))

    assert repository.get_project(user, UUID("10000000-0000-4000-8000-000000000042")) is None

    assert "set_config('request.jwt.claim.sub'" in engine.connection.calls[0][0]
    resource_sql, resource_params = engine.connection.calls[1]
    assert "user_id = :user_id" in resource_sql
    assert resource_params["user_id"] == user.id


def test_upload_factory_receives_validated_content_metadata() -> None:
    captured = {}

    def signer(document_id, object_key, payload):
        captured.update(document_id=document_id, object_key=object_key, payload=payload)
        return "https://upload.example.test/signed"

    repository = PostgresResearchMateRepository(RecordingEngine(), upload_url_factory=signer)  # type: ignore[arg-type]
    payload = UploadUrlRequest(
        project_id=UUID("10000000-0000-4000-8000-000000000042"),
        filename="paper.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        size_bytes=100,
    )

    assert repository.upload_url_factory(
        UUID("20000000-0000-4000-8000-000000000042"), "object-key", payload
    ) == "https://upload.example.test/signed"
    assert captured["payload"].mime_type == "application/pdf"


class OneMappingResult:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def mappings(self) -> "OneMappingResult":
        return self

    def one_or_none(self) -> dict[str, Any]:
        return self.value


class ReservationConnection(RecordingConnection):
    def execute(self, statement: Any, parameters: dict[str, Any]):
        self.calls.append((str(statement), parameters))
        if "select r2_object_key" in str(statement):
            return OneMappingResult(
                {
                    "r2_object_key": "users/u/document.pdf",
                    "size_bytes": 100,
                    "mime_type": "application/pdf",
                }
            )
        return EmptyResult()


class ReservationEngine(RecordingEngine):
    def __init__(self) -> None:
        self.connection = ReservationConnection()


def test_completion_verifies_reserved_object_before_accepting_work() -> None:
    repository = PostgresResearchMateRepository(
        ReservationEngine(),  # type: ignore[arg-type]
        object_metadata_reader=lambda _key: StoredObjectMetadata(
            size_bytes=99,
            content_type="application/pdf",
            etag=None,
            metadata={},
        ),
    )
    user = CurrentUser(id=UUID("00000000-0000-4000-8000-000000000042"))

    with pytest.raises(UploadVerificationError) as raised:
        repository.complete_document(
            user,
            UUID("10000000-0000-4000-8000-000000000042"),
            None,
            "a" * 64,
        )

    assert raised.value.code == "UPLOAD_SIZE_MISMATCH"


def test_completion_persists_job_and_outbox_intent_in_one_method() -> None:
    source = getsource(PostgresResearchMateRepository.complete_document).lower()

    assert "set status = 'parsing'" in source
    assert "jobstatus.pending" in source
    assert "insert into outbox_events" in source
    assert "on conflict (idempotency_key) do nothing" in source
    assert "insert into chunks" not in source
