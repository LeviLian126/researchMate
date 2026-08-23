"""Verify PostgreSQL repository ownership, transaction, and delivery contracts."""

from __future__ import annotations

from contextlib import AbstractContextManager
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

    def scalars(self) -> EmptyResult:
        return self

    def all(self) -> list:  # noqa: D401 - mirrors SQLAlchemy API
        return []

    def scalar_one(self) -> None:
        return None

    def scalar_one_or_none(self) -> None:
        return None

    def __iter__(self) -> Any:
        return iter([])


class OneMappingResult:
    """Return one configured mapping from a repository query."""

    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def mappings(self) -> OneMappingResult:
        return self

    def one_or_none(self) -> dict[str, Any]:
        return self.value

    def one(self) -> dict[str, Any]:
        return self.value

    def __iter__(self) -> Any:
        return iter([self.value] if self.value is not None else [])


class RecordingConnection:
    """Record SQL statements issued by repository operations.

    Subclasses override ``route`` to return deterministic results based on SQL
    markers so each persistence flow can be exercised without a database.
    """

    def __init__(self, *, result: Any = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._default_result = result or EmptyResult()

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        """Override to return a different result per SQL statement."""
        return self._default_result

    def execute(self, statement: Any, parameters: dict[str, Any] | None = None) -> Any:
        self.calls.append((str(statement), parameters or {}))
        return self.route(str(statement), parameters or {})


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

    def __init__(self, connection: RecordingConnection | None = None) -> None:
        self.connection = connection or RecordingConnection()

    def begin(self) -> ConnectionContext:
        return ConnectionContext(self.connection)


USER_ID = UUID("00000000-0000-4000-8000-000000000042")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000142")
DOCUMENT_ID = UUID("20000000-0000-4000-8000-000000000249")


def user() -> CurrentUser:
    """Provide a stable authenticated caller."""
    return CurrentUser(id=USER_ID, email="owner@example.test", role="user")


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

    assert repository.get_project(user(), PROJECT_ID) is None

    assert "set_config('request.jwt.claim.sub'" in engine.connection.calls[0][0]
    resource_sql, resource_params = engine.connection.calls[1]
    assert "user_id = :user_id" in resource_sql
    assert resource_params["user_id"] == USER_ID


def test_upload_factory_receives_validated_content_metadata() -> None:
    """Pass validated upload metadata into the object-storage signer."""
    captured = {}

    def signer(document_id, object_key, payload):
        captured.update(document_id=document_id, object_key=object_key, payload=payload)
        return "https://upload.example.test/signed"

    repository = PostgresResearchMateRepository(RecordingEngine(), upload_url_factory=signer)  # type: ignore[arg-type]
    payload = UploadUrlRequest(
        project_id=PROJECT_ID,
        filename="paper.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        size_bytes=100,
    )

    assert (
        repository.upload_url_factory(
            UUID("30000000-0000-4000-8000-000000000042"), "object-key", payload
        )
        == "https://upload.example.test/signed"
    )
    assert captured["payload"].mime_type == "application/pdf"


# ---------------------------------------------------------------------------
# Reservation lookup + object verification
# ---------------------------------------------------------------------------


class ReservationConnection(RecordingConnection):
    """Return deterministic upload-reservation records while recording SQL."""

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        if "r2_object_key" in statement and "join projects" in statement:
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
        super().__init__(ReservationConnection())


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

    with pytest.raises(UploadVerificationError) as raised:
        repository.complete_document(user(), DOCUMENT_ID, None, "a" * 64)

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

    repository.complete_document(user(), DOCUMENT_ID, None, "a" * 64)

    assert captured["declared_mime_type"] == "application/pdf"


# ---------------------------------------------------------------------------
# complete_document: job + outbox persistence contract
# ---------------------------------------------------------------------------


class CompleteDocumentConnection(RecordingConnection):
    """Drive complete_document through its happy path while recording SQL.

    Transaction 1 (reservation lookup) returns a reserved object row.
    Transaction 2 (state transition) returns the document owner row,
    the active-project lock marker, the UPDATE...RETURNING row, and the
    job INSERT row so complete_document persists a job and outbox event.
    """

    R2_OBJECT_KEY = "users/u/document.pdf"

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        # Transaction 1: the reservation lookup joins projects and selects r2_object_key.
        if "r2_object_key" in statement and "join projects" in statement:
            return OneMappingResult(
                {
                    "r2_object_key": self.R2_OBJECT_KEY,
                    "size_bytes": 100,
                    "mime_type": "application/pdf",
                }
            )
        if "set_config" in statement:
            return EmptyResult()
        # Transaction 2 step 1: document ownership check returns project_id.
        if "select project_id from documents" in statement:
            return OneMappingResult({"project_id": PROJECT_ID})
        # Transaction 2 step 2: active-project lock returns a marker row.
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        # Transaction 2 step 3: UPDATE documents...RETURNING returns project_id + r2_object_key.
        if "update documents" in statement and "returning" in statement:
            return OneMappingResult({"project_id": PROJECT_ID, "r2_object_key": self.R2_OBJECT_KEY})
        # Transaction 2 step 4: job INSERT...RETURNING returns the full job row.
        if "insert into jobs" in statement:
            return OneMappingResult(
                {
                    "id": UUID("40000000-0000-4000-8000-000000000042"),
                    "user_id": USER_ID,
                    "project_id": PROJECT_ID,
                    "document_id": DOCUMENT_ID,
                    "type": "parse_and_index_document",
                    "status": "pending",
                    "progress": 0,
                    "error_message": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        # Transaction 2 step 5: outbox INSERT is fire-and-forget.
        return EmptyResult()


def test_completion_persists_job_and_outbox_intent_in_one_method() -> None:
    """Persist job and outbox delivery intent through one repository method.

    Drives complete_document through the happy path via a RecordingConnection
    and asserts the captured SQL contains the parsing-status UPDATE, the job
    INSERT with status='pending', and the outbox INSERT with deduplication guard.
    No chunk inserts should occur during document completion.
    """
    engine = RecordingEngine(CompleteDocumentConnection())
    repository = PostgresResearchMateRepository(
        engine,  # type: ignore[arg-type]
        object_metadata_reader=lambda _key, **_kwargs: StoredObjectMetadata(
            size_bytes=100,
            content_type="application/pdf",
            etag=None,
            metadata={},
        ),
    )

    job = repository.complete_document(user(), DOCUMENT_ID, None, "a" * 64)

    assert job is not None, "complete_document must return a job on the happy path"
    assert job.type == "parse_and_index_document"
    assert job.status == "pending"

    calls = engine.connection.calls
    sql_text = " ".join(call[0].lower() for call in calls)

    # The UPDATE that flips the document to 'parsing' must be captured.
    assert "set status = 'parsing'" in sql_text, (
        "complete_document must issue the parsing-status UPDATE"
    )
    assert "insert into jobs" in sql_text, "complete_document must insert a parse job"
    assert "insert into outbox_events" in sql_text, (
        "complete_document must enqueue the document event"
    )
    assert "on conflict (idempotency_key) do nothing" in sql_text, (
        "document event enqueue must guard deduplication"
    )
    assert "insert into chunks" not in sql_text, "complete_document must not persist chunks"


# ---------------------------------------------------------------------------
# delete_project: active-project serialization + outbox contract
# ---------------------------------------------------------------------------


class _EmptyScalarsResult:
    """Return an empty scalar list for object/qdrant scans."""

    def scalars(self) -> _EmptyScalarsResult:
        return self

    def all(self) -> list:
        return []


class ProjectDeleteConnection(RecordingConnection):
    """Drive delete_project through the active-branch happy path.

    Returns a workspace (non-personal) project from the FOR UPDATE lock,
    empty result sets for object/qdrant scans, and the job INSERT row.
    """

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        if "set_config" in statement:
            return EmptyResult()
        # delete_project lock + select: returns a workspace project row.
        if "for update" in statement and "status" in statement and "kind" in statement:
            return OneMappingResult({"status": "active", "kind": "workspace"})
        # Fail in-flight parse jobs.
        if "update jobs" in statement and "project_deleting" in statement.lower():
            return EmptyResult()
        # Object/qdrant scans return empty scalars.
        if "r2_object_key" in statement and "select" in statement.lower():
            return _EmptyScalarsResult()
        if "qdrant_point_id" in statement and "select" in statement.lower():
            return _EmptyScalarsResult()
        # Project status UPDATE (active -> deleting).
        if "update projects" in statement and "status = 'deleting'" in statement.lower():
            return EmptyResult()
        # Job INSERT...RETURNING: returns the full job row.
        if "insert into jobs" in statement:
            return OneMappingResult(
                {
                    "id": UUID("50000000-0000-4000-8000-000000000142"),
                    "user_id": USER_ID,
                    "project_id": PROJECT_ID,
                    "document_id": None,
                    "type": "delete_project",
                    "status": "pending",
                    "progress": 0,
                    "error_message": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        return EmptyResult()


def test_async_repository_contract_uses_real_job_types_and_unique_deliveries() -> None:
    """Use supported job types and unique delivery keys for async work.

    Drives delete_project through its happy path via a RecordingConnection and
    asserts the captured SQL cancels in-flight parse_and_index_document jobs,
    reaps expired leases, clears lease owners, and enqueues a project-deletion
    outbox event with the deduplication idempotency guard.
    """
    engine = RecordingEngine(ProjectDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    job = repository.delete_project(user(), PROJECT_ID)

    assert job is not None, "delete_project must return a job on the happy path"
    assert job.type == "delete_project"
    assert job.status == "pending"

    calls = engine.connection.calls
    sql_text = " ".join(call[0].lower() for call in calls)

    assert "type = 'parse_and_index_document'" in sql_text, (
        "delete_project must cancel in-flight parse_and_index_document jobs"
    )
    assert "lease_expires_at <= now()" in sql_text or "lease_expires_at is null" in sql_text, (
        "delete_project must reap expired or null lease owners"
    )
    assert "lease_owner = null" in sql_text, (
        "delete_project must clear lease owners on cancelled jobs"
    )
    assert "insert into outbox_events" in sql_text, (
        "delete_project must enqueue a project-deletion outbox event"
    )
    assert "on conflict (idempotency_key) do nothing" in sql_text, (
        "project deletion outbox must guard deduplication"
    )


# ---------------------------------------------------------------------------
# delete_document: active-project predicate on mutations
# ---------------------------------------------------------------------------


class DocumentDeleteConnection(RecordingConnection):
    """Drive delete_document through its happy path (fresh deletion)."""

    R2_OBJECT_KEY = "users/u/doc.pdf"

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        if "set_config" in statement:
            return EmptyResult()
        # delete_document lock + select: returns a not-yet-deleted document row.
        if "for update of d, p" in statement:
            return OneMappingResult(
                {
                    "project_id": PROJECT_ID,
                    "r2_object_key": self.R2_OBJECT_KEY,
                    "deleted_at": None,
                }
            )
        # Fail in-flight parse jobs.
        if "update jobs" in statement and "document_deleting" in statement.lower():
            return EmptyResult()
        # Existing delete_document job lookup: return None to take the fresh path.
        if "from jobs" in statement and "delete_document" in statement.lower():
            return EmptyResult()
        # Document status update to 'deleted'.
        if "update documents" in statement and "deleted_at = now()" in statement.lower():
            return EmptyResult()
        # Qdrant scan returns empty scalars.
        if "qdrant_point_id" in statement and "select" in statement.lower():
            return _EmptyScalarsResult()
        # Job INSERT...RETURNING.
        if "insert into jobs" in statement:
            return OneMappingResult(
                {
                    "id": UUID("60000000-0000-4000-8000-000000000142"),
                    "user_id": USER_ID,
                    "project_id": PROJECT_ID,
                    "document_id": DOCUMENT_ID,
                    "type": "delete_document",
                    "status": "pending",
                    "progress": 0,
                    "error_message": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        return EmptyResult()


def test_document_mutations_require_an_active_parent_project() -> None:
    """Reject document mutations when the parent project is inactive.

    Drives delete_document through its happy path and asserts the captured SQL
    enforces the active-project predicate (p.status = 'active') on both the
    FOR UPDATE lock and the document lookup.
    """
    engine = RecordingEngine(DocumentDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    job = repository.delete_document(user(), DOCUMENT_ID)

    assert job is not None, "delete_document must return a job on the happy path"
    assert job.type == "delete_document"

    calls = engine.connection.calls
    sql_text = " ".join(call[0].lower() for call in calls)

    # The FOR UPDATE lock must join to an active project.
    assert "for update of d, p" in sql_text, (
        "delete_document must lock the document and project rows"
    )
    assert "p.status = 'active'" in sql_text, (
        "delete_document must enforce the active-project predicate"
    )
    assert "insert into deletion_jobs" in sql_text, (
        "delete_document must insert a deletion_jobs row"
    )
    assert "insert into outbox_events" in sql_text, (
        "delete_document must enqueue a deletion outbox event"
    )


# ---------------------------------------------------------------------------
# create_upload_url: active-project lock on project-scoped writes
# ---------------------------------------------------------------------------


class UploadUrlConnection(RecordingConnection):
    """Drive create_upload_url through its happy path (workspace kind)."""

    def route(self, statement: str, parameters: dict[str, Any]) -> Any:
        if "set_config" in statement:
            return EmptyResult()
        # Active-project lock returns marker row.
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        # Project kind lookup: workspace.
        if "select id" in statement and "kind" in statement and "from projects" in statement:
            return OneMappingResult({"id": PROJECT_ID, "kind": "workspace"})
        # Document INSERT...RETURNING: returns the document id.
        if "insert into documents" in statement and "returning" in statement:
            return OneMappingResult({"id": DOCUMENT_ID})
        return EmptyResult()


def test_project_scoped_writes_lock_the_active_project_transition() -> None:
    """Serialize child writes with project deletion instead of trusting a stale snapshot.

    Drives create_upload_url through its happy path and asserts the captured SQL
    acquires the active-project FOR UPDATE lock before the document INSERT.
    """
    engine = RecordingEngine(UploadUrlConnection())
    repository = PostgresResearchMateRepository(  # type: ignore[arg-type]
        engine,
        upload_url_factory=lambda _doc_id, _key, payload: "https://upload.example.test/signed",
    )

    result = repository.create_upload_url(
        user(),
        UploadUrlRequest(
            project_id=PROJECT_ID,
            filename="paper.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            size_bytes=100,
        ),
    )

    assert result is not None, "create_upload_url must return a reservation on the happy path"

    calls = engine.connection.calls
    lock_calls = [
        call for call in calls if "for update" in call[0] and "status = 'active'" in call[0]
    ]
    assert len(lock_calls) == 1, (
        "create_upload_url must acquire exactly one active-project FOR UPDATE lock"
    )
    lock_sql, lock_params = lock_calls[0]
    assert "status = 'active'" in lock_sql, "lock must gate on the active status"
    assert "deleted_at is null" in lock_sql, "lock must exclude soft-deleted projects"
    assert lock_params == {"project_id": PROJECT_ID, "user_id": USER_ID}, (
        "lock must bind the caller and project identifiers"
    )

    # The document INSERT must run after the lock.
    insert_idx = next(i for i, call in enumerate(calls) if "insert into documents" in call[0])
    lock_idx = calls.index(lock_calls[0])
    assert insert_idx > lock_idx, "the document INSERT must follow the active-project lock"

    # The INSERT must source from projects with the active predicate.
    insert_sql = calls[insert_idx][0]
    assert "p.status = 'active'" in insert_sql, (
        "the document INSERT must SELECT FROM projects with the active predicate"
    )
    assert "p.deleted_at is null" in insert_sql, (
        "the document INSERT must exclude soft-deleted projects"
    )


def test_active_project_lock_keeps_static_helper_call_contract() -> None:
    """The active-project lock runs one SQL with the owner predicate and FOR UPDATE.

    The lock helper is exercised through create_upload_url (a public method).
    The captured SQL must bind both identifiers and use the FOR UPDATE row lock.
    """
    engine = RecordingEngine(UploadUrlConnection())
    repository = PostgresResearchMateRepository(  # type: ignore[arg-type]
        engine,
        upload_url_factory=lambda _doc_id, _key, payload: "https://upload.example.test/signed",
    )

    result = repository.create_upload_url(
        user(),
        UploadUrlRequest(
            project_id=PROJECT_ID,
            filename="paper.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            size_bytes=100,
        ),
    )
    assert result is not None

    calls = engine.connection.calls
    lock_calls = [
        call for call in calls if "for update" in call[0] and "status = 'active'" in call[0]
    ]
    assert len(lock_calls) == 1, "the lock helper must execute exactly one SQL statement"
    lock_sql, lock_params = lock_calls[0]
    assert "from projects" in lock_sql, "the lock must target the projects table"
    assert "for update" in lock_sql, "the lock must use FOR UPDATE"
    assert lock_params == {"project_id": PROJECT_ID, "user_id": USER_ID}
