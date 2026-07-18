from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_the_full_test_build_contract_and_security_gate() -> None:
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert '"test": "python -m pytest -q"' in package
    assert "scripts/export_openapi.py --check" in package
    assert "scripts/apply_migrations.py --check-files" in package
    assert "npm ci" in workflow
    assert "npm run check:all" in workflow
    assert "bash -n scripts/provision_azure_container_apps.sh" in workflow
    assert "permissions:\n      contents: read" in workflow


def test_release_is_manual_protected_and_uses_immutable_images() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "environment: ${{ inputs.environment }}" in workflow
    assert "id-token: write" in workflow
    assert "${{ github.sha }}" in workflow
    assert "ALLOW_SCHEMA_APPLY: \"1\"" in workflow
    assert "scripts/apply_migrations.py --apply" in workflow
    assert "scripts/setup_langgraph_checkpoint.py" in workflow
    assert "/api/v1/healthz" in workflow
    assert "/api/v1/readyz" in workflow
    assert '"$WEB_BASE_URL/"' in workflow
    assert '"$WEB_BASE_URL/docs/"' not in workflow
    assert "AZURE_DISPATCHER_APP" in workflow
    assert "scripts/provision_azure_container_apps.sh" in workflow
    assert "AZURE_CONTAINERAPPS_ENVIRONMENT" in workflow
    assert "OBJECT_STORAGE_SECRET_ACCESS_KEY" in workflow
    assert "NEXT_PUBLIC_API_BASE_URL" in workflow
    assert "provision_azure_container_apps.sh --check" in workflow
    assert "push:" not in workflow.split("jobs:", 1)[0]


def test_azure_reconciler_creates_a_no_log_environment_and_uses_secret_references() -> None:
    script = (ROOT / "scripts/provision_azure_container_apps.sh").read_text(encoding="utf-8")

    assert "az containerapp env create" in script
    assert "--logs-destination none" in script
    assert "az containerapp secret set" in script
    assert "secretref:database-url" in script
    assert "RESEARCHMATE_PROCESS_ROLE=$role" in script
    assert "--min-replicas 1" in script
    assert "API_HEALTH_URL=https://$api_fqdn" in script
    assert '"${1:-}" == "--check"' in script


def test_container_images_are_non_root_and_worker_prefetches_pdf_models() -> None:
    api = (ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "workers/ai-worker/Dockerfile").read_text(encoding="utf-8")

    assert "USER researchmate" in api
    assert "HEALTHCHECK" in api
    assert "USER researchmate" in worker
    assert "docling-tools models download layout tableformer rapidocr" in worker
    assert "DOCLING_ARTIFACTS_PATH=/opt/docling/models" in worker
    assert "RESEARCHMATE_PROCESS_ROLE:-worker" in worker


def test_migration_runner_requires_approval_lock_and_checksum() -> None:
    source = (ROOT / "scripts/apply_migrations.py").read_text(encoding="utf-8")

    assert 'os.getenv("ALLOW_SCHEMA_APPLY") != "1"' in source
    assert "pg_advisory_xact_lock" in source
    assert "checksum_sha256" in source
    assert "Applied migration checksum changed" in source


def test_repository_sources_do_not_contain_provider_secrets() -> None:
    roots = [ROOT / "apps", ROOT / "workers", ROOT / "scripts", ROOT / ".github", ROOT / "docs"]
    suspicious: list[str] = []
    for base in roots:
        for path in base.rglob("*"):
            if not path.is_file() or any(part in {".next", "build", "__pycache__"} for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".html", ".css"}:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            if "nvapi-" in source or "-----BEGIN PRIVATE KEY-----" in source:
                suspicious.append(path.relative_to(ROOT).as_posix())
    assert suspicious == []


def test_web_release_sets_baseline_browser_security_headers() -> None:
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
