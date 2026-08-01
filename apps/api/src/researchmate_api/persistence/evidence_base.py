"""Shared transaction, serialization, locking, event, and outbox primitives."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from researchmate_api.persistence.postgres import _psycopg_url
from researchmate_api.schemas.common import CurrentUser


def _json(value: object) -> str:
    """Serialize a database JSON payload deterministically without ASCII escaping."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def _progress(status: str, safe_payload: dict | None) -> int:
    """Derive bounded public progress from a safe event payload or workflow status."""
    if safe_payload and isinstance(safe_payload.get("progress"), int):
        return max(0, min(100, safe_payload["progress"]))
    return {
        "pending": 0,
        "running": 25,
        "waiting_human": 65,
        "succeeded": 100,
        "failed": 100,
        "cancelled": 100,
    }.get(status, 0)


class PostgresEvidenceRepositoryBase:
    """Own the engine and transaction primitives shared by evidence aggregates."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to an existing SQLAlchemy engine."""
        self.engine = engine

    @classmethod
    def from_database_url(cls, database_url: str) -> PostgresEvidenceRepositoryBase:
        """Create a repository with the service's canonical PostgreSQL URL settings."""
        return cls(
            create_engine(
                _psycopg_url(database_url),
                pool_pre_ping=True,
                pool_recycle=300,
                future=True,
            )
        )

    @contextmanager
    def _transaction(self, user: CurrentUser | None = None) -> Iterator[Connection]:
        """Open one transaction and install the optional RLS user claim locally."""
        with self.engine.begin() as connection:
            if user is not None:
                connection.execute(
                    text("select set_config('request.jwt.claim.sub', :user_id, true)"),
                    {"user_id": str(user.id)},
                )
            yield connection

    @staticmethod
    def _lock_active_project(
        connection: Connection, user_id: UUID, project_id: UUID
    ) -> bool:
        """Serialize evidence writes against the project deletion transition."""
        row = connection.execute(
            text(
                """
                select 1 from projects
                where id=:project_id and user_id=:user_id
                  and status='active' and deleted_at is null
                for update
                """
            ),
            {"project_id": project_id, "user_id": user_id},
        ).one_or_none()
        return row is not None

    @staticmethod
    def _lock_idempotency(
        connection: Connection, user_id: UUID, idempotency_key: str
    ) -> None:
        """Serialize writes sharing one owner-scoped idempotency key."""
        connection.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key,2))"),
            {"key": f"{user_id}:{idempotency_key}"},
        )

    @staticmethod
    def _append_event(
        connection: Connection,
        run_id: UUID,
        *,
        node_key: str,
        event_type: str,
        status: str,
        safe_payload: dict,
        attempt: int = 1,
    ) -> None:
        """Append the next ordered, payload-safe event within the caller transaction."""
        connection.execute(
            text(
                """
                insert into run_events (
                  run_id,sequence,node_key,event_type,attempt,status,safe_payload
                ) values (
                  :run_id,
                  coalesce((select max(sequence)+1 from run_events where run_id=:run_id),0),
                  :node_key,:event_type,:attempt,:status,cast(:payload as jsonb)
                )
                """
            ),
            {
                "run_id": run_id,
                "node_key": node_key,
                "event_type": event_type,
                "attempt": attempt,
                "status": status,
                "payload": _json(safe_payload),
            },
        )

    @staticmethod
    def _append_outbox(
        connection: Connection,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
        idempotency_key: str,
    ) -> None:
        """Append an idempotent outbox message within the caller transaction."""
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type,aggregate_id,event_type,payload,idempotency_key
                ) values (
                  :aggregate_type,:aggregate_id,:event_type,cast(:payload as jsonb),:key
                ) on conflict (idempotency_key) do nothing
                """
            ),
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": _json(payload),
                "key": idempotency_key,
            },
        )

