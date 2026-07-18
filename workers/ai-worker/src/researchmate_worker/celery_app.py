from celery import Celery
from celery.signals import heartbeat_sent, worker_ready, worker_shutdown
from functools import lru_cache
import logging
from sqlalchemy import create_engine
from time import monotonic

from researchmate_worker.config import WorkerSettings


def create_celery_app(settings: WorkerSettings | None = None) -> Celery:
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
            "researchmate.run_workflow": {"queue": "workflow"},
            "researchmate.run_evaluation": {"queue": "evaluation"},
            "researchmate.run_fault_simulation": {"queue": "reliability"},
        },
    )
    return app


celery_app = create_celery_app()
_last_heartbeat = 0.0
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _heartbeat_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def _worker_heartbeat(status: str) -> None:
    global _last_heartbeat
    runtime = WorkerSettings()
    if not runtime.database_url:
        return
    now = monotonic()
    if status == "ready" and now - _last_heartbeat < runtime.runtime_heartbeat_seconds:
        return
    from researchmate_worker.runtime_health import record_heartbeat

    record_heartbeat(
        _heartbeat_engine(runtime.database_url),
        "worker",
        status=status,
        metadata={"queues": "ingestion,deletion,workflow,evaluation,reliability"},
    )
    _last_heartbeat = now


@worker_ready.connect
def _on_worker_ready(**_kwargs) -> None:
    try:
        _worker_heartbeat("ready")
    except Exception:
        logger.exception("worker readiness heartbeat failed")


@heartbeat_sent.connect
def _on_worker_heartbeat(**_kwargs) -> None:
    try:
        _worker_heartbeat("ready")
    except Exception:
        logger.exception("worker heartbeat failed")


@worker_shutdown.connect
def _on_worker_shutdown(**_kwargs) -> None:
    try:
        _worker_heartbeat("stopping")
    except Exception:
        logger.exception("worker shutdown heartbeat failed")
