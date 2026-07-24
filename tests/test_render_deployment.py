from pathlib import Path

from researchmate_worker.render_combined import child_commands

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_one_shared_free_service_and_secret_prompts() -> None:
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
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    ):
        assert f"key: {secret}\n        sync: false" in source


def test_render_runtime_starts_api_worker_and_dispatcher() -> None:
    commands = child_commands(10000)
    assert len(commands) == 3
    assert "uvicorn" in commands[0]
    assert "researchmate_api.main:app" in commands[0]
    assert "celery" in commands[1]
    assert "--pool=solo" in commands[1]
    assert commands[2][-1] == "researchmate_worker.dispatch_outbox"
