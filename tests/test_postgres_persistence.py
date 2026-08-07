"""Verify PostgreSQL persistence SQL construction, ownership predicates, and parameter binding.

These tests exercise the persistence mixins through a RecordingConnection that captures
executed SQL and parameters without requiring a real PostgreSQL server. They focus on
the critical contracts: RLS subject configuration, owner predicates, parameter binding,
and the SQL flow of conversation, document lifecycle, and project persistence.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from inspect import getsource
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
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
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


def test_complete_document_requires_active_project_join_in_reservation_lookup() -> None:
    """Join projects inside the reservation lookup to enforce the active-project predicate."""
    lookup = getsource(PostgresResearchMateRepository.complete_document).lower()
    assert "p.user_id = d.user_id" in lookup
    assert "p.status = 'active'" in lookup
    assert "p.deleted_at is null" in lookup


def test_delete_document_serializes_active_owner_and_job_cleanup_in_one_unit() -> None:
    """Lock the active owner row, cancel pending jobs, and write a deletion job atomically."""
    delete = getsource(PostgresResearchMateRepository.delete_document)
    assert "for update of d, p" in delete.lower()
    assert "type = 'parse_and_index_document'" in delete.lower()
    assert "status = 'failed', error_message = 'DOCUMENT_DELETING'" in delete
    assert "type = 'delete_document'" in delete.lower()
    assert "_enqueue_document_event" in delete


def test_delete_project_personal_kind_is_short_circuited() -> None:
    """Reject project deletion when the project is the caller's personal kind."""
    delete = getsource(PostgresResearchMateRepository.delete_project)
    # The personal-kind short-circuit is a Python-level guard that runs after the
    # SQL returns the project row; the source code compares to "personal".
    assert 'project["kind"] == "personal"' in delete


def test_delete_project_serializes_with_for_update_on_active_project() -> None:
    """Lock the parent project before scheduling deletion work."""
    delete = getsource(PostgresResearchMateRepository.delete_project).lower()
    assert "for update" in delete
    assert "status in ('active', 'deleting')" in delete
    assert "_enqueue_project_deletion" in delete


def test_delete_project_cancels_inflight_parse_and_index_jobs() -> None:
    """Cancel pending or expired ingestion jobs when scheduling project deletion."""
    delete = getsource(PostgresResearchMateRepository.delete_project).lower()
    assert "type = 'parse_and_index_document'" in delete
    assert (
        "(status = 'pending'\n                        or" in delete
        or "lease_expires_at <= now()" in delete
    )


def test_delete_project_persists_deletion_jobs_row_with_owner_predicate() -> None:
    """Insert into deletion_jobs only after the active project lock succeeds."""
    delete = getsource(PostgresResearchMateRepository.delete_project).lower()
    assert "insert into deletion_jobs" in delete
    assert "values (:id, :user_id, :project_id, 'pending')" in delete


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


def test_create_project_requires_existing_profile() -> None:
    """Refuse to create a project for a profile that did not exist before."""
    create = getsource(PostgresResearchMateRepository.create_project).lower()
    assert "where exists (select 1 from profiles where id = :user_id)" in create
    # The kind column is set with a literal 'workspace' value in the insert-select.
    assert "select :id, :user_id, :name, 'workspace', :expires_at" in create


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
    from researchmate_api.services.object_storage import StoredObjectMetadata

    repository = PostgresResearchMateRepository(
        RecordingEngine(),
        object_metadata_reader=lambda _key: StoredObjectMetadata(
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
    """The static project-lock helper executes one SQL with the owner predicate."""
    repository = object.__new__(PostgresResearchMateRepository)
    connection = RecordingConnection()

    assert repository._lock_active_project(connection, USER_ID, PROJECT_ID) is False
    sql, params = connection.calls[0]
    assert "status = 'active'" in sql
    assert "deleted_at is null" in sql
    assert "for update" in sql
    assert params == {"project_id": PROJECT_ID, "user_id": USER_ID}


def test_enqueue_project_deletion_writes_deterministic_idempotency_key() -> None:
    """Compose the project-deletion idempotency key from the typed identifiers."""
    connection = RecordingConnection()
    repository = object.__new__(PostgresResearchMateRepository)
    repository._enqueue_project_deletion(
        connection,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        delivery_id=JOB_ID,
    )
    sql, params = connection.calls[0]
    assert "insert into outbox_events" in sql
    assert "on conflict (idempotency_key) do nothing" in sql
    assert params["idempotency_key"] == f"project:{PROJECT_ID}:delete:{JOB_ID}:{JOB_ID}"
    assert params["payload"] == _json(
        {"job_id": str(JOB_ID), "user_id": str(USER_ID), "project_id": str(PROJECT_ID)}
    )


def test_enqueue_document_event_picks_action_by_event_type() -> None:
    """Choose 'ingest' vs 'delete' in the idempotency key by event_type."""
    connection_ingest = RecordingConnection()
    repository = object.__new__(PostgresResearchMateRepository)
    delivery_id_ingest = UUID("00000000-0000-4000-8000-000000000060")
    repository._enqueue_document_event(
        connection_ingest,
        event_type="document.ingest.requested",
        document_id=DOCUMENT_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        delivery_id=delivery_id_ingest,
    )
    _, ingest_params = connection_ingest.calls[0]
    assert ingest_params["idempotency_key"] == (
        f"document:{DOCUMENT_ID}:ingest:{JOB_ID}:{delivery_id_ingest}"
    )

    connection_delete = RecordingConnection()
    delivery_id_delete = UUID("00000000-0000-4000-8000-000000000061")
    repository._enqueue_document_event(
        connection_delete,
        event_type="document.delete.requested",
        document_id=DOCUMENT_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        delivery_id=delivery_id_delete,
    )
    _, delete_params = connection_delete.calls[0]
    assert delete_params["idempotency_key"] == (
        f"document:{DOCUMENT_ID}:delete:{JOB_ID}:{delivery_id_delete}"
    )
    assert delete_params["payload"] == _json(
        {
            "job_id": str(JOB_ID),
            "user_id": str(USER_ID),
            "project_id": str(PROJECT_ID),
            "document_id": str(DOCUMENT_ID),
        }
    )
