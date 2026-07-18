from __future__ import annotations

import argparse
import time

from sqlalchemy import create_engine

from researchmate_worker.celery_app import celery_app
from researchmate_worker.config import WorkerSettings
from researchmate_worker.outbox import CeleryTaskPublisher, OutboxDispatcher, SqlOutboxStore
from researchmate_worker.runtime_health import record_heartbeat


def build_dispatcher(settings: WorkerSettings) -> OutboxDispatcher:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required to dispatch outbox events")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return OutboxDispatcher(
        SqlOutboxStore(engine),
        CeleryTaskPublisher(celery_app, queue=settings.ingestion_queue),
        batch_size=settings.outbox_batch_size,
        max_attempts=settings.outbox_max_attempts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch committed ResearchMate outbox events")
    parser.add_argument("--once", action="store_true", help="dispatch one batch and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = WorkerSettings()
    dispatcher = build_dispatcher(settings)
    dispatcher.recover_stale_claims()
    while True:
        record_heartbeat(
            dispatcher.store.engine,
            "dispatcher",
            metadata={"poll_seconds": max(0.25, args.poll_seconds)},
        )
        published = dispatcher.dispatch_once()
        if args.once:
            return
        if published == 0:
            time.sleep(max(0.25, args.poll_seconds))


if __name__ == "__main__":
    main()
