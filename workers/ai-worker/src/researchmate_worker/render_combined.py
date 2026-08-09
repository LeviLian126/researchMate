"""Supervise API, worker, and dispatcher child processes for the combined deployment."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from http.client import HTTPConnection

QUEUES = "ingestion,deletion,workflow,evaluation,reliability"

# INFRA-3: graceful-shutdown window must exceed the worker soft time limit (840s) so a
# task mid-flight is not SIGKILLed before it can checkpoint. We keep a 60s buffer under
# the hard 900s ceiling so the supervisor still reaps children before the platform does.
GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 840


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


def backfill_qdrant_hybrid() -> None:
    """Run the explicitly enabled native-hybrid replay before accepting traffic."""
    if os.getenv("RUN_QDRANT_HYBRID_BACKFILL") != "1":
        return
    environment = {
        **os.environ,
        "ALLOW_QDRANT_HYBRID_BACKFILL": "1",
    }
    subprocess.run(
        [sys.executable, "/app/scripts/provision_qdrant_hybrid.py"],
        check=True,
        env=environment,
    )


def child_commands(port: int) -> list[list[str]]:
    """Declare the supervised API, Celery, and dispatcher commands."""
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
            # INFRA-3: align uvicorn's graceful shutdown with the supervisor's wait window
            # so in-flight API requests and the MCP session get the full soft-time budget
            # to drain instead of being torn down by the default 20s.
            f"--timeout-graceful-shutdown={GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS}",
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
    """Terminate every supervised child within a bounded shutdown window."""
    for child in children:
        if child.poll() is None:
            child.send_signal(signum)


def wait_for_api(
    api_process: subprocess.Popen[bytes],
    port: int,
    *,
    timeout_seconds: float = 240,
) -> bool:
    """Wait for an actual successful API health response before starting workers."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if api_process.poll() is not None:
            return False
        connection = HTTPConnection("127.0.0.1", port, timeout=0.5)
        try:
            connection.request("GET", "/api/v1/healthz")
            response = connection.getresponse()
            if response.status == 200:
                return True
        except (OSError, TimeoutError):
            time.sleep(0.25)
        finally:
            connection.close()
    return False


def run(port: int) -> int:
    """Supervise combined deployment processes and propagate child failures."""
    apply_schema_migrations()
    backfill_qdrant_rerank()
    backfill_qdrant_hybrid()
    commands = child_commands(port)
    children: list[subprocess.Popen[bytes]] = []

    def forward(signum: int, _frame: object) -> None:
        stop_children(children, signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        api_process = subprocess.Popen(commands[0])
        children.append(api_process)
        if not wait_for_api(api_process, port):
            return api_process.poll() or 1
        children.extend(subprocess.Popen(command) for command in commands[1:])
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
                child.wait(timeout=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()


def main() -> None:
    """Validate the configured port and start the combined process supervisor."""
    raise SystemExit(run(int(os.getenv("PORT", "10000"))))


if __name__ == "__main__":
    main()
