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
        "apps/web/app/app/projects/[projectId]/labs/page.tsx",
        "apps/web/app/components/project-nav.tsx",
        "apps/web/app/components/state-notice.tsx",
        "apps/web/app/components/auth-gate.tsx",
        "apps/web/app/app/layout.tsx",
        "apps/web/app/dev/layout.tsx",
        "apps/web/app/lib/supabase.ts",
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
            ROOT / "apps/web/app/app/projects/[projectId]/labs/page.tsx",
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
        "/research-runs",
        "/runs/${runId}/events",
        "/decisions",
        "/claims",
        "/claim-relations",
        "/reports",
        "/refresh",
        "/evaluation-runs",
        "/dev/reliability",
        "/dev/fault-scenarios",
    ]

    for token in required_tokens:
        assert token in source


# 验证普通应用导航不暴露 Developer Trace 入口。
def test_regular_project_pages_do_not_nav_to_dev_trace() -> None:
    regular_pages = [
        ROOT / "apps/web/app/app/page.tsx",
        ROOT / "apps/web/app/app/projects/[projectId]/library/page.tsx",
        ROOT / "apps/web/app/app/projects/[projectId]/quiz/page.tsx",
        ROOT / "apps/web/app/app/projects/[projectId]/labs/page.tsx",
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


# Evidence review uses the authenticated API boundary and visibly covers recovery states.
def test_evidence_frontend_covers_async_and_recovery_states() -> None:
    source = (ROOT / "apps/web/app/app/projects/[projectId]/page.tsx").read_text(encoding="utf-8")
    api_source = (ROOT / "apps/web/app/lib/api.ts").read_text(encoding="utf-8")

    required_state_tokens = [
        "waiting_human",
        "Run failed safely",
        "pending",
        "provider",
        "Authentication required",
        "Developer access required",
        "State changed",
        "Usage limit reached",
        "Refresh evidence",
    ]
    combined = source + api_source
    for token in required_state_tokens:
        assert token in combined


# Provider credentials and direct LLM calls remain outside the browser bundle.
def test_frontend_does_not_call_model_provider_directly() -> None:
    frontend_files = list((ROOT / "apps/web/app").rglob("*.tsx")) + list((ROOT / "apps/web/app").rglob("*.ts"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in frontend_files)
    forbidden_provider_calls = [
        "integrate.api.nvidia.com",
        "api.openai.com",
        "chat.completions.create",
        "responses.create",
    ]
    for token in forbidden_provider_calls:
        assert token not in combined


# Preview and production authenticate through a persisted Supabase session and never a dev fallback.
def test_frontend_uses_supabase_session_outside_local_development() -> None:
    package = (ROOT / "apps/web/package.json").read_text(encoding="utf-8")
    auth = (ROOT / "apps/web/app/components/auth-gate.tsx").read_text(encoding="utf-8")
    supabase = (ROOT / "apps/web/app/lib/supabase.ts").read_text(encoding="utf-8")
    api = (ROOT / "apps/web/app/lib/api.ts").read_text(encoding="utf-8")

    for token in [
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "onAuthStateChange",
        "signInWithPassword",
        "sendMagicLink",
        "signOut",
        "getSupabaseSession",
        "session.access_token",
        '"/token?grant_type=password"',
        '"/token?grant_type=refresh_token"',
        '"/logout?scope=local"',
        '"apikey"',
        "researchmate_supabase_session",
        "REFRESH_SKEW_MS",
        "window.setTimeout(() => void refreshSession",
    ]:
        assert token in package + auth + supabase + api

    assert '"@supabase/supabase-js"' not in package
    assert "if (isLocalDevelopment()) return getDevToken()" in api
    assert "if (!session?.access_token)" in api
    assert 'return window.localStorage.getItem("researchmate_token") || "dev"' in api
    assert 'if (!isLocalDevelopment()) throw new ApiError' in api
