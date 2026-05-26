from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# 验证前端 MVP 页面已经覆盖项目、问答、资料库、测验和开发者 Trace。
def test_frontend_mvp_pages_exist() -> None:
    required_pages = [
        "apps/web/app/page.tsx",
        "apps/web/app/app/page.tsx",
        "apps/web/app/app/projects/[projectId]/page.tsx",
        "apps/web/app/app/projects/[projectId]/library/page.tsx",
        "apps/web/app/app/projects/[projectId]/quiz/page.tsx",
        "apps/web/app/dev/traces/[traceId]/page.tsx",
        "apps/web/app/lib/api.ts",
        "apps/web/app/globals.css",
    ]

    missing = [path for path in required_pages if not (ROOT / path).exists()]

    assert missing == []


# 验证前端页面连接当前 API 契约中的核心路由。
def test_frontend_calls_mvp_api_contracts() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "apps/web/app/app/page.tsx",
            ROOT / "apps/web/app/app/projects/[projectId]/page.tsx",
            ROOT / "apps/web/app/app/projects/[projectId]/library/page.tsx",
            ROOT / "apps/web/app/app/projects/[projectId]/quiz/page.tsx",
            ROOT / "apps/web/app/dev/traces/[traceId]/page.tsx",
            ROOT / "apps/web/app/lib/api.ts",
        ]
    )
    required_tokens = [
        "NEXT_PUBLIC_API_BASE_URL",
        "Authorization",
        "Bearer",
        "/projects",
        "/documents/upload-url",
        "extracted_text",
        "/ask",
        "/quiz",
        "/dev/traces/",
    ]

    for token in required_tokens:
        assert token in source


# 验证普通应用导航不暴露 Developer Trace 入口。
def test_regular_project_pages_do_not_nav_to_dev_trace() -> None:
    regular_pages = [
        ROOT / "apps/web/app/app/page.tsx",
        ROOT / "apps/web/app/app/projects/[projectId]/library/page.tsx",
        ROOT / "apps/web/app/app/projects/[projectId]/quiz/page.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in regular_pages)

    assert "/dev/traces/" not in combined


# 验证前端代码不引用后端 secret 名称，避免误导部署到浏览器环境。
def test_frontend_does_not_reference_backend_secret_names() -> None:
    frontend_files = list((ROOT / "apps/web/app").rglob("*.tsx")) + list((ROOT / "apps/web/app").rglob("*.ts"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in frontend_files)
    forbidden_tokens = [
        "SUPABASE_SERVICE_ROLE_KEY",
        "R2_SECRET_ACCESS_KEY",
        "NVIDIA_API_KEY",
        "SERPER_API_KEY",
        "TAVILY_API_KEY",
        "JINA_API_KEY",
        "FIRECRAWL_API_KEY",
    ]

    for token in forbidden_tokens:
        assert token not in combined
