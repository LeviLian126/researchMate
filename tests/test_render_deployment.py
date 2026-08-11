"""Verify Render deployment configuration and combined-runtime startup order."""

# Verifies that the Render blueprint and image stay within the combined free-tier boundary.
from __future__ import annotations

from pathlib import Path

from researchmate_worker import render_combined
from researchmate_worker.render_combined import child_commands

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_one_shared_free_service_and_secret_prompts() -> None:
    """Keep every Python process inside one sleeping Render Free web service."""
    source = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert source.count("type: web") == 1
    assert source.count("plan: free") == 1
    assert "researchmate-backend-dev" in source
    assert "dockerCommand: python -m researchmate_worker.render_combined" in source
    assert "buildFilter:" in source
    for backend_path in (
        "apps/api/**",
        "workers/ai-worker/**",
        "infra/supabase/migrations/**",
        "uv.lock",
    ):
        assert f"- {backend_path}" in source
    for secret in (
        "DATABASE_URL",
        "REDIS_URL",
        "OBJECT_STORAGE_ACCESS_KEY_ID",
        "OBJECT_STORAGE_SECRET_ACCESS_KEY",
        "QDRANT_API_KEY",
        "NVIDIA_API_KEY",
        "TAVILY_API_KEY",
        "LANGFUSE_SECRET_KEY",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
    ):
        assert f"key: {secret}\n        sync: false" in source
    assert "value: https://cloud.langfuse.com/api/public/otel/v1/traces" in source
    assert "NVIDIA_INPUT_COST_PER_MILLION_USD" not in source
    assert "NVIDIA_OUTPUT_COST_PER_MILLION_USD" not in source


def test_worker_image_copies_hybrid_replay_script() -> None:
    """Keep the opt-in native-hybrid replay executable in the Render runtime image."""
    source = (ROOT / "workers" / "ai-worker" / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "COPY scripts/provision_qdrant_hybrid.py /app/scripts/provision_qdrant_hybrid.py" in source
    )


def test_nvidia_free_endpoint_has_no_runtime_price_fields() -> None:
    """Keep free NVIDIA endpoint configuration free of runtime price fields."""
    config_source = (
        ROOT / "workers" / "ai-worker" / "src" / "researchmate_worker" / "config.py"
    ).read_text(encoding="utf-8")
    tasks_source = (
        ROOT / "workers" / "ai-worker" / "src" / "researchmate_worker" / "task_builders.py"
    ).read_text(encoding="utf-8")
    assert "nvidia_input_cost_per_million_usd" not in config_source
    assert "nvidia_output_cost_per_million_usd" not in config_source
    assert "input_price_per_million_usd=Decimal(0)" in tasks_source
    assert "output_price_per_million_usd=Decimal(0)" in tasks_source


def test_render_runtime_starts_api_worker_dispatcher_and_heartbeat() -> None:
    """Start the public API and every supervised worker-side process together."""
    commands = child_commands(10000)
    assert len(commands) == 4
    assert "uvicorn" in commands[0]
    assert "researchmate_api.main:app" in commands[0]
    assert "celery" in commands[1]
    assert "--pool=solo" in commands[1]
    assert commands[2][-1] == "researchmate_worker.dispatch_outbox"
    assert commands[3][-1] == "researchmate_worker.worker_heartbeat"


def test_combined_runtime_waits_for_api_health_before_heavy_workers(monkeypatch) -> None:
    """Start heavy workers only after the API answers its HTTP health endpoint."""

    class FakeProcess:
        def poll(self) -> int | None:
            return None

    class Response:
        status: int = 200

    class Connection:
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            calls.append((host, port, timeout))

        def request(self, method: str, path: str) -> None:
            requests.append((method, path))

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            closed.append(True)

    calls, requests, closed = [], [], []

    monkeypatch.setattr(render_combined, "HTTPConnection", Connection)

    assert render_combined.wait_for_api(FakeProcess(), 10000, timeout_seconds=1) is True
    assert calls == [("127.0.0.1", 10000, 0.5)]
    assert requests == [("GET", "/api/v1/healthz")]
    assert closed == [True]


def test_render_image_uses_cpu_only_pytorch() -> None:
    """Prevent CUDA wheels from exhausting free-tier build and runtime resources."""
    source = (ROOT / "workers" / "ai-worker" / "Dockerfile").read_text(encoding="utf-8")
    worker_project = (ROOT / "workers" / "ai-worker" / "pyproject.toml").read_text(encoding="utf-8")
    workspace = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pytorch-cpu" in workspace
    assert "https://download.pytorch.org/whl/cpu" in workspace
    assert "torch==2.13.0+cpu" in worker_project
    assert "torchvision==0.28.0+cpu" in worker_project
    assert "uv sync --frozen" in source
