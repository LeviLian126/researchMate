from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# 验证项目初始化必须产出核心契约文件。
def test_required_contract_files_exist() -> None:
    required_paths = [
        ".gitignore",
        ".env.example",
        "README.md",
        "docs/index.html",
        "docs/progress.html",
        "docs/progress-backend.html",
        "docs/progress-frontend.html",
        "docs/progress-ops.html",
        "docs/api-spec.html",
        "docs/db-schema.html",
        "docs/ui-page-spec.html",
        "docs/execution-plan.html",
        "docs/researchmate-prd.html",
        "docs/researchmate-architecture.html",
        "docs/project-development-process.html",
        "docs/openapi-spec.html",
        "infra/openapi/openapi.yaml",
        "infra/supabase/migrations/202605260001_initial_schema.sql",
        "packages/shared/src/contracts.ts",
        "apps/api/src/researchmate_api/main.py",
        "docs/handoff/index.html",
        "docs/handoff/context-state.json",
    ]

    missing = [path for path in required_paths if not (ROOT / path).exists()]

    assert missing == []


# 验证 OpenAPI 契约覆盖 MVP 必须接口。
def test_openapi_contract_declares_mvp_routes() -> None:
    spec = (ROOT / "infra/openapi/openapi.yaml").read_text(encoding="utf-8")
    required_routes = [
        "/api/v1/me",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
        "/api/v1/documents/upload-url",
        "/api/v1/documents",
        "/api/v1/projects/{project_id}/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/jobs/{job_id}",
        "/api/v1/ask",
        "/api/v1/quiz",
        "/api/v1/runs/{run_id}/sources",
        "/api/v1/dev/traces/{trace_id}",
        "/api/v1/healthz",
    ]

    for route in required_routes:
        assert route in spec

    assert "bearerAuth" in spec
    assert "ErrorResponse" in spec


# 验证 docs 目录不再保留 Markdown 文档。
def test_docs_do_not_contain_markdown_files() -> None:
    markdown_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.md"))

    assert markdown_files == []


# 验证 HTML 文档没有被 Windows 代码页写成问号乱码。
def test_docs_html_do_not_contain_question_mark_garbled_text() -> None:
    html_files = sorted(path for path in (ROOT / "docs").rglob("*.html"))
    garbled_files = [
        path.relative_to(ROOT).as_posix()
        for path in html_files
        if "??" in path.read_text(encoding="utf-8")
    ]

    assert garbled_files == []


# 验证数据库迁移包含用户隔离、状态枚举和安全策略骨架。
def test_database_schema_has_security_boundaries() -> None:
    migration = (
        ROOT / "infra/supabase/migrations/202605260001_initial_schema.sql"
    ).read_text(encoding="utf-8")
    required_tokens = [
        "create table if not exists profiles",
        "create table if not exists projects",
        "create table if not exists documents",
        "create table if not exists chunks",
        "create table if not exists ask_runs",
        "create table if not exists quiz_sets",
        "create table if not exists jobs",
        "alter table projects enable row level security",
        "owner_user_id",
        "idx_chunks_user_project_source",
    ]

    for token in required_tokens:
        assert token in migration


# 验证共享类型固定 Mode、Task 与输出 Schema 边界。
def test_shared_contracts_define_core_modes_and_outputs() -> None:
    contracts = (ROOT / "packages/shared/src/contracts.ts").read_text(encoding="utf-8")
    required_tokens = [
        "SourceMode",
        "TaskType",
        "GroundedAnswer",
        "QuizSet",
        "ExecutionPlan",
        "local_only",
        "web_only",
        "hybrid",
    ]

    for token in required_tokens:
        assert token in contracts


# 验证后端 schema 可以被导入并执行基础请求校验。
def test_backend_pydantic_contracts_validate_request_shape() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from researchmate_api.schemas.ask import AskRequest

    request = AskRequest(
        project_id="00000000-0000-4000-8000-000000000001",
        message="/study explain RAG",
        selected_mode="auto",
    )

    assert request.selected_mode == "auto"
