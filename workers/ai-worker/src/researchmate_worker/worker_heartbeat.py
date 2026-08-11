"""Publish worker liveness from a supervisor-managed companion process."""

from __future__ import annotations

import argparse
import time

from sqlalchemy import Engine, create_engine

from researchmate_worker.config import WorkerSettings, psycopg_database_url
from researchmate_worker.render_combined import QUEUES
from researchmate_worker.runtime_health import record_heartbeat

MINIMUM_HEARTBEAT_SECONDS = 10.0


def build_engine(settings: WorkerSettings) -> Engine:
    """Create one bounded connection pool for durable liveness writes."""
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required to publish worker heartbeats")
    return create_engine(
        psycopg_database_url(settings.database_url),
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=0,
    )


def main() -> None:
    """Refresh worker readiness while the supervisor keeps Celery alive."""
    parser = argparse.ArgumentParser(description="Publish ResearchMate worker liveness")
    parser.add_argument("--once", action="store_true", help="publish one heartbeat and exit")
    parser.add_argument("--interval-seconds", type=float)
    args = parser.parse_args()
    settings = WorkerSettings()
    engine = build_engine(settings)
    interval_seconds = max(
        MINIMUM_HEARTBEAT_SECONDS,
        args.interval_seconds or settings.runtime_heartbeat_seconds,
    )
    while True:
        record_heartbeat(
            engine,
            "worker",
            metadata={"queues": QUEUES},
        )
        if args.once:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
