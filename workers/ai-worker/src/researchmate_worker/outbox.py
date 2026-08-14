"""Claim durable outbox events and publish them to stable Celery task names."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Protocol
from uuid import UUID

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class ClaimedOutboxEvent:
    """Carry one leased outbox event and its validated publication payload."""

    id: UUID
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str
    attempts: int


class OutboxStore(Protocol):
    """Define durable claim and publication transitions for outbox events."""

    def claim(self, limit: int, max_attempts: int) -> list[ClaimedOutboxEvent]: ...

    def mark_published(self, event_id: UUID) -> None: ...

    def mark_failed(self, event_id: UUID, attempts: int, safe_error: str) -> None: ...

    def requeue_stale(self, older_than: datetime) -> int: ...


class TaskPublisher(Protocol):
    """Define stable task publication independent of the Celery client."""

    def publish(self, event: ClaimedOutboxEvent) -> None: ...


class OutboxDispatcher:
    """Publish bounded batches while preserving at-least-once delivery semantics."""

    def __init__(
        self,
        store: OutboxStore,
        publisher: TaskPublisher,
        *,
        batch_size: int = 50,
        max_attempts: int = 8,
    ) -> None:
        self.store = store
        self.publisher = publisher
        self.batch_size = batch_size
        self.max_attempts = max_attempts

    def dispatch_once(self) -> int:
        """Publish one bounded batch and persist each delivery outcome."""
        published = 0
        for event in self.store.claim(self.batch_size, self.max_attempts):
            try:
                self.publisher.publish(event)
            except Exception as exc:
                self.store.mark_failed(event.id, event.attempts, type(exc).__name__)
                continue
            self.store.mark_published(event.id)
            published += 1
        return published

    def recover_stale_claims(self, minutes: int = 15) -> int:
        """Return expired publication leases to the pending queue."""
        return self.store.requeue_stale(datetime.now(UTC) - timedelta(minutes=minutes))


class SqlOutboxStore:
    """Persist outbox leases, attempts, and publication outcomes."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def claim(self, limit: int, max_attempts: int) -> list[ClaimedOutboxEvent]:
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select id, event_type, payload, idempotency_key, attempts
                    from outbox_events
                    where status in ('pending', 'failed')
                      and available_at <= now() and attempts < :max_attempts
                    order by available_at, created_at, id
                    for update skip locked
                    limit :limit
                    """
                    ),
                    {"limit": limit, "max_attempts": max_attempts},
                )
                .mappings()
                .all()
            )
            events = [
                ClaimedOutboxEvent(
                    id=row["id"],
                    event_type=row["event_type"],
                    payload=dict(row["payload"]),
                    idempotency_key=row["idempotency_key"],
                    attempts=int(row["attempts"]) + 1,
                )
                for row in rows
            ]
            if events:
                connection.execute(
                    text(
                        """
                        update outbox_events
                        set status = 'publishing', attempts = attempts + 1, last_error = null,
                            available_at = now()
                        where id = any(:ids)
                        """
                    ),
                    {"ids": [event.id for event in events]},
                )
            return events

    def mark_published(self, event_id: UUID) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update outbox_events
                    set status = 'published', published_at = now(), last_error = null
                    where id = :id and status = 'publishing'
                    """
                ),
                {"id": event_id},
            )

    def mark_failed(self, event_id: UUID, attempts: int, safe_error: str) -> None:
        delay_seconds = min(300, 2 ** min(attempts, 8))
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update outbox_events
                    set status = 'failed', last_error = :safe_error,
                        available_at = now() + make_interval(secs => :delay_seconds)
                    where id = :id and status = 'publishing'
                    """
                ),
                {
                    "id": event_id,
                    "safe_error": safe_error[:200],
                    "delay_seconds": delay_seconds,
                },
            )

    def requeue_stale(self, older_than: datetime) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    update outbox_events
                    set status = 'failed', last_error = 'stale_publishing_claim', available_at = now()
                    where status = 'publishing' and available_at < :older_than
                    """
                ),
                {"older_than": older_than},
            )
            return int(result.rowcount or 0)


class CeleryTaskPublisher:
    """Map durable event types to stable Celery task names."""

    TASK_BY_EVENT: ClassVar[dict[str, str]] = {
        "document.ingest.requested": "researchmate.ingest_document",
        "document.delete.requested": "researchmate.delete_document",
        "project.delete.requested": "researchmate.delete_project",
        "workflow.run.requested": "researchmate.run_workflow",
        "workflow.resume.requested": "researchmate.run_workflow",
        "evaluation.run.requested": "researchmate.run_evaluation",
        "fault.exercise.requested": "researchmate.run_fault_simulation",
    }

    def __init__(
        self, celery_app: Any, queue: str = "ingestion"
    ) -> None:  # boundary: Celery SDK app instance, Celery docs type it as Any
        self.celery_app = celery_app
        self.queue = queue

    def publish(self, event: ClaimedOutboxEvent) -> None:
        task_name = self.TASK_BY_EVENT.get(event.event_type)
        if task_name is None:
            raise ValueError("unsupported_outbox_event")
        if event.event_type in {"document.delete.requested", "project.delete.requested"}:
            queue = "deletion"
        elif event.event_type.startswith("workflow."):
            queue = "workflow"
        elif event.event_type.startswith("evaluation."):
            queue = "evaluation"
        elif event.event_type.startswith("fault."):
            queue = "reliability"
        else:
            queue = self.queue
        self.celery_app.send_task(
            task_name,
            kwargs={"event": event.payload},
            task_id=event.idempotency_key,
            queue=queue,
        )
