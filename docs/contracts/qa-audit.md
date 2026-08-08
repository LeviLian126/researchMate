# ResearchMate QA 审计报告

- **审计日期**：2026-08-08
- **标准**：indie-product-delivery skill Node05 (CP1-CP11) + `AGENTS.md` 仓库规则
- **范围**：`apps/api/src/`、`workers/ai-worker/src/`、`tests/`、`docs/`、`.github/workflows/`、`infra/`、`scripts/`、`apps/web/`
- **方法**：通过三个并行 Explore subagent 进行静态审查（Python 代码质量、文档/基础设施一致性、indie-skill 标准提取）。运行时检查点 CP5-CP8（应用启动、E2E、多分辨率、调试）在本次审计中**未执行**。
- **风险等级**：STANDARD（本次审计未涉及认证/支付/迁移/公开 API/数据表变更；适用基线安全检查）

## 结论：FIX

| 严重度 | 数量 | 摘要 |
|---|---|---|
| Blocker | 0 | — |
| Major | 2 | CI 类型检查门控被弱化；cicd.html ↔ cicd.zh.html 不同步 (Node08) |
| Minor | 6 | 测试 `__future__` 导入、测试 fixture 缺注解、validator 中的魔法数字、flows section-ID 不匹配、worker.zh 导航标签、未文档化的脚本 |

应用端到端可运行，无核心流程中断，未发现安全漏洞或数据丢失风险。两个 Major 是可修复的门控/同步问题；Minor 是一致性缺口。无 Blocker 阻止发布。

---

## 按检查点分类的发现

### CP2 — LLM 代码审计：PASS

扫描了所有生产 Python 代码，检查 indie skill 定义的 8 种 LLM 特定失败模式（位于 `skill/indie-product-delivery/references/nodes/05-qa-review-security-hardening/code-and-test-review.md`）。

| 模式 | 结果 | 证据 |
|---|---|---|
| 幻觉 API | 未发现 | 无调用不存在的方法/字段；签名与已安装 SDK 版本匹配 |
| 占位符返回 | 未发现 | 核心路径上无 `return None`/`pass`/忽略输入的固定值返回 |
| 硬编码假数据 | 未发现 | 无伪装成真逻辑的示例数据 |
| 静默降级 | 未发现 | 所有 29 个 `except Exception:` 块（`apps/api` 12 个、`workers/ai-worker` 17 个）都带上下文记录日志并重新抛出，或是合理化的健康检查/观察者边界（`observability.py:31,36,124`、`routers/health.py:136,151,162`、`celery_app.py:79,87,95`） |
| 测试弱化 | 未发现 | 无跳过/清空的测试；前端测试是实质性的（`auth-gate.test.tsx`、`presentation.test.tsx`、`project-nav.test.tsx`、`app-sidebar.test.tsx`） |
| 过宽权限 | 本次未标记 | 所有者/租户范围在 CP9 中审查——未发现 IDOR |
| 缺失错误处理 | 未发现 | 核心路径上无无限循环、N+1 查询或未关闭资源 |
| 捏造依赖 | 未发现 | 所有导入都解析到已安装包 |

### CP3 — 测试质量：2 Minor

- **Minor-1** — 45 个测试文件中有 41 个缺少 `from __future__ import annotations`。`AGENTS.md` 要求"每个 Python 模块"都有，对测试无例外。受影响文件：`tests/conftest.py`、`tests/api_workflow_fixtures.py`、`tests/test_document_deletion.py`、`tests/test_document_ingestion.py` 等 37 个其他文件。仅 4 个测试文件包含它（`test_worker_evaluation.py`、`test_postgres_persistence.py`、`test_quiz_service.py`、`test_grounded_query.py`）。
- **Minor-2** — 100+ 个未注解的测试 fixture/mock 方法。代表性示例：`tests/test_document_deletion.py:33` `def __init__(self, attempts=1):`、`tests/test_enabled_ai_runtime.py:11` `def plan(self, _state):`、`tests/test_evidence_postgres_unit.py:55` `def execute(self, statement, parameters=None):`。仅测试代码；优先级较低。

### CP4 — 静态门控：1 Major

- **Major-1** — `.github/workflows/ci.yml:35` 在"Run Python type checks"步骤（`npm run check:types`）上设置了 `continue-on-error: true`。由于该步骤是建议性的，即使 pyright 失败，`python-quality` job 也会报告 `success`，因此 `ci-success` 聚合器（断言 `needs.python-quality.result == success`）永远看不到类型错误。CP4 要求 lint + 类型检查 + 构建实际阻断。英文 `docs/learn/cicd.html:354` 甚至将此文档化为"types continue-on-error"，将弱化的门控正常化。

### CP9 / CP11 — 安全：PASS（基线）

- 仓库中无密钥；`.gitignore` 排除了 `.env`、`*.pem`、`*.key`、`*service-account*.json`、`*secret*.json`。
- 通过 SQLAlchemy 的参数化查询——无 SQL 注入。
- 无裸 `typing.Any` 泄露 PII；所有 `Any` 用法都位于外部 SDK 边界（`services/llm.py:16`、`services/qdrant_store.py:54`、`services/rerank.py:87,192`、`services/object_storage.py:115`、`services/embedding.py:17`）并有理由说明。
- 所有 `# noqa` 抑制都注解了原因：`routers/health.py:25` (B008)、`tests/test_http_security_hardening.py:12` (F401)、`tests/test_postgres_persistence.py:43` (D401)、`tests/test_object_storage.py:18,55` (F401, N803)、`tests/test_worker_tasks.py:9` (F401)。

### Node08 — HTML 看板同步：1 Major + 2 Minor

- **Major-2** — `docs/learn/cicd.html` ↔ `docs/learn/cicd.zh.html` 在两个方向上都不同步。中文版将 `#deployment-arch` 合并到 `#full-flow`（架构图现在内联在 `cicd.zh.html:355`），为每个 proof-step 添加了 indie-skill 状态标签（planned/ready/executed/verified）（`cicd.zh.html:348-353`），并添加了"恢复与回滚"通知（`cicd.zh.html:390`）。英文版仍有两个独立的部分（`cicd.html:348 #full-flow` 无图、`cicd.html:362 #deployment-arch` 有图），无状态标签，无恢复通知。Node08 要求中英文副本保持同步。
- **Minor-3** — `docs/learn/flows.html:306` 使用 `id="further-reading"`，而 `docs/learn/flows.zh.html:331` 使用 `id="extended-reading"`。两者都在内部解析，但该对之间的 section-ID 命名不一致。
- **Minor-4** — `docs/learn/worker.zh.html:37-43` 导航栏混合了英文标签（"Frontend"、"Backend"、"Worker"、"Infrastructure"、"CI/CD"）和一个中文标签（"切面分析"）。

### AGENTS.md 代码质量：1 Minor

- **Minor-5** — 约 15 个 pydantic validator 字段使用硬编码的 `max_length` 字面量而非领域常量。仅 `schemas/common.py:14 MAX_TEXT_LENGTH=1200` 被集中化并实际被引用（由 `Citation.quote`）。硬编码字面量：`schemas/ask.py:19 (8000)`、`:29 (120)`、`:39 (16000)`、`:52 (16000)`、`:60 (300)`、`schemas/document.py:58 (200_000)`、`schemas/conversation.py:70 (16000)`、`schemas/quiz.py:18 (4000)`、`schemas/evidence.py:88 (2000)`、`services/evidence_generation.py:23 (1600)`。加上 5 个带硬编码长度的 `snippet()` 调用：`services/quiz_generation.py:62 (900)`、`:166 (180)`、`:187 (220)`、`:204 (260)`、`:225 (220)`，以及 `services/retrieval.py:147 (280)`、`services/_store_text.py:6 (900)`。

### 文档完整性：1 Minor

- **Minor-6** — `scripts/_gen_infra_pt1.py` 和 `scripts/_gen_infra_zh.py`（私有文档生成辅助脚本，前导下划线约定）未被 `package.json`、CI 或基础设施 HTML 文档引用。要么将它们接入文档管道，要么文档化为一次性辅助脚本。

---

## 干净类别（显式 PASS）

这些类别已检查且零违规——记录在此以便区分"未检查"和"已检查但无问题"：

- **生产**代码中缺失 `from __future__ import annotations`：0 违规（`apps/api/src` + `workers/ai-worker/src` 中所有约 125 个文件）
- 通配符导入（`import *`）：0
- 可变默认参数（`def f(x=[])`）：0
- 公共签名中无理的 `typing.Any`：0
- 静默吞掉错误（`except Exception: pass`）：0
- 源码中的中文注释：0（仅在 `answering.py`、`query_generation.py`、`quiz_generation.py` 的用户面向字符串字面量中找到 CJK，`AGENTS.md` 允许）
- 前端 `TODO`/`FIXME`/`HACK`/`console.log`：0
- 空或跳过的前端测试：0
- `docs/index.html` 交叉引用中的破损内部锚链接：0（所有 `#cap-*` 目标都解析）

---

## 修复建议（本次审计未执行）

按严重度排序。每条是建议的修复及需接触的文件；根据用户的"仅报告"决定，本次审计均未应用。

| # | 严重度 | 发现 | 建议修复 | 文件 |
|---|---|---|---|---|
| Major-1 | Major | CI 类型检查门控非阻断 | 移除 `continue-on-error: true`，或捕获 `TYPE_RESULT` 环境变量并在 `ci-success` 中断言 | `.github/workflows/ci.yml:35`；更新 `docs/learn/cicd.html:354` 和 `cicd.zh.html:349` 措辞 |
| Major-2 | Major | cicd.html ↔ cicd.zh.html 不同步 | 对英文 `cicd.html` 应用相同的合并（将 `#deployment-arch` 折叠到 `#full-flow`，添加状态标签 + 恢复通知），或回退中文合并——选择一种规范结构 | `docs/learn/cicd.html`、`docs/learn/cicd.zh.html` |
| Minor-1 | Minor | 41 个测试文件缺 `from __future__` | 在每个文件的模块 docstring 后添加 `from __future__ import annotations` | `tests/*.py`（41 个文件） |
| Minor-2 | Minor | 100+ 个未注解的测试 fixture | 为测试 fixture/mock 方法添加返回类型注解 | `tests/*.py` |
| Minor-3 | Minor | flows section-ID 不匹配 | 重命名 `flows.zh.html` 的 `extended-reading` → `further-reading`（或反之）以保持对之间的一致性 | `docs/learn/flows.html:306`、`docs/learn/flows.zh.html:331` |
| Minor-4 | Minor | worker.zh 导航双语标签 | 将剩余英文导航标签翻译为中文，或使整个导航为英文 | `docs/learn/worker.zh.html:37-43` |
| Minor-5 | Minor | validator 中的魔法数字 | 将剩余的 `max_length` 字面量和 `snippet()` 长度集中为 `schemas/common.py` 中的领域常量 | `schemas/ask.py`、`schemas/document.py`、`schemas/conversation.py`、`schemas/quiz.py`、`schemas/evidence.py`、`services/evidence_generation.py`、`services/quiz_generation.py`、`services/retrieval.py`、`services/_store_text.py` |
| Minor-6 | Minor | 未文档化的私有脚本 | 将 `_gen_infra_*.py` 接入文档管道，或在 `docs/learn/infra.*.html` 中文档化为一次性辅助脚本 | `scripts/_gen_infra_pt1.py`、`scripts/_gen_infra_zh.py`、`docs/learn/infra.html`、`docs/learn/infra.zh.html` |

---

## 方法与局限

- **Agent**：三个并行 Explore subagent——(1) indie-skill 标准提取，(2) 针对 `AGENTS.md` 的 Python 代码库审计，(3) 文档/基础设施/前端/脚本一致性。
- **标准来源**：`skill/indie-product-delivery/references/nodes/05-qa-review-security-hardening/`（中文）和 `skill/personal-dev-skills-v9-baseline-plus-en/indie-product-delivery/.../`（英文），加上 `AGENTS.md` 仓库规则。
- **局限**：仅静态审查。运行时检查点 CP5（应用启动）、CP6（E2E 用户旅程）、CP7（多分辨率前端）、CP8（调试根因分析）未执行。CP10（完整可靠性审查）仅适用于 HIGH_RISK 变更，本次未触发。根据 Node05 的范围，本次审计验证已编写的代码；它不设计 UI、不更改公共契约、不执行部署。
