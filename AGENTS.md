# ResearchMate Agent Instructions

## TLDR

- 先读 `docs/index.html`、`docs/handoff/index.html`、`docs/handoff/context-state.json`，再改代码。
- 修改后的文件路径向用户展示时使用相对路径。
- 写类、函数等代码块时，每个类或函数前添加一行简短注释说明作用。
- 不把真实 API key、OAuth token、R2 secret、provider secret 放进仓库或 trace。

## Current Project Boundary

ResearchMate 当前阶段已完成本地可运行 MVP：Next.js 前端、FastAPI API、in-memory 本地 adapter、上传/解析/索引 fallback、Local Ask、Sources、Quiz、Developer Trace、用户隔离和测试。

> 允许继续完善本地 MVP、测试和文档；上线前必须把本地 dev token、in-memory store、demo web evidence 和 deterministic LLM fallback 替换为真实 Supabase/R2/Qdrant/Redis/provider adapter。

## Safety Rules

- Auto 默认 local-only；除 `/search`、`/hybrid` 或显式 `web_only` 外，不调用 web/search/crawl 工具。
- 普通用户不能看到 Developer Trace；trace 只能由 developer/admin 访问。
- 所有 resource 访问都要校验 owner user_id 或明确 admin 权限。
- 错误响应、日志和 trace 不得泄露 stack trace、SQL、raw provider error、secret、token 或 signed URL secret。
- 删除 project/document 时必须清理关联 chunks；上线时还需同步清理 DB/R2/Qdrant/Redis。

## Documentation Rule

`docs` 目录内的项目文档使用 HTML 页面维护，不再新增 Markdown 文档。更新上下文时同步维护 `docs/handoff/index.html` 和 `docs/handoff/context-state.json`。
