from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_contract_files_exist() -> None:
    required_paths = [
        ".gitignore",
        ".env.example",
        "README.md",
        "docs/index.html",
        "docs/assets/site.css",
        "docs/product/index.html",
        "docs/architecture/index.html",
        "docs/contracts/data/index.html",
        "docs/contracts/api/index.html",
        "infra/openapi/openapi.yaml",
        "infra/supabase/migrations/202605260001_initial_schema.sql",
        "infra/supabase/migrations/202607160006_runtime_readiness_and_workflow_budget.sql",
        "packages/shared/src/contracts.ts",
        "apps/api/src/researchmate_api/main.py",
    ]

    missing = [path for path in required_paths if not (ROOT / path).exists()]
    assert missing == []


def test_docs_local_links_resolve() -> None:
    from html.parser import HTMLParser
    from urllib.parse import unquote, urldefrag

    class LinkParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.links: list[str] = []
            self.ids: set[str] = set()

        def handle_starttag(self, _: str, attrs: list[tuple[str, str | None]]) -> None:
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)
                if name == "id" and value:
                    self.ids.add(value)

    broken_links: list[str] = []
    for html_file in sorted((ROOT / "docs").rglob("*.html")):
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for href in parser.links:
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            path, fragment = urldefrag(href)
            target = (html_file.parent / unquote(path)).resolve() if path else html_file.resolve()
            if not target.exists():
                broken_links.append(f"{html_file.relative_to(ROOT).as_posix()} -> {href}")
                continue
            if fragment and target.suffix == ".html":
                target_parser = LinkParser()
                target_parser.feed(target.read_text(encoding="utf-8"))
                if unquote(fragment) not in target_parser.ids:
                    broken_links.append(
                        f"{html_file.relative_to(ROOT).as_posix()} -> {href} (missing fragment)"
                    )

    assert broken_links == []


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
        "/api/v1/readyz",
    ]

    for route in required_routes:
        assert route in spec

    assert "HTTPBearer" in spec
    assert "ErrorResponse" in spec


def test_docs_use_english_html_without_separate_planning_markdown() -> None:
    markdown_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.md"))
    assert markdown_files == []

    html_files = sorted((ROOT / "docs").rglob("*.html"))
    assert html_files
    for html_file in html_files:
        source = html_file.read_text(encoding="utf-8")
        assert '<html lang="en">' in source
        assert "ResearchMate documentation" in source


def test_docs_have_five_page_information_architecture() -> None:
    html_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.html"))
    assert html_files == [
        "docs/architecture/index.html",
        "docs/contracts/api/index.html",
        "docs/contracts/data/index.html",
        "docs/index.html",
        "docs/product/index.html",
    ]

    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in html_files)
    for retired in ("delivery/index.html", "operations/index.html", "activity/index.html", "todo.md"):
        assert retired not in combined


def test_database_and_api_docs_reconcile_complete_source_contracts() -> None:
    import re

    migration = (ROOT / "infra/supabase/migrations/202605260001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    data_docs = (ROOT / "docs/contracts/data/index.html").read_text(encoding="utf-8")
    migration_tables = set(
        re.findall(r"(?im)^create table if not exists\s+([a-z_]+)", migration)
    )
    documented_tables = set(
        re.findall(r'<details id="[^"]+"><summary><code>([a-z_]+)</code>', data_docs)
    )
    assert len(migration_tables) == 15
    assert documented_tables == migration_tables

    spec = (ROOT / "infra/openapi/openapi.yaml").read_text(encoding="utf-8")
    spec_operations: set[tuple[str, str]] = set()
    current_path: str | None = None
    for line in spec.splitlines():
        path_match = re.match(r"^  (/api/v1/[^:]+):$", line)
        if path_match:
            current_path = path_match.group(1)
            continue
        method_match = re.match(r"^    (get|post|put|patch|delete):$", line)
        if current_path and method_match:
            spec_operations.add((method_match.group(1).upper(), current_path))

    api_docs = (ROOT / "docs/contracts/api/index.html").read_text(encoding="utf-8")
    documented_operations = set(
        re.findall(r"<code>(GET|POST|PUT|PATCH|DELETE) (/api/v1/[^<]+)</code> —", api_docs)
    )
    assert len(spec_operations) == 35
    assert documented_operations == spec_operations


def test_overview_deep_links_to_authoritative_detail_sections() -> None:
    overview = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    expected_links = [
        "product/index.html#cap-projects",
        "product/index.html#cap-documents",
        "product/index.html#cap-grounded-ask",
        "product/index.html#cap-source-routing",
        "product/index.html#cap-sources",
        "product/index.html#cap-quiz",
        "architecture/index.html#current-architecture",
        "architecture/index.html#target-architecture",
        "architecture/index.html#stack",
        "contracts/data/index.html#tables",
        "contracts/api/index.html#operations",
    ]
    for href in expected_links:
        assert f'href="{href}"' in overview


def test_docs_have_unique_ids_and_one_page_title() -> None:
    import re

    for html_file in sorted((ROOT / "docs").rglob("*.html")):
        source = html_file.read_text(encoding="utf-8")
        ids = re.findall(r'\bid="([^"]+)"', source)
        assert len(ids) == len(set(ids)), html_file.relative_to(ROOT).as_posix()
        assert len(re.findall(r"<h1(?:\s|>)", source)) == 1


def test_quality_scripts_do_not_reference_legacy_handoff_docs() -> None:
    checked_files = [
        ROOT / "package.json",
        ROOT / "scripts/check_contracts.ps1",
        ROOT / "scripts/repair_docs_html_encoding.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_files)
    legacy_tokens = [
        "validate_context_dashboard.py",
        "docs/handoff",
        "handoff/assets",
        "progress.html",
    ]
    for token in legacy_tokens:
        assert token not in combined


def test_docs_html_do_not_contain_question_mark_garbled_text() -> None:
    html_files = sorted(path for path in (ROOT / "docs").rglob("*.html"))
    garbled_files = [
        path.relative_to(ROOT).as_posix()
        for path in html_files
        if "??" in path.read_text(encoding="utf-8")
    ]
    assert garbled_files == []


def test_database_schema_has_security_boundaries() -> None:
    migration = (ROOT / "infra/supabase/migrations/202605260001_initial_schema.sql").read_text(encoding="utf-8")
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
