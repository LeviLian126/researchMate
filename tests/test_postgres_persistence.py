"""Verify PostgreSQL persistence SQL construction, ownership predicates, and parameter binding.

These tests exercise the persistence mixins through a RecordingConnection that captures
executed SQL and parameters without requiring a real PostgreSQL server. They focus on
the critical contracts: RLS subject configuration, owner predicates, parameter binding,
and the SQL flow of conversation, document lifecycle, and project persistence.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID

import pytest

pytest.importorskip("sqlalchemy", reason="PostgreSQL adapter dependencies are not installed")

from researchmate_api.persistence._postgres_core import _enum_value, _json, _safe_filename
from researchmate_api.persistence.postgres import (
    PostgresResearchMateRepository,
    _psycopg_url,
)
from researchmate_api.schemas.common import CurrentUser, JobStatus
from researchmate_api.schemas.document import UploadUrlRequest
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    StoredObjectMetadata,
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

    def __iter__(self):
        # Listing queries iterate mapping results; an empty result yields no rows.
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

    def __iter__(self):
        # Listing queries iterate the mapping result; expose one row when it exists.
        return iter([self.value] if self.value is not None else [])


class RecordingConnection:
    """Record SQL statements issued by repository operations.

    Subclasses override ``route`` to return deterministic results based on SQL
    markers so each persistence flow can be exercised without a database.
    """

    def __init__(self, *, result=None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._default_result = result or EmptyResult()

    def route(self, statement: str, parameters: dict[str, Any]):
        """Override to return a different result per SQL statement."""
        return self._default_result

    def execute(self, statement: Any, parameters: dict[str, Any] | None = None):
        self.calls.append((str(statement), parameters or {}))
        return self.route(str(statement), parameters or {})


class ConversationLockConnection(RecordingConnection):
    """Return success-only results for active-project lock and conversation lookups."""

    def route(self, statement: str, parameters: dict[str, Any]):
        """Return a marker row for lock checks and the configured lookup row otherwise."""
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        # Return None for conversation lookups by default.
        return EmptyResult()


class ConversationNamedNewChatConnection(RecordingConnection):
    """Drive the rename path by returning a New-chat conversation row."""

    def __init__(self) -> None:
        super().__init__()
        self.rename_returned = False

    def route(self, statement: str, parameters: dict[str, Any]):
        """Return the lock, lookup, and rename rows in order."""
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        if "rename" in statement or "update conversations" in statement:
            self.rename_returned = True
            return EmptyResult()
        if "where id=:id and project_id=:project_id and user_id=:user_id" in statement:
            return OneMappingResult(
                {
                    "id": CONVERSATION_ID,
                    "title": "New chat",
                    "project_id": PROJECT_ID,
                    "created_at": "2026-08-01T00:00:00Z",
                    "updated_at": "2026-08-01T00:00:00Z",
                }
            )
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
    """Expose a recording transaction context."""

    def __init__(self, connection: RecordingConnection | None = None) -> None:
        self.connection = connection or RecordingConnection()

    def begin(self) -> ConnectionContext:
        return ConnectionContext(self.connection)


USER_ID = UUID("00000000-0000-4000-8000-000000000051")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000052")
CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000000053")
DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000000054")
JOB_ID = UUID("00000000-0000-4000-8000-000000000055")


def user() -> CurrentUser:
    """Provide a stable authenticated caller."""
    return CurrentUser(id=USER_ID, email="owner@example.test", role="user")


# ---------------------------------------------------------------------------
# URL & serialization helpers
# ---------------------------------------------------------------------------


def test_psycopg_url_normalizes_legacy_postgres_scheme() -> None:
    """Normalize both legacy and canonical Postgres schemes to the psycopg3 driver."""
    assert _psycopg_url("postgres://user:pass@host/db").startswith("postgresql+psycopg://")
    assert _psycopg_url("postgresql://user:pass@host/db").startswith("postgresql+psycopg://")
    assert _psycopg_url("postgresql+psycopg://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_enum_value_serializes_enums_and_strings() -> None:
    """Normalize enum values and raw strings to plain values before binding."""
    assert _enum_value(JobStatus.PENDING) == "pending"
    assert _enum_value("active") == "active"


def test_json_serialization_is_compact_and_unicode_preserving() -> None:
    """Serialize SQL-bound payloads compactly while preserving CJK characters."""
    assert _json({"key": "value", "中文": "检索"}) == ('{"key":"value","中文":"检索"}')


def test_safe_filename_collapses_unsafe_characters() -> None:
    """Sanitize filenames so storage keys never carry path-traversal segments."""
    assert _safe_filename("paper v1.pdf") == "paper_v1.pdf"
    assert _safe_filename("../weird/../path/PAPER.PDF") == "weird_.._path_PAPER.PDF"
    assert _safe_filename("   ") == "document"


# ---------------------------------------------------------------------------
# Conversation persistence (SQL flow + parameter binding)
# ---------------------------------------------------------------------------


def test_existing_conversation_lookup_sets_owner_predicate_and_join_to_active_project() -> None:
    """Bind owner and active-project predicates when resolving an existing conversation."""
    repository = PostgresResearchMateRepository(
        RecordingEngine(ConversationLockConnection())  # type: ignore[arg-type]
    )
    repository.ensure_conversation(user(), PROJECT_ID, CONVERSATION_ID, "first message")

    # calls[0] is the RLS guard. calls[1] is the active-project lock.
    # calls[2] is the existing-conversation lookup SQL.
    calls = repository.engine.connection.calls
    assert len(calls) == 3
    lock_sql, lock_params = calls[1]
    assert "for update" in lock_sql
    assert "status = 'active'" in lock_sql
    assert "deleted_at is null" in lock_sql
    assert lock_params == {"project_id": PROJECT_ID, "user_id": USER_ID}

    lookup_sql, lookup_params = calls[2]
    assert "id=:id" in lookup_sql
    assert "project_id=:project_id" in lookup_sql
    assert "user_id=:user_id" in lookup_sql
    assert "deleted_at is null" in lookup_sql
    assert "p.status='active'" in lookup_sql
    assert lookup_params["id"] == CONVERSATION_ID
    assert lookup_params["project_id"] == PROJECT_ID
    assert lookup_params["user_id"] == USER_ID


def test_transaction_sets_jwt_subject_then_runs_repository_query() -> None:
    """Set the RLS subject before any repository SQL executes."""
    repository = PostgresResearchMateRepository(
        RecordingEngine(ConversationLockConnection())  # type: ignore[arg-type]
    )
    repository.ensure_conversation(user(), PROJECT_ID, CONVERSATION_ID, "first message")

    rls_sql, rls_params = repository.engine.connection.calls[0]
    assert "set_config('request.jwt.claim.sub'" in rls_sql
    assert rls_params == {"user_id": str(USER_ID)}


def test_existing_conversation_named_new_chat_triggers_rename_query() -> None:
    """Rename a default-titled conversation only when no messages are persisted."""
    connection = ConversationNamedNewChatConnection()
    repository = PostgresResearchMateRepository(RecordingEngine(connection))  # type: ignore[arg-type]
    repository.ensure_conversation(user(), PROJECT_ID, CONVERSATION_ID, "first message")

    rename_sql = connection.calls[3][0]
    rename_params = connection.calls[3][1]
    assert "update conversations c" in rename_sql
    assert "set title=:title,updated_at=now()" in rename_sql
    assert "not exists" in rename_sql
    assert "messages m" in rename_sql
    assert rename_params["title"] == "first message"
    assert rename_params["id"] == CONVERSATION_ID
    assert rename_params["user_id"] == USER_ID


def test_list_conversations_requires_owned_project_before_listing() -> None:
    """Require an owned project before listing its conversations."""

    # Routing returns a marker row for the active-project predicate (so the listing runs)
    # and an empty iterable for the listing SQL itself (so the result list is empty).
    class ListingConnection(RecordingConnection):
        def route(self, statement: str, parameters: dict[str, Any]):
            if "from conversations" in statement:
                return EmptyResult()
            return OneMappingResult({"?column?": 1})

    repository = PostgresResearchMateRepository(RecordingEngine(ListingConnection()))  # type: ignore[arg-type]
    repository.list_conversations(user(), PROJECT_ID)

    project_check = repository.engine.connection.calls[1][0]
    listing_sql = repository.engine.connection.calls[2][0]
    listing_params = repository.engine.connection.calls[2][1]
    assert "from projects" in project_check
    assert "from conversations" in listing_sql
    assert "deleted_at is null" in listing_sql
    assert "limit 100" in listing_sql
    assert listing_params == {"project_id": PROJECT_ID, "user_id": USER_ID}


def test_existing_conversation_missing_returns_none() -> None:
    """Conceal absent or foreign conversations rather than constructing partial state."""
    repository = PostgresResearchMateRepository(RecordingEngine())  # type: ignore[arg-type]
    # EmptyResult causes the active-project lock and the lookup to both return None.
    assert (
        repository.ensure_conversation(user(), PROJECT_ID, CONVERSATION_ID, "first message") is None
    )
    # Only the RLS guard and the active-project lock execute; the lookup never runs.
    assert len(repository.engine.connection.calls) == 2


# ---------------------------------------------------------------------------
# Document lifecycle & project persistence (SQL contracts)
# ---------------------------------------------------------------------------


def test_complete_document_requires_object_storage_configuration() -> None:
    """Reject completion when the object-storage reader is not configured."""
    repository = PostgresResearchMateRepository(RecordingEngine())  # type: ignore[arg-type]
    with pytest.raises(ObjectStorageConfigurationError):
        repository.complete_document(user(), DOCUMENT_ID, "irrelevant")


class CompleteReservationConnection(RecordingConnection):
    """Drive complete_document Transaction 1 so the reservation lookup SQL is captured."""

    def route(self, statement: str, parameters: dict[str, Any]):
        if "r2_object_key" in statement and "join projects" in statement:
            return OneMappingResult(
                {
                    "r2_object_key": "users/u/document.pdf",
                    "size_bytes": 100,
                    "mime_type": "application/pdf",
                }
            )
        return EmptyResult()


def test_complete_document_requires_active_project_join_in_reservation_lookup() -> None:
    """Join projects inside the reservation lookup to enforce the active-project predicate.

    Drives complete_document Transaction 1 via a RecordingConnection and asserts
    the reservation lookup SQL joins projects with the active-owner predicate.
    """
    engine = RecordingEngine(CompleteReservationConnection())
    repository = PostgresResearchMateRepository(
        engine,  # type: ignore[arg-type]
        object_metadata_reader=lambda _key, **_kwargs: StoredObjectMetadata(
            size_bytes=100,
            content_type="application/pdf",
            etag=None,
            metadata={},
        ),
    )
    # Transaction 1 returns a reservation; Transaction 2 returns None (no owner).
    repository.complete_document(user(), DOCUMENT_ID, "irrelevant")

    reservation_sql = engine.connection.calls[1][0]
    assert "join projects p" in reservation_sql, "reservation lookup must join the projects table"
    assert "p.user_id = d.user_id" in reservation_sql, (
        "reservation lookup must enforce the owner join"
    )
    assert "p.status = 'active'" in reservation_sql, (
        "reservation lookup must require an active project"
    )
    assert "p.deleted_at is null" in reservation_sql, (
        "reservation lookup must exclude soft-deleted projects"
    )


class CompleteDocumentConnection(RecordingConnection):
    """Drive complete_document through its happy path while recording SQL.

    Transaction 1 returns a reserved object row; Transaction 2 returns the document
    owner row, the active-project lock marker, the UPDATE...RETURNING row, and the
    job INSERT row so complete_document persists a job and outbox event.
    """

    R2_OBJECT_KEY = "users/u/document.pdf"

    def route(self, statement: str, parameters: dict[str, Any]):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
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
        if "select project_id from documents" in statement:
            return OneMappingResult({"project_id": PROJECT_ID})
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        if "update documents" in statement and "returning" in statement:
            return OneMappingResult({"project_id": PROJECT_ID, "r2_object_key": self.R2_OBJECT_KEY})
        if "insert into jobs" in statement:
            return OneMappingResult(
                {
                    "id": UUID("40000000-0000-4000-8000-000000000054"),
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
        return EmptyResult()


class UploadUrlConnection(RecordingConnection):
    """Drive create_upload_url through its happy path (workspace kind)."""

    def route(self, statement: str, parameters: dict[str, Any]):
        if "set_config" in statement:
            return EmptyResult()
        if "for update" in statement and "status = 'active'" in statement:
            return OneMappingResult({"?column?": 1})
        if "select id" in statement and "kind" in statement and "from projects" in statement:
            return OneMappingResult({"id": PROJECT_ID, "kind": "workspace"})
        if "insert into documents" in statement and "returning" in statement:
            return OneMappingResult({"id": DOCUMENT_ID})
        return EmptyResult()


class _EmptyScalarsResult:
    """Return an empty scalar list for object/qdrant scans."""

    def scalars(self) -> _EmptyScalarsResult:
        return self

    def all(self) -> list:
        return []


class DocumentDeleteConnection(RecordingConnection):
    """Drive delete_document through its happy path (fresh deletion)."""

    R2_OBJECT_KEY = "users/u/doc.pdf"

    def route(self, statement: str, parameters: dict[str, Any]):
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
                    "id": UUID("60000000-0000-4000-8000-000000000154"),
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


def test_delete_document_serializes_active_owner_and_job_cleanup_in_one_unit() -> None:
    """Lock the active owner row, cancel pending jobs, and write a deletion job atomically.

    Drives delete_document through its happy path via a RecordingConnection and
    asserts the captured SQL locks both rows, cancels in-flight parse jobs, and
    persists a delete_document job plus a deletion_jobs row atomically.
    """
    engine = RecordingEngine(DocumentDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    job = repository.delete_document(user(), DOCUMENT_ID)

    assert job is not None, "delete_document must return a job on the happy path"
    assert job.type == "delete_document"

    calls = engine.connection.calls
    sql_text = " ".join(call[0].lower() for call in calls)

    assert "for update of d, p" in sql_text, (
        "delete_document must lock both document and project rows"
    )
    assert "type = 'parse_and_index_document'" in sql_text, (
        "delete_document must cancel in-flight parse_and_index_document jobs"
    )
    assert "status = 'failed', error_message = 'document_deleting'" in sql_text, (
        "delete_document must mark cancelled jobs failed with the deletion code"
    )
    assert "type = 'delete_document'" in sql_text, (
        "delete_document must persist a delete_document job row"
    )
    assert "insert into outbox_events" in sql_text, (
        "delete_document must enqueue a deletion outbox event"
    )


class PersonalProjectLockConnection(RecordingConnection):
    """Return a personal-kind project so delete_project short-circuits."""

    def route(self, statement: str, parameters: dict[str, Any]):
        if "set_config" in statement:
            return EmptyResult()
        if "for update" in statement and "kind" in statement:
            return OneMappingResult({"status": "active", "kind": "personal"})
        return EmptyResult()


def test_delete_project_personal_kind_is_short_circuited() -> None:
    """Reject project deletion when the project is the caller's personal kind.

    Drives delete_project against a personal-kind project and asserts the method
    returns None immediately after the lock — no job INSERT, no outbox enqueue.
    """
    engine = RecordingEngine(PersonalProjectLockConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    result = repository.delete_project(user(), PROJECT_ID)

    assert result is None, "delete_project must short-circuit personal-kind projects"

    # Only the RLS guard + the lock SELECT should execute.
    calls = engine.connection.calls
    assert len(calls) == 2, (
        "delete_project must stop after the personal-kind guard (no further SQL)"
    )
    assert "for update" in calls[1][0]
    sql_text = calls[1][0].lower()
    assert "status in ('active', 'deleting')" in sql_text, (
        "the project lock must target active or deleting status"
    )
    assert "insert into jobs" not in " ".join(c[0].lower() for c in calls), (
        "no job must be persisted when the project kind is personal"
    )


class ProjectDeleteConnection(RecordingConnection):
    """Drive delete_project through the active-branch happy path."""

    def route(self, statement: str, parameters: dict[str, Any]):
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
                    "id": UUID("50000000-0000-4000-8000-000000000154"),
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


def test_delete_project_serializes_with_for_update_on_active_project() -> None:
    """Lock the parent project before scheduling deletion work.

    Drives delete_project through its happy path and asserts the captured SQL
    acquires a FOR UPDATE lock with the status predicate and enqueues the
    project-deletion outbox event.
    """
    engine = RecordingEngine(ProjectDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    job = repository.delete_project(user(), PROJECT_ID)

    assert job is not None, "delete_project must return a job on the happy path"
    assert job.type == "delete_project"

    calls = engine.connection.calls
    lock_sql = calls[1][0]
    assert "for update" in lock_sql, "delete_project must acquire a FOR UPDATE lock"
    assert "status in ('active', 'deleting')" in lock_sql, (
        "the project lock must target active or deleting status"
    )

    sql_text = " ".join(call[0].lower() for call in calls)
    assert "insert into outbox_events" in sql_text, (
        "delete_project must enqueue a project-deletion outbox event"
    )
    assert "on conflict (idempotency_key) do nothing" in sql_text, (
        "project deletion outbox must guard deduplication"
    )


def test_delete_project_cancels_inflight_parse_and_index_jobs() -> None:
    """Cancel pending or expired ingestion jobs when scheduling project deletion.

    Drives delete_project through its happy path and asserts the captured SQL
    cancels parse_and_index_document jobs that are pending or have expired leases.
    """
    engine = RecordingEngine(ProjectDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    repository.delete_project(user(), PROJECT_ID)

    calls = engine.connection.calls
    cancel_calls = [
        call for call in calls if "update jobs" in call[0] and "parse_and_index_document" in call[0]
    ]
    assert cancel_calls, "delete_project must cancel in-flight parse_and_index_document jobs"
    cancel_sql = cancel_calls[0][0].lower()
    assert "status = 'pending'" in cancel_sql, "cancellation must target pending parse jobs"
    assert "lease_expires_at is null" in cancel_sql or "lease_expires_at <= now()" in cancel_sql, (
        "cancellation must also target expired-lease running jobs"
    )


def test_delete_project_persists_deletion_jobs_row_with_owner_predicate() -> None:
    """Insert into deletion_jobs only after the active project lock succeeds.

    Drives delete_project through its happy path and asserts the captured SQL
    inserts a deletion_jobs row with the 'pending' status and the owner predicate.
    """
    engine = RecordingEngine(ProjectDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    repository.delete_project(user(), PROJECT_ID)

    calls = engine.connection.calls
    deletion_job_calls = [call for call in calls if "insert into deletion_jobs" in call[0]]
    assert deletion_job_calls, (
        "delete_project must insert a deletion_jobs row after the lock succeeds"
    )
    sql_text = deletion_job_calls[0][0].lower()
    assert "values (:id, :user_id, :project_id, 'pending')" in sql_text, (
        "deletion_jobs INSERT must bind the owner and project identifiers with 'pending'"
    )


def test_ensure_user_upserts_profile_with_role_and_provider() -> None:
    """Upsert caller profiles with explicit role and provider columns."""
    repository = PostgresResearchMateRepository(RecordingEngine())  # type: ignore[arg-type]
    repository.ensure_user(user())

    sql, params = repository.engine.connection.calls[1]
    assert "insert into profiles (id, email, provider, role)" in sql
    assert "on conflict (id) do update" in sql
    assert "set email = excluded.email, role = excluded.role, updated_at = now()" in sql
    assert params["id"] == USER_ID
    assert params["email"] == "owner@example.test"
    assert params["role"] == "user"


class CreateProjectConnection(RecordingConnection):
    """Drive create_project through its happy path so the project INSERT SQL is captured."""

    def route(self, statement: str, parameters: dict[str, Any]):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        if "set_config" in statement:
            return EmptyResult()
        # ensure_user upsert: return nothing.
        if "insert into profiles" in statement:
            return EmptyResult()
        # create_project INSERT...SELECT...RETURNING: return the project row.
        if "insert into projects" in statement and "returning" in statement:
            return OneMappingResult(
                {
                    "id": PROJECT_ID,
                    "user_id": USER_ID,
                    "name": "test",
                    "kind": "workspace",
                    "status": "active",
                    "expires_at": now,
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                }
            )
        return EmptyResult()


def test_create_project_requires_existing_profile() -> None:
    """Refuse to create a project for a profile that did not exist before.

    Drives create_project through its happy path and asserts the captured SQL
    gates the project INSERT on a profiles EXISTS subquery and sets kind='workspace'.
    """
    engine = RecordingEngine(CreateProjectConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    from researchmate_api.schemas.project import ProjectCreate

    project = repository.create_project(user(), ProjectCreate(name="test"))

    assert project is not None, "create_project must return a project on the happy path"

    calls = engine.connection.calls
    insert_calls = [
        call for call in calls if "insert into projects" in call[0] and "returning" in call[0]
    ]
    assert insert_calls, "create_project must issue the project INSERT...RETURNING"
    insert_sql = insert_calls[0][0]
    assert "where exists (select 1 from profiles where id = :user_id)" in insert_sql.lower(), (
        "project INSERT must gate on a profiles EXISTS subquery"
    )
    # The kind column is set with a literal 'workspace' value in the insert-select.
    assert "'workspace'" in insert_sql.lower(), (
        "project INSERT must set the kind column to 'workspace'"
    )


def test_get_project_applies_owner_and_deleted_at_predicate() -> None:
    """Owner predicate and non-deleted predicate are required for project lookups."""
    repository = PostgresResearchMateRepository(RecordingEngine())  # type: ignore[arg-type]
    assert repository.get_project(user(), PROJECT_ID) is None
    lookup_sql, lookup_params = repository.engine.connection.calls[1]
    assert "id = :project_id and user_id = :user_id" in lookup_sql
    assert "deleted_at is null" in lookup_sql
    assert lookup_params == {"project_id": PROJECT_ID, "user_id": USER_ID}


def test_complete_document_returns_none_for_missing_reservation() -> None:
    """Return None when the reserved document cannot be found under the owner predicate."""
    repository = PostgresResearchMateRepository(
        RecordingEngine(),
        object_metadata_reader=lambda _key, **_kwargs: StoredObjectMetadata(
            size_bytes=10,
            content_type="application/pdf",
            etag=None,
            metadata={},
        ),
    )  # type: ignore[arg-type]
    assert repository.complete_document(user(), DOCUMENT_ID, "irrelevant") is None


# ---------------------------------------------------------------------------
# Internal helpers: idempotency keys & job insertion
# ---------------------------------------------------------------------------


def test_lock_active_project_static_helper_keeps_owner_predicate() -> None:
    """The project-lock helper executes one SQL with the owner predicate and FOR UPDATE.

    The lock is exercised through the create_upload_url public method (via the
    UploadUrlConnection that returns the lock marker row). The captured SQL must
    bind both identifiers and use the FOR UPDATE row lock.
    """
    engine = RecordingEngine(UploadUrlConnection())
    repository = PostgresResearchMateRepository(  # type: ignore[arg-type]
        engine,
        upload_url_factory=lambda _doc_id, _key, payload: "https://upload.example.test/signed",
    )

    repository.create_upload_url(
        user(),
        UploadUrlRequest(
            project_id=PROJECT_ID,
            filename="paper.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            size_bytes=100,
        ),
    )

    calls = engine.connection.calls
    lock_calls = [
        call for call in calls if "for update" in call[0] and "status = 'active'" in call[0]
    ]
    assert len(lock_calls) == 1, "the lock helper must execute exactly one SQL statement"
    sql = lock_calls[0][0]
    params = lock_calls[0][1]
    assert "status = 'active'" in sql
    assert "deleted_at is null" in sql
    assert "for update" in sql
    assert params == {"project_id": PROJECT_ID, "user_id": USER_ID}


def test_enqueue_project_deletion_writes_deterministic_idempotency_key() -> None:
    """Compose the project-deletion idempotency key from the typed identifiers.

    Observes the outbox enqueue through the delete_project public method.
    The PROJECT_ID and JOB_ID are fixed, so the idempotency key is deterministic.
    """
    engine = RecordingEngine(ProjectDeleteConnection())
    repository = PostgresResearchMateRepository(engine)  # type: ignore[arg-type]

    job = repository.delete_project(user(), PROJECT_ID)
    assert job is not None, "delete_project must return a job to observe the outbox"

    calls = engine.connection.calls
    outbox_calls = [call for call in calls if "insert into outbox_events" in call[0]]
    assert len(outbox_calls) == 1, (
        "delete_project must enqueue exactly one project-deletion outbox event"
    )
    sql = outbox_calls[0][0]
    params = outbox_calls[0][1]
    assert "on conflict (idempotency_key) do nothing" in sql, (
        "outbox enqueue must guard deduplication"
    )
    # delivery_id == job.id, so the idempotency key is project:{project}:{action}:{job}:{job}.
    assert params["idempotency_key"] == (f"project:{PROJECT_ID}:delete:{job.id}:{job.id}"), (
        "the project-deletion idempotency key must be deterministic"
    )
    assert params["payload"] == _json(
        {"job_id": str(job.id), "user_id": str(USER_ID), "project_id": str(PROJECT_ID)}
    ), "the outbox payload must carry the typed identifiers as compact JSON"


def test_enqueue_document_event_picks_action_by_event_type() -> None:
    """Choose 'ingest' vs 'delete' in the idempotency key by event_type.

    Observes the document event outbox through two public methods:
    - complete_document (ingest path)
    - delete_document (delete path)

    Both produce outbox INSERTs whose idempotency keys encode the action.
    """
    # --- ingest path via complete_document ---
    ingest_engine = RecordingEngine(CompleteDocumentConnection())
    ingest_repo = PostgresResearchMateRepository(
        ingest_engine,  # type: ignore[arg-type]
        object_metadata_reader=lambda _key, **_kwargs: StoredObjectMetadata(
            size_bytes=100,
            content_type="application/pdf",
            etag=None,
            metadata={},
        ),
    )
    ingest_job = ingest_repo.complete_document(user(), DOCUMENT_ID, "a" * 64)
    assert ingest_job is not None, "complete_document must return a job"
    ingest_outbox = [
        c for c in ingest_engine.connection.calls if "insert into outbox_events" in c[0]
    ]
    assert len(ingest_outbox) == 1, (
        "complete_document must enqueue exactly one document-ingest outbox event"
    )
    ingest_params = ingest_outbox[0][1]
    assert ingest_params["idempotency_key"] == (
        f"document:{DOCUMENT_ID}:ingest:{ingest_job.id}:{ingest_job.id}"
    ), "the ingest idempotency key must encode the 'ingest' action"
    assert ingest_params["payload"] == _json(
        {
            "job_id": str(ingest_job.id),
            "user_id": str(USER_ID),
            "project_id": str(PROJECT_ID),
            "document_id": str(DOCUMENT_ID),
        }
    ), "the ingest payload must carry the document_id"

    # --- delete path via delete_document ---
    delete_engine = RecordingEngine(DocumentDeleteConnection())
    delete_repo = PostgresResearchMateRepository(delete_engine)  # type: ignore[arg-type]
    delete_job = delete_repo.delete_document(user(), DOCUMENT_ID)
    assert delete_job is not None, "delete_document must return a job"
    delete_outbox = [
        c for c in delete_engine.connection.calls if "insert into outbox_events" in c[0]
    ]
    assert len(delete_outbox) == 1, (
        "delete_document must enqueue exactly one document-delete outbox event"
    )
    delete_params = delete_outbox[0][1]
    assert delete_params["idempotency_key"] == (
        f"document:{DOCUMENT_ID}:delete:{delete_job.id}:{delete_job.id}"
    ), "the delete idempotency key must encode the 'delete' action"
    assert delete_params["payload"] == _json(
        {
            "job_id": str(delete_job.id),
            "user_id": str(USER_ID),
            "project_id": str(PROJECT_ID),
            "document_id": str(DOCUMENT_ID),
        }
    ), "the delete payload must carry the document_id"
