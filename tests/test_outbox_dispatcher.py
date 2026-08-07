"""Verify outbox delivery outcomes and bounded worker routing."""

from uuid import UUID

from researchmate_worker.outbox import (
    CeleryTaskPublisher,
    ClaimedOutboxEvent,
    OutboxDispatcher,
)


class FakeStore:
    """Record outbox claim and delivery-state transitions."""

    def __init__(self, events):
        self.events = events
        self.published = []
        self.failed = []

    def claim(self, limit, max_attempts):
        assert (limit, max_attempts) == (10, 3)
        return self.events

    def mark_published(self, event_id):
        self.published.append(event_id)

    def mark_failed(self, event_id, attempts, safe_error):
        self.failed.append((event_id, attempts, safe_error))

    def requeue_stale(self, older_than):
        return 0


class FakePublisher:
    """Record published events and inject selected failures."""

    def __init__(self, failing_id=None):
        self.failing_id = failing_id
        self.events = []

    def publish(self, event):
        if event.id == self.failing_id:
            raise TimeoutError("provider detail must not be persisted")
        self.events.append(event)


def event(value: int) -> ClaimedOutboxEvent:
    """Create a representative claimed outbox event."""
    return ClaimedOutboxEvent(
        id=UUID(f"00000000-0000-4000-8000-{value:012d}"),
        event_type="document.ingest.requested",
        payload={"document_id": str(value)},
        idempotency_key=f"document:{value}:ingest:v1",
        attempts=1,
    )


def test_dispatcher_marks_each_publish_outcome_without_losing_the_batch() -> None:
    """Persist each event outcome while continuing through the batch."""
    first, second = event(1), event(2)
    store = FakeStore([first, second])
    publisher = FakePublisher(failing_id=first.id)
    dispatcher = OutboxDispatcher(store, publisher, batch_size=10, max_attempts=3)

    assert dispatcher.dispatch_once() == 1
    assert store.failed == [(first.id, 1, "TimeoutError")]
    assert store.published == [second.id]
    assert publisher.events == [second]


def test_fault_exercise_is_routed_to_bounded_reliability_worker() -> None:
    """Route fault exercises to the bounded reliability task."""

    class FakeCelery:
        def __init__(self):
            self.calls = []

        def send_task(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    celery = FakeCelery()
    publisher = CeleryTaskPublisher(celery)
    exercise = ClaimedOutboxEvent(
        id=UUID(int=20),
        event_type="fault.exercise.requested",
        payload={"exercise_id": str(UUID(int=21)), "requested_by": str(UUID(int=22))},
        idempotency_key="fault:user:key",
        attempts=1,
    )

    publisher.publish(exercise)

    args, kwargs = celery.calls[0]
    assert args == ("researchmate.run_fault_simulation",)
    assert kwargs["queue"] == "reliability"
    assert kwargs["task_id"] == "fault:user:key"


def test_project_deletion_is_routed_to_the_deletion_queue() -> None:
    """Route project deletion events to the deletion queue."""

    class FakeCelery:
        def __init__(self):
            self.calls = []

        def send_task(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    celery = FakeCelery()
    publisher = CeleryTaskPublisher(celery)
    deletion = ClaimedOutboxEvent(
        id=UUID(int=30),
        event_type="project.delete.requested",
        payload={"project_id": str(UUID(int=31))},
        idempotency_key="project:31:delete:v1",
        attempts=1,
    )

    publisher.publish(deletion)

    args, kwargs = celery.calls[0]
    assert args == ("researchmate.delete_project",)
    assert kwargs["queue"] == "deletion"
