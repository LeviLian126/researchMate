# Verifies that the Render blueprint and image stay within the combined free-tier boundary.
from pathlib import Path

from researchmate_worker.render_combined import child_commands

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_one_shared_free_service_and_secret_prompts() -> None:
    """Keep every Python process inside one sleeping Render Free web service."""
    source = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert source.count("type: web") == 1
    assert source.count("plan: free") == 1
    assert "researchmate-backend-dev" in source
    assert "dockerCommand: python -m researchmate_worker.render_combined" in source
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
    assert (
        "value: https://cloud.langfuse.com/api/public/otel/v1/traces"
        in source
    )
    assert "NVIDIA_INPUT_COST_PER_MILLION_USD" not in source
    assert "NVIDIA_OUTPUT_COST_PER_MILLION_USD" not in source


def test_nvidia_free_endpoint_has_no_runtime_price_fields() -> None:
    config_source = (
        ROOT / "workers" / "ai-worker" / "src" / "researchmate_worker" / "config.py"
    ).read_text(encoding="utf-8")
    tasks_source = (
        ROOT / "workers" / "ai-worker" / "src" / "researchmate_worker" / "tasks.py"
    ).read_text(encoding="utf-8")
    assert "nvidia_input_cost_per_million_usd" not in config_source
    assert "nvidia_output_cost_per_million_usd" not in config_source
    assert "input_price_per_million_usd=Decimal(0)" in tasks_source
    assert "output_price_per_million_usd=Decimal(0)" in tasks_source


def test_render_runtime_starts_api_worker_and_dispatcher() -> None:
    """Start the public API and both durable-delivery processes together."""
    commands = child_commands(10000)
    assert len(commands) == 3
    assert "uvicorn" in commands[0]
    assert "researchmate_api.main:app" in commands[0]
    assert "celery" in commands[1]
    assert "--pool=solo" in commands[1]
    assert commands[2][-1] == "researchmate_worker.dispatch_outbox"


def test_render_image_uses_cpu_only_pytorch() -> None:
    """Prevent CUDA wheels from exhausting free-tier build and runtime resources."""
    source = (ROOT / "workers" / "ai-worker" / "Dockerfile").read_text(encoding="utf-8")
    assert "https://download.pytorch.org/whl/cpu" in source
    assert "torch==2.13.0+cpu" in source
    assert "torchvision==0.28.0+cpu" in source
