# ResearchMate

> **TLDR:** ResearchMate 是一个可溯源 AI 研究学习工作台。当前仓库已完成本地可运行 MVP：前端页面、FastAPI 业务闭环、本地解析/索引 fallback、Ask、Sources、Quiz、Developer Trace、安全边界、测试与 HTML handoff 文档。剩余工作是填入真实云端 API/secret、替换本地 adapter 并上线。

## 当前能力

| 模块 | 状态 | 说明 |
|---|---|---|
| Frontend | 已实现 | Next.js App Router 页面：Project list、Ask、Library、Quiz、Developer Trace。 |
| API | 已实现 | FastAPI 路由覆盖 project、document、jobs、ask、quiz、sources、trace、health。 |
| Auth | 本地 dev 模式已实现 | `dev`、`dev-admin`、`dev-user-a`、`dev-user-b` 用于本地联调；生产替换为 Supabase JWT。 |
| Upload / Parse / Index | 本地 fallback 已实现 | `documents/upload-url` 创建文档；`complete` 通过 `extracted_text` 模拟 worker 解析并切片。 |
| Ask | 已实现 | `/study` local-only、`/search` web-only demo、`/hybrid` local-first fallback。 |
| Quiz | 已实现 | 基于本地 chunks 生成有引用的题目；选择题固定 4 个选项。 |
| Developer Trace | 已实现 | 仅 developer/admin 可见；普通用户无法读取。 |
| Docs | 已实现 | `docs/index.html` 是唯一主入口，`docs/progress*.html` 展示实时模块进度，另包含 handoff dashboard、test plan、安全清单和 OpenAPI 镜像。 |

## 本地运行

### 1. 安装 Python 依赖

```powershell
pip install -r requirements-dev.txt
```

### 2. 启动 API

```powershell
python -m uvicorn researchmate_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
```

### 3. 安装并启动前端

```powershell
npm install
npm --workspace @researchmate/web run dev
```

打开：

```text
http://localhost:3000/app
```

本地默认 token：

| Token | Role | 用途 |
|---|---|---|
| `dev` | developer | 默认本地开发账号，可看 trace。 |
| `dev-admin` | admin | 管理员权限。 |
| `dev-user-a` | user | 普通用户 A，用于隔离测试。 |
| `dev-user-b` | user | 普通用户 B，用于隔离测试。 |

## 快速验证

```powershell
pytest tests/test_project_scaffold.py tests/test_api_workflow.py tests/test_frontend_contracts.py -q
python skill/agent-context-html/scripts/validate_context_dashboard.py docs/handoff
```

可选检查：

```powershell
ruff check apps/api/src workers/ai-worker/src tests
npm --workspace @researchmate/web run build
```

> 当前交付不包含 `.venv`、`node_modules`、真实密钥或部署产物；如果本地环境未安装 ruff 或 node_modules，不应把未运行的检查误记为通过。

## 目录说明

```text
researchMate/
  apps/
    api/              FastAPI API、schemas、routers、本地服务 adapter
    web/              Next.js 前端 MVP
  workers/
    ai-worker/        文档解析和索引 worker 抽象及本地 fallback
  packages/
    shared/           前后端共享 TypeScript 契约
  infra/
    openapi/          OpenAPI 机器可读契约
    supabase/         数据库 migration
    qdrant/           向量集合 schema
  docs/
    progress*.html    实时模块进度
    handoff/          agent 交接 dashboard
    *.html            项目 HTML 文档、测试计划、安全清单
  tests/              scaffold、API workflow、frontend contract 测试
```

## 上线前替换点

| 本地实现 | 上线替换 |
|---|---|
| dev token | Supabase Auth JWT issuer/audience/signature/expiry 校验 |
| in-memory store | Supabase Postgres + RLS、Redis cache/job state |
| local upload URL placeholder | Cloudflare R2 signed URL 和对象生命周期 |
| `extracted_text` fallback | Docling/MarkItDown worker 从 R2 读取并解析 |
| in-memory chunk retrieval | Qdrant embedding search，必须带 user_id/project_id filter |
| deterministic answer/quiz | OpenAI-compatible LLM provider，保留 schema validation 和 citation validation |
| demo web evidence | SERPER/Tavily + JINA/Firecrawl provider，保留 source-policy guard |

## 开发原则

1. **Local-first**：Auto 默认不联网；Local Ask 不得调用 web 工具。
2. **Owner isolation**：任何 project、document、run、quiz、trace 访问都必须校验用户归属或管理员角色。
3. **No secrets in repo**：真实 key 只进本地 `.env` 或部署平台 secret manager。
4. **Grounded output**：Ask、Quiz 必须有 citations；无本地资料时拒绝编造。
5. **可验证**：新增功能必须补测试或更新测试计划。
6. **HTML 文档优先**：`docs` 下不新增 Markdown，项目文档以 `docs/index.html` 和 `docs/progress*.html` 为实时入口维护。
