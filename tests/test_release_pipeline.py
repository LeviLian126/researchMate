"""Verify release automation, container, migration, and secret-safety contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_the_full_test_build_contract_and_security_gate() -> None:
    """Require CI to run the full test, build, and security gates."""
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert '"test": "npm run test:python && npm run test:web"' in package
    assert '"test:python": "uv run --frozen coverage run --branch' in package
    assert "coverage report --fail-under=69" in package
    assert '"test:web": "npm --workspace @researchmate/web run test"' in package
    assert '"test:e2e": "npm --workspace @researchmate/web run test:e2e"' in package
    assert "scripts/export_openapi.py --check" in package
    assert "scripts/apply_migrations.py --check-files" in package
    assert "npx --yes pyright@1.1.390" in package
    assert "npm install" in workflow
    for job in ("python-quality", "web-quality", "browser-e2e", "container-quality", "ci-success"):
        assert f"{job}:" in workflow
    assert "uv sync --frozen --all-packages --group dev" in workflow
    assert "npx --yes pyright@1.1.390" in package
    assert "continue-on-error: true" in workflow
    assert "npx playwright install --with-deps chromium" in workflow
    assert "hadolint/hadolint:v2.15.1-debian" in workflow
    assert "aquasec/trivy:0.73.0" in workflow
    assert "target: dependencies" in workflow
    assert "researchmate-worker-dependencies:ci" in workflow
    assert "permissions:\n      contents: read" in workflow
    assert "continue-on-error: true" in workflow


def test_python_dependency_graph_is_locked_for_ci_and_images() -> None:
    """Require one frozen dependency graph across local, CI, and container installs."""
    workspace = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    api_image = (ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")
    worker_image = (ROOT / "workers/ai-worker/Dockerfile").read_text(encoding="utf-8")

    assert "[tool.uv.workspace]" in workspace
    assert 'members = ["apps/api", "workers/ai-worker"]' in workspace
    assert 'name = "researchmate-api"' in lock
    assert 'name = "researchmate-ai-worker"' in lock
    assert not (ROOT / "requirements-dev.txt").exists()
    assert "uv sync --frozen --no-dev --package researchmate-api" in api_image
    assert "uv sync --frozen --no-dev --all-packages" in worker_image


def test_retired_delivery_paths_are_inert_and_cloudflare_sources_are_archived() -> None:
    """Keep retired release paths inert and archived."""
    active_workflows = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".github/workflows").glob("*.yml")
    )
    web_package = (ROOT / "apps/web/package.json").read_text(encoding="utf-8")
    package_lock = (ROOT / "package-lock.json").read_text(encoding="utf-8")
    archive = ROOT / "docs/archive/cloudflare"

    assert "cloudflare" not in active_workflows.lower()
    assert "generate chinese documentation" not in active_workflows.lower()
    assert not (ROOT / ".github/workflows/release.yml").exists()
    assert not (ROOT / ".github/workflows/translate-docs.yml").exists()
    assert not (ROOT / "scripts/generate_zh_docs.py").exists()
    assert not (ROOT / "docs/zh").exists()
    assert not (ROOT / "apps/web/open-next.config.ts").exists()
    assert not (ROOT / "apps/web/wrangler.jsonc").exists()
    assert "opennextjs-cloudflare" not in web_package
    assert "wrangler" not in web_package.lower()
    assert "node_modules/@opennextjs/cloudflare" not in package_lock
    assert "node_modules/wrangler" not in package_lock

    release_snapshot = (archive / "release-workflow.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in release_snapshot
    assert "CLOUDFLARE_API_TOKEN" in release_snapshot
    assert "wrangler deploy --config wrangler.jsonc" in release_snapshot
    for name in (
        "release-workflow.yml",
        "open-next.config.ts",
        "wrangler.jsonc",
        "web-package-fragment.json",
    ):
        assert (archive / name).is_file()


def test_container_images_are_non_root_and_worker_prefetches_pdf_models() -> None:
    """Require non-root images and deterministic worker model prefetch."""
    api = (ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "workers/ai-worker/Dockerfile").read_text(encoding="utf-8")

    assert "USER 10001:10001" in api
    assert "HEALTHCHECK" in api
    assert "USER 10001:10001" in worker
    assert "uv.lock" in api
    assert "uv.lock" in worker
    assert "docling-tools models download layout tableformer rapidocr" in worker
    assert "DOCLING_ARTIFACTS_PATH=/opt/docling/models" in worker
    assert "RESEARCHMATE_PROCESS_ROLE:-worker" in worker


def test_migration_runner_requires_approval_lock_and_checksum() -> None:
    """Require migration approval, serialization, and checksum tracking."""
    source = (ROOT / "scripts/apply_migrations.py").read_text(encoding="utf-8")

    assert 'os.getenv("ALLOW_SCHEMA_APPLY") != "1"' in source
    assert "pg_advisory_xact_lock" in source
    assert "checksum_sha256" in source
    assert "Applied migration checksum changed" in source


def test_repository_sources_do_not_contain_provider_secrets() -> None:
    """Prevent provider credentials from entering tracked sources."""
    roots = [ROOT / "apps", ROOT / "workers", ROOT / "scripts", ROOT / ".github", ROOT / "docs"]
    suspicious: list[str] = []
    for base in roots:
        for path in base.rglob("*"):
            if not path.is_file() or any(
                part in {".next", "build", "__pycache__"} for part in path.parts
            ):
                continue
            if path.suffix.lower() not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".json",
                ".yml",
                ".yaml",
                ".html",
                ".css",
            }:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            if "nvapi-" in source or "-----BEGIN PRIVATE KEY-----" in source:
                suspicious.append(path.relative_to(ROOT).as_posix())
    assert suspicious == []


def test_web_release_sets_baseline_browser_security_headers() -> None:
    """Require baseline browser security headers in the web release."""
    config = (ROOT / "apps/web/next.config.ts").read_text(encoding="utf-8")

    for header in (
        "Content-Security-Policy",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
    ):
        assert header in config
    assert "frame-ancestors 'none'" in config
    assert "object-src 'none'" in config
    assert 'source: "/docs", destination: "/docs/index.html"' not in config
