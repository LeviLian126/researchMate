from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence

QUEUES = "ingestion,deletion,workflow,evaluation,reliability"


def apply_schema_migrations() -> None:
    """Apply repository migrations before any process can observe the new schema."""
    if os.getenv("RUN_SCHEMA_MIGRATIONS") != "1":
        return
    environment = {**os.environ, "ALLOW_SCHEMA_APPLY": "1"}
    subprocess.run(
        [sys.executable, "/app/scripts/apply_migrations.py", "--apply"],
        check=True,
        env=environment,
    )


def backfill_qdrant_rerank() -> None:
    """Build and verify the free multivector projection before starting traffic."""
    if os.getenv("RUN_QDRANT_RERANK_BACKFILL") != "1":
        return
    environment = {
        **os.environ,
        "ALLOW_QDRANT_RERANK_BACKFILL": "1",
    }
    subprocess.run(
        [sys.executable, "/app/scripts/provision_qdrant_rerank.py"],
        check=True,
        env=environment,
    )


def child_commands(port: int) -> list[list[str]]:
    return [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "researchmate_api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--proxy-headers",
        ],
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "researchmate_worker.celery_app:celery_app",
            "worker",
            "--loglevel=INFO",
            f"--queues={QUEUES}",
            "--pool=solo",
            "--concurrency=1",
        ],
        [sys.executable, "-m", "researchmate_worker.dispatch_outbox"],
    ]


def stop_children(children: Sequence[subprocess.Popen[bytes]], signum: int) -> None:
    for child in children:
        if child.poll() is None:
            child.send_signal(signum)


def run(port: int) -> int:
    apply_schema_migrations()
    backfill_qdrant_rerank()
    children = [subprocess.Popen(command) for command in child_commands(port)]

    def forward(signum: int, _frame: object) -> None:
        stop_children(children, signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    stop_children(children, signal.SIGTERM)
                    return code or 1
            time.sleep(0.5)
    finally:
        stop_children(children, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()


def main() -> None:
    raise SystemExit(run(int(os.getenv("PORT", "10000"))))


if __name__ == "__main__":
    main()
