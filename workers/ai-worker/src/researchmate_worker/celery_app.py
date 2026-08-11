"""Configure the worker process and task discovery."""

from __future__ import annotations

from celery import Celery

from researchmate_worker.config import WorkerSettings


def create_celery_app(settings: WorkerSettings | None = None) -> Celery:
    """Create the worker application without contacting its managed dependencies."""
    runtime = settings or WorkerSettings()
    broker_url = runtime.redis_url or "memory://"
    app = Celery("researchmate_worker", broker=broker_url, include=["researchmate_worker.tasks"])
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        task_soft_time_limit=runtime.worker_soft_time_limit_seconds,
        task_time_limit=runtime.worker_time_limit_seconds,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": runtime.worker_time_limit_seconds * 2},
        task_routes={
            "researchmate.ingest_document": {"queue": runtime.ingestion_queue},
            "researchmate.delete_document": {"queue": "deletion"},
            "researchmate.delete_project": {"queue": "deletion"},
            "researchmate.run_workflow": {"queue": "workflow"},
            "researchmate.run_evaluation": {"queue": "evaluation"},
            "researchmate.run_fault_simulation": {"queue": "reliability"},
        },
    )
    return app


celery_app = create_celery_app()
