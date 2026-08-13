"""Verify PostgreSQL repository ownership, transaction, and delivery contracts."""

from __future__ import annotations

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
from researchmate_api.services.object_storage import (
    StoredObjectMetadata,
    UploadVerificationError,
)


class EmptyResult:
    """Return no rows from isolated repository queries."""

    def mappings(self) -> EmptyResult:
        return self

    def one_or_none(self) -> None:
        return None


class RecordingConnection:
    """Record SQL statements issued by repository operations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement: Any, parameters: dict[str, Any]) -> EmptyResult:
        self.calls.append((str(statement), parameters))
        return EmptyResult()


class ConnectionContext(AbstractContextManager[RecordingConnection]):
    """Provide a recording connection through a context manager."""

    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    def __enter__(self) -> RecordingConnection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        return None


class RecordingEngine:
    """Expose recording transaction and connection contexts."""

    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def begin(self) -> ConnectionContext:
        return ConnectionContext(self.connection)


def test_postgres_urls_select_the_installed_psycopg3_driver() -> None:
    """Normalize PostgreSQL URLs to the installed psycopg3 driver."""
    assert _psycopg_url("postgres://user:pass@host/db").startswith("postgresql+psycopg://")
    assert _psycopg_url("postgresql://user:pass@host/db").startswith("postgresql+psycopg://")


def test_preview_requires_postgres_and_database_url() -> None:
    """Require PostgreSQL and its URL in preview configuration."""
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
        "object_storage_endpoint_url": "https://example.test",
        "object_storage_access_key_id": SecretStr("access"),
        "object_storage_secret_access_key": SecretStr("secret"),
        "object_storage_bucket": "bucket",
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
    """Set RLS subject state and an explicit owner predicate for lookups."""
    engine = RecordingEngine()
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]
    user = CurrentUser(id=UUID("00000000-0000-4000-8000-000000000042"))

    assert repository.get_project(user, UUID("10000000-0000-4000-8000-000000000042")) is None

    assert "set_config('request.jwt.claim.sub'" in engine.connection.calls[0][0]
    resource_sql, resource_params = engine.connection.calls[1]
    assert "user_id = :user_id" in resource_sql
    assert resource_params["user_id"] == user.id


def test_upload_factory_receives_validated_content_metadata() -> None:
    """Pass validated upload metadata into the object-storage signer."""
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

    assert (
        repository.upload_url_factory(
            UUID("20000000-0000-4000-8000-000000000042"), "object-key", payload
        )
        == "https://upload.example.test/signed"
    )
    assert captured["payload"].mime_type == "application/pdf"


class OneMappingResult:
    """Return one configured mapping from a repository query."""

    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def mappings(self) -> OneMappingResult:
        return self

    def one_or_none(self) -> dict[str, Any]:
        return self.value


class ReservationConnection(RecordingConnection):
    """Return deterministic upload-reservation records while recording SQL."""

    def execute(self, statement: Any, parameters: dict[str, Any]) -> EmptyResult | OneMappingResult:
        self.calls.append((str(statement), parameters))
        if "r2_object_key" in str(statement) and "join projects" in str(statement):
            return OneMappingResult(
                {
                    "r2_object_key": "users/u/document.pdf",
                    "size_bytes": 100,
                    "mime_type": "application/pdf",
                }
            )
        return EmptyResult()


class ReservationEngine(RecordingEngine):
    """Provide reservation-aware repository connections."""

    def __init__(self) -> None:
        self.connection = ReservationConnection()


def test_completion_verifies_reserved_object_before_accepting_work() -> None:
    """Verify reserved object metadata before accepting ingestion work."""
    repository = PostgresResearchMateRepository(
        ReservationEngine(),  # type: ignore[arg-type]
        object_metadata_reader=lambda _key, **_kwargs: StoredObjectMetadata(
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


def test_completion_passes_declared_mime_type_to_metadata_reader() -> None:
    """Forward the reserved MIME type so the reader can perform server-side content checks."""
    captured: dict[str, object] = {}

    def reader(_key, *, declared_mime_type=None):
        captured["declared_mime_type"] = declared_mime_type
        # Match the reservation size so the size-mismatch branch is skipped; the next
        # branch (content-type mismatch) is also satisfied by reusing the same value.
        return StoredObjectMetadata(
            size_bytes=100,
            content_type=declared_mime_type,
            etag=None,
            metadata={},
        )

    repository = PostgresResearchMateRepository(
        ReservationEngine(),  # type: ignore[arg-type]
        object_metadata_reader=reader,
    )
    user = CurrentUser(id=UUID("00000000-0000-4000-8000-000000000042"))

    repository.complete_document(
        user,
        UUID("10000000-0000-4000-8000-000000000042"),
        None,
        "a" * 64,
    )

    assert captured["declared_mime_type"] == "application/pdf"


def test_completion_persists_job_and_outbox_intent_in_one_method() -> None:
    """Persist job and outbox delivery intent through one repository method."""
    source = getsource(PostgresResearchMateRepository.complete_document).lower()

    assert "set status = 'parsing'" in source
    assert "jobstatus.pending" in source
    assert "_enqueue_document_event" in source
    assert (
        "on conflict (idempotency_key) do nothing"
        in getsource(PostgresResearchMateRepository._enqueue_document_event).lower()
    )
    assert "insert into chunks" not in source


def test_async_repository_contract_uses_real_job_types_and_unique_deliveries() -> None:
    """Use supported job types and unique delivery keys for async work."""
    project_delete = getsource(PostgresResearchMateRepository.delete_project).lower()
    complete = getsource(PostgresResearchMateRepository.complete_document).lower()
    document_delete = getsource(PostgresResearchMateRepository.delete_document).lower()
    enqueue = getsource(PostgresResearchMateRepository._enqueue_document_event).lower()

    assert "type = 'parse_and_index_document'" in project_delete
    assert "type = 'ingest_document'" not in project_delete
    assert "lease_expires_at <= now()" in project_delete
    assert "lease_owner = null" in project_delete
    assert "_enqueue_project_deletion" in project_delete
    assert "_enqueue_document_event" in complete
    assert "_enqueue_document_event" in document_delete
    assert "job_id" in enqueue
    assert "delivery_id" in enqueue
    assert "interval '30 seconds'" in enqueue
    assert ") < 5" in enqueue


def test_document_mutations_require_an_active_parent_project() -> None:
    """Reject document mutations when the parent project is inactive."""
    create = getsource(PostgresResearchMateRepository.create_document).lower()
    complete = getsource(PostgresResearchMateRepository.complete_document).lower()
    delete = getsource(PostgresResearchMateRepository.delete_document).lower()

    assert "p.status = 'active'" in create
    assert complete.count("p.status = 'active'") >= 2
    assert "p.status = 'active'" in delete


def test_project_scoped_writes_lock_the_active_project_transition() -> None:
    """Serialize child writes with project deletion instead of trusting a stale snapshot."""
    for method in (
        PostgresResearchMateRepository.create_upload_url,
        PostgresResearchMateRepository.complete_document,
        PostgresResearchMateRepository.record_run,
        PostgresResearchMateRepository.save_quiz_set,
        PostgresResearchMateRepository.ensure_conversation,
    ):
        assert "_lock_active_project" in getsource(method)
    lock = getsource(PostgresResearchMateRepository._lock_active_project).lower()
    assert "status = 'active'" in lock
    assert "for update" in lock


def test_active_project_lock_keeps_static_helper_call_contract() -> None:
    """Call the split lock helper through the repository without binding an extra self."""
    repository = object.__new__(PostgresResearchMateRepository)
    connection = RecordingConnection()
    user_id = UUID("00000000-0000-4000-8000-000000000001")
    project_id = UUID("00000000-0000-4000-8000-000000000002")

    assert repository._lock_active_project(connection, user_id, project_id) is False
    assert connection.calls[0][1] == {"project_id": project_id, "user_id": user_id}
