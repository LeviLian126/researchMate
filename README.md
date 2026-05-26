# ResearchMate

> **TLDR:** ResearchMate 是一个可溯源 AI 研究学习工作台。当前仓库已完成初始化骨架、API 契约、数据库结构、校验边界和 multi-agent handoff 页面。

## 当前范围

本次初始化只覆盖：

- **Monorepo 结构**：`apps/web`、`apps/api`、`workers/ai-worker`、`packages/shared`、`infra`、`docs`
- **API 契约**：`infra/openapi/openapi.yaml` 与 `docs/api-spec.html`
- **数据库结构**：Supabase Postgres migration 与 `docs/db-schema.html`
- **抽象边界**：FastAPI schema、router stub、provider protocol、共享 TypeScript types
- **安全基线**：`.gitignore`、`.env.example`、RLS 草案、错误脱敏约束
- **交接页面**：`docs/HANDOFF.html` 与 `docs/handoff/index.html`

## 暂不实现

| 不做 | 原因 |
|---|---|
| 真实 OAuth 流程 | 当前阶段只固定接口和权限边界 |
| 文档解析和向量化 | 需要后续 worker agent 接入 Docling、MarkItDown、Qdrant |
| LLM 调用 | 真实 provider key 不能进仓库 |
| Web search/crawl | 先定义 Search/Reader 抽象和安全边界 |
| 完整 UI | UI 只保留可启动壳层，具体交互交给前端 agent |

## 本机环境

已复用本机现有工具：

- `Node.js`
- `npm`
- `bun`
- `Python`
- `uv`
- `pytest`
- `ruff`

推荐 Python 虚拟环境位置：

```powershell
D:\software\researchMate\.venv
```

## 快速验证

```powershell
pytest tests/test_project_scaffold.py -q
python skill/agent-context-html/scripts/validate_context_dashboard.py docs/handoff
```

## 目录说明

```text
researchMate/
  apps/
    api/              FastAPI API 契约和 schema
    web/              Next.js 前端壳层
  workers/
    ai-worker/        文档解析、索引、删除任务抽象
  packages/
    shared/           前后端共享 TypeScript 契约
  infra/
    supabase/         数据库 migration
    qdrant/           向量集合 schema
  docs/
    handoff/          agent 交接页面
    *.html            agent 友好的项目文档页面
  infra/
    openapi/
      openapi.yaml    API 机器可读事实源
```

## 开发原则

1. **先契约，后实现**：接口、库表、页面状态先冻结。
2. **默认安全**：真实密钥只进本地 `.env` 或云平台 secret manager。
3. **Local-first**：Auto 默认不联网，Hybrid 先查本地。
4. **可验证**：每个模块都需要明确验收标准。
5. **可交接**：任何 agent 完成任务后都要更新 handoff 页面。
6. **HTML 文档优先**：`docs` 下不新增 Markdown，项目文档以 HTML 页面维护。
