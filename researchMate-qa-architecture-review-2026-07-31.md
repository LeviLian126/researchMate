# ResearchMate QA、API 与架构审计报告

**审计日期：** 2026-07-31  
**目标仓库：** `LeviLian126/researchMate`  
**目标版本：** `main@358ab5fbb5f04ae330915f487ba2bd65f3b9d0c5`  
**审计方式：** 只读源码审查、契约与测试代码审查、关键控制流推演、测试体系与发布证据评估  
**最终结论：** **STOP / BLOCKED，不建议将当前版本视为已通过生产级 QA**

> 本报告中的“已确认”表示问题能够直接从当前源码控制流和契约中推出，不依赖猜测；“运行证据缺口”表示当前环境未能取得完整仓库执行、线上凭据或对应构建产物，不能把静态审查冒充成线上验收。

---

## 1. 执行摘要

ResearchMate 当前不是一个已经失控的 spaghetti code 项目。它有一些值得保留的基础：FastAPI 路由总体较薄，Pydantic 请求模型覆盖了多项输入边界，Repository、LLM、向量库、Web Search 等外部依赖已经抽象为可替换接口，PostgreSQL 写入路径也有用户过滤和活动项目复核。问题在于，这些抽象正在变得过宽，REST、MCP、内存仓储和 PostgreSQL 仓储之间已经出现策略漂移，且漂移已经转化为真实的产品语义错误。

本次审查确认了一个 P0、八个 P1 和若干 P2 问题。最需要优先处理的是：

1. **个人会话附件的 conversation scope 可被 MCP 的 project-level 接口绕过。** 同一用户在一个个人会话中上传的资料，可能被项目级 MCP 搜索或资源接口从另一个会话读取。这违反了现有测试明确声明的“个人聊天附件按会话隔离”边界。
2. **小型资料直接走 `full_context`，完全跳过相关性门槛。** 对 RAG 资料询问“光合作用”时，当前测试反而要求返回引用；测试注释和断言相互矛盾，并把错误行为固化成回归契约。
3. **Quiz 默认请求与检索算法不匹配。** 默认英文提示词被当作 BM25 主题查询；全中文资料通常与该提示词没有任何 token 重合，因此即使资料已经索引完成，也可能错误返回 `DOCUMENT_NOT_INDEXED`。同时，前端声称“使用所有 ready resources”，后端却只选有词项命中的候选，最多 50 个 chunk。
4. **REST 与 MCP 的 Developer Trace 权限不一致。** REST 明确要求 developer/admin，MCP 却允许普通用户读取自己拥有的 trace，违反了 MCP 自己声明的“保持 REST permission rules”。
5. **Ask 与 Quiz 在完整校验和提供方成功之前就消耗 quota、创建会话或写入部分状态。** 失败重试还缺少幂等保护，可能重复计费、重复消息和重复 Quiz。
6. **现有测试对本地内存实现覆盖较好，但无法证明生产路径。** 主要 API 工作流使用内存 Store、fake provider 和直接 `extracted_text`；真实路径中的 PostgreSQL、R2/S3、outbox、Celery、Qdrant、Redis、解析与索引协作没有在本次可获得的运行证据中闭环。

因此，当前版本不应仅凭现有契约测试或 Vercel 状态被标记为“生产就绪”。阻塞原因不是代码风格偏好，而是已经确认的隔离、授权、引用正确性和核心 Quiz 行为问题。

---

## 2. 审计方法与证据边界

### 2.1 采用的 QA 工作流

仓库真正的 QA 流程位于：

```text
skill/indie-product-delivery/references/nodes/05-qa-review-security-hardening/
├── README.md
├── quality-scope-and-diff-review.md
├── runtime-reliability-and-security-proof.md
└── quality-decision-and-release-readiness.md
```

本次按其中的风险优先原则执行：先恢复产品和权限边界，再检查调用链、契约、数据隔离、失败路径、幂等、运行证据和发布状态，最后给出 PASS、FAIL 或 GAP。由于仓库包含 auth、tenant-like scope、upload、AI provider、MCP、外部搜索和持久化写入，本次按 G3 高风险门槛处理。

同时补充参考了以下公开测试工作流和官方实践：

- Fugazi `test-automation-skills-agents`：风险分层的 API、E2E、smoke、regression、a11y 和 flaky test 工作流。
- OpenAI Agents Python 的 `code-change-verification`：运行时代码变化必须经过完整测试、lint、typecheck 和 coverage 验证。
- Playwright 官方 API 与浏览器测试模式：通过 API 构造前置状态，并在浏览器操作后验证服务端后置状态。
- OWASP API Security Top 10 2023：统一授权模块、资源消耗限制和敏感业务流保护。
- pytest、coverage.py、Starlette 与 Python asyncio 官方文档。

### 2.2 已获得与未获得的证据

| 证据 | 状态 | 说明 |
|---|---|---|
| 当前 HEAD 与关键源码 | PASS | 已读取 API、MCP、Store、PostgreSQL、Quiz、检索、回答、前端、测试和 CI 配置 |
| 关键控制流推演 | PASS | 隔离绕过、权限不一致、full-context 绕过和 Quiz 默认检索问题可由源码确定 |
| 现有测试质量审查 | PASS | 已检查主要 API、前端契约、项目契约和 CI 命令 |
| 完整本地 `npm run check:all` | GAP | 当前执行环境无法完成 GitHub 仓库 clone，不能声称完整测试已实际通过 |
| 当前 HEAD 的 GitHub Actions 产物 | GAP | 连接器仅返回 Vercel 成功状态，未取得与该 HEAD 对应的完整 Actions 日志和测试产物 |
| PostgreSQL/R2/Redis/Qdrant/Celery 集成执行 | GAP | 无本次可验证的部署凭据和隔离测试环境 |
| 线上或 preview smoke test | GAP | 未取得可安全使用的测试账号、环境 URL 和授权范围 |

这些 GAP 不会降低已经由源码确认的问题严重度；它们只意味着本报告不会声称未执行的线上行为已经失败或已经通过。

---

## 3. 优先级总览

### 3.1 严重度定义

- **P0：** 隔离、敏感数据或权限边界被绕过，必须在下一次发布前修复。
- **P1：** 核心功能正确性、持久化一致性、计费/配额、可靠性或生产证明存在高风险缺口。
- **P2：** 可维护性、可观测性、测试质量或中期架构问题；应在 P0/P1 后处理。
- **P3：** 局部清理和一致性改进，不单独阻塞发布。

### 3.2 问题列表

| ID | 优先级 | 问题 | 主要影响 | 置信度 |
|---|---:|---|---|---:|
| RM-QA-001 | P0 | MCP 项目级搜索绕过个人会话附件隔离 | 错误会话读取敏感附件，错误上下文混入回答 | 高 |
| RM-QA-002 | P1 | `full_context` 绕过相关性与 answerability gate | 无关资料被强制引用，RAG 可信度失真 | 高 |
| RM-QA-003 | P1 | Quiz 默认提示词被误当作 BM25 主题查询 | 已索引资料仍可能 409，非英文资料尤为明显 | 高 |
| RM-QA-004 | P1 | REST 与 MCP Trace 权限策略不一致 | 普通用户通过另一接口获得 REST 禁止的能力 | 高 |
| RM-QA-005 | P1 | quota 和会话副作用发生在完整校验之前 | 失败请求消耗额度并留下空会话/部分状态 | 高 |
| RM-QA-006 | P1 | Ask/Quiz 缺少幂等键语义 | 网络重试、双击或超时可重复调用模型和写入 | 高 |
| RM-QA-007 | P1 | 主要测试未跨越生产 Adapter 边界 | 内存实现通过不能证明 Postgres/outbox/worker 正常 | 高 |
| RM-QA-008 | P1 | Quiz 保存和会话删除缺少完整 Unit of Work | 中途失败产生孤立 run 或半删除会话 | 高 |
| RM-QA-009 | P1 | async MCP middleware 直接执行同步网络/数据库调用 | JWKS 或数据库抖动可阻塞事件循环 | 中高 |
| RM-QA-010 | P1 | 跨会话 Project Memory 被提升为 assistant role | 用户文本获得错误信任级别，增加提示注入风险 | 中高 |
| RM-QA-011 | P2 | 语义检索和摘要失败被静默吞掉 | 线上退化难发现，trace 仍显示成功 | 高 |
| RM-QA-012 | P2 | 多个 token budget 不是硬上限 | 首个超大消息或 chunk 可突破预算 | 高 |
| RM-QA-013 | P2 | Service/Repository 过宽，职责和变化原因混杂 | REST/MCP、memory/Postgres 更易继续漂移 | 高 |
| RM-QA-014 | P2 | 测试中存在相反断言、字符串存在性测试和过低总覆盖门槛 | 测试可能保护错误行为或允许关键分支未覆盖 | 高 |
| RM-QA-015 | P2 | API、worker、dispatcher 同进程部署扩大故障域 | 单子进程退出可能拖垮全部能力 | 中高 |
| RM-QA-016 | P2/P3 | OpenAPI、异常处理、Schema 与 Skill 路由存在一致性债务 | 契约漂移、隐藏依赖故障和维护噪声 | 高 |

---

## 4. 重大问题与修复方案

## RM-QA-001：MCP 绕过个人会话附件隔离

**优先级：P0**  
**类型：隐私边界、作用域错误、跨接口策略漂移**

### 已确认的控制流

个人聊天采用一个隐藏的 personal project 复用项目基础设施，但附件被显式绑定到 `conversation_id`。REST Ask 路径在 personal project 中调用：

```text
list_conversation_documents(...)
conversation_chunks(...)
```

因此现有测试可以证明第二个个人会话不能使用第一个会话的附件。

但是 MCP 存在两条 project-level 路径：

```text
mcp_server.search_project(project_id, query)
  -> GroundedQueryService.search(...)
  -> repository.project_chunks(...)

mcp_server.project_documents(project_id)
  -> repository.list_project_documents(...)
```

这两个接口都没有 `conversation_id`，也没有拒绝 `project.kind == "personal"`。内存 Store 和 PostgreSQL Store 的 `project_chunks` / `list_project_documents` 都按 `user_id + project_id` 返回整个 personal project 的内容。用户可以从 `/chat/bootstrap` 得到 personal project ID，因此该 ID 不是不可获得的秘密。

### 影响

- 一个会话内的 MCP agent 可以检索另一个个人会话的附件内容。
- `project://{project_id}/documents` 可能枚举所有个人聊天附件元数据。
- 同一账号下不同对话的隐私边界被破坏，模型可能把无关或敏感资料带入当前回答。
- 该问题同时存在于内存和 PostgreSQL 适配器，不是测试环境特例。

### 涉及源码

```text
apps/api/src/researchmate_api/mcp_server.py
apps/api/src/researchmate_api/services/grounded_query.py
apps/api/src/researchmate_api/services/store.py
apps/api/src/researchmate_api/persistence/postgres.py
apps/api/src/researchmate_api/routers/documents.py
apps/api/src/researchmate_api/routers/projects.py
```

### 最小安全修复

1. 将 project-level 能力定义为 workspace-only：
   - `search_project` 遇到 personal project 直接返回 `PROJECT_SCOPE_REQUIRES_CONVERSATION`。
   - `project://.../documents` 对 personal project 同样拒绝。
2. 新增明确的 conversation-level MCP 能力：
   - `search_conversation(project_id, conversation_id, query, limit)`。
   - `conversation://{conversation_id}/documents`。
3. 不再使用含糊的 `project_chunks` 作为所有场景的通用入口，改为：

```python
workspace_chunks(user, project_id)
conversation_chunks(user, project_id, conversation_id)
```

4. 把 workspace/personal scope policy 放在共享应用服务中，REST 和 MCP 都调用同一策略，而不是各自拼装 Repository 方法。

### 必须补充的回归测试

```text
test_mcp_personal_search_cannot_cross_conversations
test_mcp_personal_project_resource_is_rejected
test_mcp_conversation_resource_returns_only_its_documents
test_workspace_mcp_search_remains_project_scoped
test_memory_and_postgres_scope_contract_are_identical
```

验收场景应创建两个个人会话，分别上传只包含 `ALPHA-ONLY` 和 `BETA-ONLY` 的资料；任何 conversation-A 调用都不得看到 B 的内容或元数据。

---

## RM-QA-002：`full_context` 把“能装下”错误等同于“与问题相关”

**优先级：P1**  
**类型：核心回答正确性、RAG 可信度、错误测试契约**

### 已确认的控制流

`GroundedQueryService.execute` 先计算所有本地 chunk 的估算 token 数。当总量不超过默认 `full_context_token_limit=12000` 时：

- 所有 chunk 直接成为 candidate；
- 不执行 BM25 相关性过滤；
- 在未启用 Web 时不执行 rerank；
- 所有能装入预算的 chunk 都会进入回答生成。

fake provider 路径中的 `build_grounded_answer` 又会为每个传入 chunk 创建 citation，因此只要项目中有小型资料，任意问题都容易得到看似“有依据”的回答。

现有测试进一步把该错误固化：测试注释写的是“无词项重合时拒答，不能用无关 chunk 伪造引用”，但测试使用 RAG 文档询问 `photosynthesis chlorophyll`，最终断言却是 `citations` 必须非空。

### 影响

- 引用存在不再代表资料支持答案。
- 小项目比大项目更容易产生无关引用，行为随资料总 token 数发生不合理突变。
- 测试会阻止未来正确修复，因为它把错误行为当成预期。
- 用户最关心的“有引用、可追溯”承诺失去可信度。

### 涉及源码

```text
apps/api/src/researchmate_api/services/grounded_query.py
apps/api/src/researchmate_api/services/retrieval.py
apps/api/src/researchmate_api/services/answering.py
apps/api/src/researchmate_api/config.py
tests/test_api_workflow.py
```

### 改进原则

`full_context` 只能是**上下文装箱策略**，不能是**相关性策略**。建议拆成两步：

```text
1. relevance / answerability：资料是否支持这个问题？
2. packing：已通过相关性判断的证据是否全部能放入上下文？
```

最小实现可以先做到：

1. 无论资料大小，都运行轻量 lexical/semantic gate。
2. 对无任何相关证据的查询，返回明确的 insufficient-evidence 回答，`citations=[]`。
3. 只有通过 gate 的候选才进入 full-context packing。
4. 为 answerability 设置可观测结果，而不是把“模型引用了某个 evidence ID”误当作证据真的相关。
5. 建立包含 supported、partially-supported、unsupported 三类问题的 RAG golden dataset，度量 citation precision、citation recall 和 abstention accuracy。

### 必须补充的回归测试

```text
test_full_context_unrelated_query_abstains_without_citations
test_full_context_related_query_uses_all_relevant_chunks
test_context_strategy_does_not_change_answerability_semantics
test_negative_control_questions_do_not_generate_fake_citations
```

原有矛盾测试必须重写，不能只改注释来迁就现有断言。

---

## RM-QA-003：Quiz 默认提示词与 BM25 检索语义不兼容

**优先级：P1**  
**类型：核心 API 逻辑错误、多语言缺陷、产品承诺不一致**

### 已确认的控制流

`POST /quiz` 当前执行：

```python
ranked = retrieve_local_chunks(chunks, payload.prompt, limit=len(chunks))
```

这里的 `retrieve_local_chunks` 是纯 BM25；`payload.prompt` 同时承担“生成指令”和“主题查询”两个职责。

后端默认值是：

```text
Generate a quiz from my documents.
```

前端空输入时发送：

```text
Generate a balanced quiz from all project resources.
```

这些通用指令并不描述资料主题。对全中文资料，英文默认词与中文 chunk 通常没有 token 重合，BM25 返回空列表，随后 API 抛出：

```text
409 DOCUMENT_NOT_INDEXED
```

这与真实状态不符：资料可能已经 ready，只是默认生成指令没有词项命中。现有测试使用 `Generate a RAG quiz`，刚好命中测试夹具中的 RAG，因此没有覆盖真实默认路径。

此外，前端写着“Uses every ready project resource”，后端实际上：

- 只保留 BM25 得分大于零的 chunk；
- 再尝试每个文档选一个代表 chunk；
- 总量最多 50；
- 不保证所有 ready 文档都被覆盖。

### 影响

- 用户不填写自定义提示词时，Quiz 的最常用路径可能失败。
- 中文或其他非英语资料受影响更明显。
- 返回的错误码误导用户认为资料没有索引。
- “使用所有资料”的 UI 承诺与实际算法不一致。

### 涉及源码

```text
apps/api/src/researchmate_api/routers/quiz.py
apps/api/src/researchmate_api/schemas/quiz.py
apps/api/src/researchmate_api/services/retrieval.py
apps/api/src/researchmate_api/services/quiz_generation.py
apps/web/app/components/chat-workspace.tsx
tests/test_api_workflow.py
```

### 推荐修复

将两个概念拆开：

```json
{
  "project_id": "...",
  "instructions": "Generate a balanced quiz",
  "topic_query": null,
  "resource_scope": "all_ready_documents"
}
```

- `instructions` 只控制题型、难度和风格，不参与资料相关性搜索。
- `topic_query` 非空时才执行主题检索。
- `resource_scope=all_ready_documents` 时，先从每个 ready 文档选择代表 chunk，再在预算内扩充。
- 文档过多时明确返回 coverage summary，例如“覆盖 40/63 个文档”，而不是声称全部覆盖。
- 若用户确实选择 topic mode，则使用 semantic/hybrid retrieval，并把未覆盖文档作为响应元数据返回。

### 必须补充的回归测试

```text
test_quiz_default_prompt_works_for_chinese_documents
test_quiz_default_prompt_does_not_require_keyword_overlap
test_quiz_all_resources_reports_actual_document_coverage
test_quiz_topic_mode_filters_by_topic
test_quiz_ready_documents_are_not_reported_as_not_indexed
```

---

## RM-QA-004：REST 与 MCP 的 Developer Trace 授权不一致

**优先级：P1**  
**类型：Broken Function Level Authorization、接口契约漂移**

### 已确认的控制流

REST 路由：

```text
GET /api/v1/dev/traces/{trace_id}
  -> Depends(require_admin)
```

普通用户在现有测试中应得到 403。

MCP 工具：

```text
get_run_trace(trace_id)
  -> repository.get_trace(ctx.user, trace_id)
```

MCP 没有 developer/admin 检查。两个 Repository 实现又都允许：

```text
privileged user OR trace.user_id == current_user.id
```

因此普通用户不能通过 REST 读自己的 trace，却可以通过 MCP 读。这也与 MCP server instructions 中“tools preserve REST permission rules”的描述冲突。

### 影响

Trace 包含 retrieved chunk 摘要、tool input/output summary、模型与 rerank 元数据、错误和 token usage。即使当前只能读取自己拥有的 trace，接口级权限承诺仍已失效，后续任何 trace 字段扩展都可能扩大暴露面。

### 涉及源码

```text
apps/api/src/researchmate_api/routers/dev_traces.py
apps/api/src/researchmate_api/mcp_server.py
apps/api/src/researchmate_api/dependencies.py
apps/api/src/researchmate_api/services/store.py
apps/api/src/researchmate_api/persistence/postgres.py
```

### 推荐修复

建立唯一的 `TraceAccessPolicy` 或 `TraceQueryService`，由 REST 和 MCP 共同调用。只能选择以下一种明确契约：

1. **admin-only：** 所有接口都要求 developer/admin；或
2. **owner-safe：** 普通 owner 只能得到专门的脱敏 `UserRunTrace`，DeveloperTrace 仍为 admin-only。

不要把权限规则藏在 Repository 中。Repository 只负责按明确 scope 查询，应用层负责决定当前角色能请求哪种 scope。

### 必须补充的回归测试

建立 REST/MCP 权限矩阵，覆盖 user、developer、admin、owner、non-owner，并断言两个协议得到相同结果。

---

## RM-QA-005：失败请求提前消耗 quota 并留下副作用

**优先级：P1**  
**类型：业务一致性、资源计量、失败语义**

### 已确认的顺序

Ask 当前大致顺序为：

```text
校验项目
-> increment_usage
-> ensure_conversation
-> 读取/可能更新会话摘要
-> 检查文档处理状态
-> 检索/Web/Provider
-> record_run 和保存消息
```

因此以下情况都可能已经消耗 quota：

- `conversation_id` 无效；
- 文档仍在 parsing/indexing；
- Web provider 未配置或未找到证据；
- LLM provider 暂时失败；
- 模型输出结构无法修复。

当没有传 `conversation_id` 时，某些失败还会留下没有消息的空会话。Quiz 同样在检查 ready chunk 和 provider 成功之前调用 `increment_usage`。

这不一定意味着“所有失败都必须免费”，但当前代码没有定义 quota 到底统计 accepted attempt、provider call 还是 successful result，导致用户可见语义和实现顺序不一致。

### 涉及源码

```text
apps/api/src/researchmate_api/services/grounded_query.py
apps/api/src/researchmate_api/routers/quiz.py
apps/api/src/researchmate_api/services/store.py
apps/api/src/researchmate_api/persistence/postgres.py
```

### 推荐修复

1. 先定义计量契约：
   - `attempt_quota`：合法进入执行阶段即计数；或
   - `billable_quota`：实际触发收费 provider 才计数；或
   - `successful_quota`：成功返回才计数。
2. 把不产生费用的前置校验放在 quota reservation 之前。
3. 对需要收费的操作采用 reservation/finalize 模型：

```text
reserve -> execute -> finalize
                 -> cancel/compensate on non-billable failure
```

4. 新会话不要在请求尚未通过执行前置条件时持久化；可以在成功记录 run/message 的同一 Unit of Work 中创建。
5. 为每种失败码建立状态与 quota 断言矩阵。

---

## RM-QA-006：Ask 与 Quiz 缺少幂等保护

**优先级：P1**  
**类型：重试安全、成本控制、数据重复**

CORS 已允许 `Idempotency-Key`，Evaluation API 也已经有幂等概念，但 Ask 和 Quiz 没有读取或保存该键。浏览器双击、客户端重试、代理超时后的重发都可能：

- 重复调用 LLM/Web/Rerank；
- 重复扣 quota；
- 在同一 conversation 写入重复消息；
- 生成多个逻辑相同的 Quiz；
- 让第一次已成功但响应丢失的请求无法安全恢复。

### 推荐修复

为成本型写操作建立统一幂等表或服务：

```text
scope: user_id + operation + idempotency_key
request_hash: canonical request body hash
state: pending / succeeded / failed_retriable / failed_terminal
response: successful response snapshot or resource IDs
```

相同 key + 相同 body 应重放第一次结果；相同 key + 不同 body 应返回 409；并发相同 key 只能有一个执行者。

### 必须补充的测试

```text
test_ask_same_idempotency_key_replays_without_duplicate_messages
test_quiz_same_idempotency_key_replays_same_quiz
test_idempotency_key_body_mismatch_returns_409
test_concurrent_same_key_executes_provider_once
```

---

## RM-QA-007：本地测试无法证明生产 Adapter 与异步流水线

**优先级：P1**  
**类型：测试架构、发布证据缺口**

主要 API 工作流测试通过：

```python
TestClient(create_app(Settings(app_env="test", llm_provider="fake")))
```

并使用全局内存 Store、直接提交 `extracted_text`、同步成功 job。这条路径没有经过生产中的：

```text
R2/S3 object verification
-> outbox event
-> dispatcher
-> Celery worker
-> Docling/parser
-> embedding
-> Qdrant
-> PostgreSQL transaction/RLS-like filters
```

`test_project_scaffold.py` 中还有多项源码字符串断言，例如检查某段 SQL token 出现次数；`test_frontend_contracts.py` 主要检查文件和字符串是否存在。这些测试适合作为轻量契约哨兵，但不能证明代码真正调用了这些路径，也可能在死代码存在时继续通过。

### 推荐测试分层

#### Tier 0：快速纯逻辑测试

- relevance、token packing、quota policy、scope policy、idempotency state machine。
- 每次提交运行，目标数十秒内完成。

#### Tier 1：Adapter contract tests

同一套 Repository contract 分别运行于：

```text
InMemoryResearchMateStore
PostgresResearchMateRepository
```

重点验证 owner scope、conversation scope、active/deleted state、并发版本和事务回滚。

#### Tier 2：可丢弃集成环境

使用 CI service containers 或 Testcontainers 启动 Postgres、Redis、MinIO/S3-compatible、Qdrant，运行：

```text
upload reservation
-> object upload
-> complete
-> outbox dispatch
-> worker parse/index
-> Ask/Quiz
-> delete and cleanup
```

#### Tier 3：浏览器 E2E

引入 Playwright，以用户可见行为为断言，并用 API 检查后置状态。重点覆盖上传、处理中状态、问答引用、Quiz、个人会话隔离、登录刷新和 developer 权限。

#### Tier 4：部署后 smoke 与故障注入

在明确授权的 preview 环境验证 provider、outbox backlog、worker heartbeat、重试和恢复；保存 commit、环境、命令、结果和日志链接。

---

## RM-QA-008：多步写操作缺少完整 Unit of Work

**优先级：P1**  
**类型：部分成功、孤立状态、恢复困难**

### Quiz

```text
repository.record_run(...)
repository.save_quiz_set(...)
```

这是两个独立 Repository 调用。若 `record_run` 成功而 `save_quiz_set` 失败，会留下一个状态为 succeeded 的 run，但没有对应 QuizSet。

### 删除会话

路由先遍历会话中的每个 document，逐个调用 `delete_document`，最后再 `delete_conversation`。PostgreSQL 中每次调用都可能是独立事务。若第 N 个文件失败，会出现：

- 前 N-1 个附件已进入删除流程；
- 后续附件未处理；
- conversation 仍存在；
- 用户重试时状态更复杂。

### 推荐修复

- 数据库内的相关状态变化使用应用级 Unit of Work。
- 外部对象存储、Qdrant 和 worker 任务不要放在长事务中，而应采用 outbox + idempotent saga。
- Quiz 先创建 `generating` aggregate，provider 完成后在一个事务中写入 questions、citations 和最终状态。
- 删除会话先在一个事务中标记 conversation/dependent documents 为 `deleting` 并写入 outbox，再由异步流程逐项完成；重复事件必须幂等。

### 必须补充的测试

使用故障注入让第 N 次写入、enqueue 或外部删除失败，验证最终状态可恢复且不会出现“succeeded 但资源缺失”。

---

## RM-QA-009：MCP async middleware 直接执行同步阻塞调用

**优先级：P1**  
**类型：并发可靠性、事件循环阻塞**

`attach_request_id` 是 async middleware，但 MCP 分支中直接执行：

```text
resolve_bearer_token(...)
app.state.store.ensure_user(...)
```

生产 auth 使用 `PyJWKClient.get_signing_key_from_jwt`，缓存 miss 时可能进行同步网络请求；PostgreSQL Store 的 `ensure_user` 也是同步 SQLAlchemy I/O。Starlette 会把 `def` endpoint 和同步 dependency 放入线程池，但不会自动识别 async middleware 内任意同步函数并替你 offload。

### 影响

JWKS、DNS 或数据库稍慢时，一个 MCP 请求可能阻塞事件循环，拖慢同一进程中的其他 MCP/HTTP 请求和健康检查。

### 推荐修复

- 最佳方案：采用 async JWT/JWKS client 和 async database adapter。
- 最小修复：使用 `anyio.to_thread.run_sync` 或 Starlette `run_in_threadpool` 包裹明确的阻塞调用。
- 不要仅通过扩大线程池掩盖问题；线程池也需要并发上限和超时。
- 加入慢 JWKS、慢 DB fake 的并发测试，验证 `/healthz` 和并发请求延迟不会被线性阻塞。

---

## RM-QA-010：跨会话 Project Memory 被提升为 assistant role

**优先级：P1**  
**类型：LLM 信任边界、提示注入、上下文语义混乱**

workspace 项目会从其他会话收集历史消息，然后 `_bounded_project_memory` 把 user/assistant 内容拼成一个新的：

```python
ConversationMessage(role="assistant", content="<project_memory>...")
```

在无证据的普通聊天路径中，`build_llm_chat_answer` 按原 role 直接把该消息交给模型。这样，其他会话里由用户输入的文本被重新包装为 assistant 消息，丢失了原始 provenance 和信任级别。

### 影响

- 恶意或偶然的用户指令可能在后续会话中以更高信任角色出现。
- 模型难以区分“用户曾经说过”“助手曾经回答过”和“系统确认事实”。
- 该行为与 grounded 路径中“history is data”的设计不一致。

### 推荐修复

- 保存结构化 provenance：原 role、conversation ID、时间和来源类型。
- 将跨会话记忆作为明确的 untrusted data 放入单独 user data block，而不是 assistant role。
- system prompt 明确禁止执行 memory 内指令，只能把它当背景事实候选。
- 对“忽略系统指令”“调用工具”“泄露其他会话”等注入文本做回归测试。

---

## 5. 其他高价值问题

## RM-QA-011：语义检索和摘要失败被静默吞掉

`_semantic_candidates` 捕获 `VectorStoreRequestError` 后直接返回空列表；`_history_context` 遇到摘要 provider 错误后直接 `pass`。调用者没有获得统一的 degraded 状态，trace 可能仍把本地查询标记为 succeeded。Quiz 的两个 tool trace 还把 `latency_ms` 固定为 0。

建议引入：

```python
RetrievalOutcome(candidates, degraded, reason, provider)
SummaryOutcome(summary, updated, degraded, reason)
```

并将降级写入响应、trace、结构化日志和指标。只有明确允许降级的错误才能被吞掉；其余应 fail closed 或返回 503。

## RM-QA-012：token budget 不是硬上限

`pack_chunks`、`_bounded_history` 和 `_bounded_project_memory` 都只在“已经选中过至少一项”后检查超预算。因此首个超大 chunk 或消息即使超过预算，也会被加入。

建议：

- 第一个元素也必须受限；
- 超大 chunk 先切分或截断，并保留 truncation 元数据；
- 使用 provider-aware tokenizer 或在发送前做最后硬校验；
- 用 property-based test 断言任何输入下总 token 不超过预算。

## RM-QA-013：过宽 Service 和 Repository 正在产生策略漂移

当前主要压力点：

- `GroundedQueryService` 同时负责 quota、conversation、memory、retrieval、Web、rerank、generation、validation、trace 和 persistence orchestration。
- `ResearchMateRepository` Protocol 覆盖用户、项目、文件、job、run、trace、quiz、usage、conversation、summary 和 runtime config。
- `persistence/postgres.py` 接近两千行，包含多个独立 aggregate 的 SQL 和事务语义。
- `services/store.py` 同时定义大接口和完整内存实现。
- `chat-workspace.tsx` 同时处理加载、上传、问答、消息、错误、Web toggle 和 Quiz drawer。

这还不是 spaghetti，因为依赖方向大体可追踪，router 也较薄；但它已经违反 Interface Segregation，并让 REST/MCP、memory/Postgres 很难保持一致。此次发现的 scope 和 trace 漂移就是直接证据。

### 推荐目标结构

```text
researchmate_api/
├── modules/
│   ├── ask/
│   │   ├── service.py
│   │   ├── relevance_policy.py
│   │   ├── context_builder.py
│   │   └── ports.py
│   ├── conversations/
│   │   ├── service.py
│   │   └── scope_policy.py
│   ├── documents/
│   ├── quiz/
│   ├── traces/
│   │   └── access_policy.py
│   └── usage/
│       └── quota_service.py
├── infrastructure/
│   ├── postgres/
│   │   ├── projects.py
│   │   ├── documents.py
│   │   ├── conversations.py
│   │   ├── runs.py
│   │   └── unit_of_work.py
│   ├── qdrant.py
│   └── object_storage.py
└── interfaces/
    ├── http/
    └── mcp/
```

拆分标准应是“不同变化原因和事务边界”，而不是机械地一类一文件。HTTP 和 MCP 只做协议映射，共享同一 application service 与 policy。

## RM-QA-014：现有测试有用，但部分测试保护错误或只验证字符串

值得肯定的测试包括：跨用户 404 concealment、个人 Ask 会话隔离、REST Trace admin-only、MIME/checksum、runtime config 乐观版本和删除项目时不提前消耗 usage。

需要修正的部分：

1. `test_small_document_uses_full_context_without_keyword_gate` 的注释、名称和断言互相冲突。
2. Quiz 测试使用包含 RAG 的提示词，未覆盖默认提示和非英文资料。
3. 前端契约测试大量使用“字符串存在”作为行为证明，代码即使不可达也可能通过。
4. scaffold 测试通过统计 SQL token 或源码片段保护实现细节，重构时容易产生假失败，死代码又可能产生假通过。
5. Python coverage 启用了 branch，但总门槛只有 50%，关键安全模块可以被大量低风险代码稀释。
6. 当前前端依赖只有 Vitest/JSdom，没有可见的 Playwright E2E 门槛。
7. CI 未显示独立 type checker；Ruff 不能替代 Pyright/Mypy 的跨函数类型分析。

建议逐步采用：

- 总覆盖率先提升到 75%，核心 policy/auth/retrieval/usage 模块 branch coverage 至少 90%。
- 增加 changed-lines coverage，避免大仓库平均值掩盖新代码。
- 字符串契约测试保留少量，但主要契约改为执行行为和生成结果比较。
- 对 scope、auth、quota、idempotency 使用参数化矩阵。
- 对检索、token packing 和状态机增加 property-based test。
- 失败时上传 coverage、pytest、Playwright trace、截图和服务日志作为 CI artifact。

## RM-QA-015：API、worker 和 dispatcher 同进程扩大故障域

`render_combined.py` 将 API、Celery worker 和 outbox dispatcher 作为子进程放进同一容器。任何一个子进程退出都可能触发整个服务关闭；三者共享 CPU、内存和发布生命周期。该设计可以降低早期部署成本，但不适合作为长期可靠性边界。

建议优先拆为独立服务；若短期必须合并，则至少使用成熟 supervisor、独立 process group、明确 restart policy、资源限制和真正的 HTTP readiness，而不仅是 TCP 端口可连接。

`/readyz` 对数据库、checkpoint、heartbeat、outbox、Redis 和 Qdrant 有较好检查，这是优点；但 object storage、LLM 和 Web Search 目前主要检查“已配置”，并未证明服务可用。报告和 UI 中应把 `configured_not_probed` 与 `ready` 明确区分。

## RM-QA-016：契约与维护一致性债务

以下问题不应盖过 P0/P1，但适合在同一轮清理：

- Ask 可能返回 `502 LLM_OUTPUT_INVALID`，全局 OpenAPI responses 未声明 502。
- `dev_traces.py` 在已抛异常后还有 unreachable `RuntimeError`，权限条件也可明显简化。
- `create_app` 用宽泛的 `except ImportError: pass` 隐藏 MCP 导入失败，可能把内部缺陷误判成“SDK 未安装”。
- `UploadCompleteRequest` 没有像多数 request model 一样设置 `extra="forbid"`。
- `raise_api_error` 实际不返回，类型应标为 `NoReturn`，方便类型检查器理解控制流。
- `full_context` 分支中存在不可达或语义多余的 rerank 参数逻辑，应删除或重写。
- 根目录 `skill/SKILL.md` 实际是从 Gemini CLI 移植的 docs-writer，并不是 QA 路由；真正 QA 流程深藏在嵌套 references 中，agent 很容易加载错误入口。
- 建议在根 skill 增加明确 router/index，或把外来 docs skill 移入有语义的子目录，并在 CI 验证每个 skill 的名称、description 和入口用途一致。

---

## 6. 主要 API 功能评估

| 功能域 | 源码评估 | 现有测试 | 结论 |
|---|---|---|---|
| `/healthz` | 简单、不会等待共享同步线程池 | 有基础契约 | 源码层面正常 |
| `/readyz` | DB、heartbeat、outbox、Redis、Qdrant 检查较完整 | 缺少本次真实依赖执行证据 | **PARTIAL / GAP** |
| Auth / `/me` | REST dependency 边界较清楚；生产 JWT 校验配置严格 | dev token 测试为主 | REST 基础正常，MCP async 阻塞需修 |
| Projects | owner filter 与 hidden personal project 设计合理 | 有跨用户 concealment | 基础正常 |
| Conversations | rename/delete/owner 检查较好 | 有主要行为测试 | 删除多附件的原子性不足 |
| Documents | 文件类型、MIME、大小、checksum 和生产 object metadata 验证较好 | 本地路径覆盖较多 | 本地正常；真实 worker 流水线为 GAP |
| Ask | 结构化输出、evidence ID allowlist 和 trace 较好 | 有 happy path 和部分错误路径 | **FAIL：相关性、quota、幂等和信任边界** |
| Quiz | Schema 和四选项约束较清楚 | 非默认关键词路径通过 | **FAIL：默认检索、多语言和资源覆盖语义** |
| Sources | owner scoped 查询较清楚 | 有基础测试 | 源码层面基本正常 |
| Developer Trace | REST admin gate 存在 | REST 权限有测试 | **FAIL：MCP 权限不一致** |
| MCP | 复用应用服务的方向正确 | 未见同等协议矩阵证明 | **FAIL：个人 scope 和 trace parity** |
| Worker/outbox | 有 heartbeat、outbox 和 job 设计 | 本次无完整集成执行 | **GAP** |
| Web/Qdrant/Rerank | 有 provider 抽象和 degraded 字段 | 真实 provider 证据不足 | **PARTIAL / GAP** |

---

## 7. 代码质量与架构结论

### 7.1 值得保留的设计

- 路由多数只做依赖注入、错误映射和响应建模，没有把所有业务直接写进 controller。
- Pydantic 对消息长度、Quiz 数量、MIME、文件大小和 checksum 做了明确限制。
- 生产配置对 auth、PostgreSQL、Redis、object storage、LLM、embedding、Qdrant、Web Search 和 Langfuse 有 fail-fast 校验。
- grounded LLM 输出要求 evidence ID 来自服务端 allowlist，并把 evidence 文本声明为不可信数据。
- PostgreSQL `record_run` 会在写入前重新检查 active project，并对 conversation/project 做锁定，说明作者已经意识到删除与 Ask 的竞态。
- 运行时 rerank config 有版本号和 optimistic concurrency。
- `/readyz` 不通过付费 provider 调用来做探针，避免健康检查产生费用，这是正确取舍。

### 7.2 当前是否已经 spaghetti

**结论：还不是，但已经处于需要主动控制的临界点。**

判断依据不是文件行数本身，而是：

- 同一业务策略在 REST、MCP、memory 和 Postgres 中重复表达；
- 不同协议通过不同底层方法取得同一类数据；
- Repository 同时承载数据访问和部分权限语义；
- 一个 service 中出现过多顺序敏感副作用；
- 已经出现个人 scope、trace role 和 Quiz 语义漂移。

如果继续在 `GroundedQueryService`、`ResearchMateRepository` 和 `postgres.py` 中横向添加功能，未来很容易形成真正的 spaghetti。当前最优策略不是大重写，而是先把**共享 policy、事务边界和 application service**抽出来，随后按模块渐进拆分。

---

## 8. 建议的新测试清单

| 测试名称 | 层级 | 主要证明 |
|---|---|---|
| `test_mcp_personal_search_cannot_cross_conversations` | API/MCP | conversation scope 不可绕过 |
| `test_trace_access_matrix_is_identical_for_rest_and_mcp` | Contract | 两种协议权限一致 |
| `test_full_context_unrelated_query_abstains_without_citations` | Unit/API | full-context 不绕过相关性 |
| `test_quiz_default_prompt_works_for_chinese_documents` | API | 默认 Quiz 不依赖英文词项 |
| `test_quiz_reports_actual_document_coverage` | API | UI 承诺与实际覆盖一致 |
| `test_failed_ask_quota_semantics` | Unit/API | 每类失败的 quota 行为明确 |
| `test_ask_idempotency_replays_without_duplicate_message` | Integration | 重试不重复调用和写入 |
| `test_repository_scope_contract_memory_and_postgres` | Adapter contract | 两种 Store 行为一致 |
| `test_quiz_transaction_rolls_back_on_question_insert_failure` | Integration | 不产生孤立 succeeded run |
| `test_conversation_delete_recovers_after_nth_document_failure` | Integration/fault | 半删除可恢复 |
| `test_worker_outbox_recovery_after_dispatcher_crash` | Integration/fault | at-least-once 事件保持幂等 |
| `test_mcp_slow_jwks_does_not_block_healthz` | Concurrency | async event loop 不被同步 I/O 阻塞 |
| `test_project_memory_preserves_untrusted_provenance` | Unit/security | 用户文本不被提升为 assistant |
| `test_pack_chunks_never_exceeds_budget` | Property | token budget 是硬约束 |
| `test_upload_to_answer_preview_journey` | Playwright E2E | 用户主路径闭环 |
| `test_personal_chat_attachment_isolation_in_browser_and_mcp` | Playwright/API | UI 与 MCP 同时满足隐私边界 |

---

## 9. 修复顺序

### 阶段 A：下一次部署前必须完成

1. 修复 personal project 的 MCP conversation scope。
2. 统一 REST/MCP Trace access policy。
3. 将 full-context 改为 packing 优化，并加入 answerability gate。
4. 修复 Quiz 默认 prompt 和非英文资料路径。
5. 删除或重写与产品意图相反的测试。
6. 在 memory 与 Postgres 两种实现上执行对应的 scope/权限 contract tests。

### 阶段 B：可靠性硬化

1. 定义 quota 语义并调整副作用顺序。
2. 为 Ask/Quiz 增加幂等键和并发保护。
3. 为 Quiz 保存、会话删除建立 Unit of Work / saga。
4. 修复 MCP middleware 的同步阻塞。
5. 将所有降级结果写入 trace、日志和指标。
6. 建立真实 Adapter 的 disposable integration suite。

### 阶段 C：结构治理

1. 抽出 scope、trace、quota、relevance 等纯 policy。
2. 按 aggregate 拆分 PostgreSQL Repository 和大 Protocol。
3. 拆分 `GroundedQueryService` 的编排职责。
4. 把 `chat-workspace.tsx` 拆成 upload、thread、composer、quiz 等可独立测试组件。
5. 增加 Pyright/Mypy、Playwright、changed-lines coverage 和 CI artifacts。
6. 评估拆分 API、worker 和 dispatcher 的部署故障域。

---

## 10. 发布判定

### 当前判定

```text
STOP / BLOCKED
```

### 阻塞理由

- 已确认的 personal conversation scope 绕过。
- 已确认的无关引用行为。
- 已确认的默认 Quiz 语义缺陷。
- 已确认的 REST/MCP 权限不一致。
- 缺少 exact-commit 的完整 Actions 与生产 Adapter 运行证据。

### 解除阻塞的最低证据

1. RM-QA-001 至 RM-QA-004 修复并有负向回归测试。
2. `npm run check:all` 在修复后的准确 commit 上通过。
3. memory/Postgres adapter contract suite 均通过。
4. preview 环境完成 upload → process → Ask → Quiz → delete 的 smoke test。
5. REST/MCP 权限矩阵和 personal conversation 隔离测试通过。
6. 保存测试命令、commit SHA、环境、结果、失败 artifact 和已知剩余风险。

在这些条件满足前，Vercel 构建成功只能证明特定部署检查成功，不能替代 API、worker、数据隔离和 RAG 正确性验证。

---

## 11. 参考资料

### 仓库内事实源

```text
skill/indie-product-delivery/references/nodes/05-qa-review-security-hardening/
.github/workflows/ci.yml
package.json
apps/web/package.json
requirements-dev.txt
tests/test_api_workflow.py
tests/test_project_scaffold.py
tests/test_frontend_contracts.py
apps/api/src/researchmate_api/main.py
apps/api/src/researchmate_api/dependencies.py
apps/api/src/researchmate_api/mcp_server.py
apps/api/src/researchmate_api/services/grounded_query.py
apps/api/src/researchmate_api/services/retrieval.py
apps/api/src/researchmate_api/services/answering.py
apps/api/src/researchmate_api/services/store.py
apps/api/src/researchmate_api/persistence/postgres.py
apps/api/src/researchmate_api/routers/quiz.py
apps/api/src/researchmate_api/routers/dev_traces.py
apps/api/src/researchmate_api/routers/conversations.py
apps/web/app/components/chat-workspace.tsx
```

### 外部方法来源

- OWASP API Security Top 10 2023：Broken Function Level Authorization、Unrestricted Resource Consumption。
- FastAPI 官方 Testing 文档。
- pytest 官方 Good Integration Practices。
- Playwright 官方 API Testing、Best Practices、Web Server 和 Trace 文档。
- coverage.py 官方 Branch Coverage 文档。
- Starlette 官方 Thread Pool 文档。
- Python 官方 asyncio “Running Blocking Code” 文档。
- Fugazi `test-automation-skills-agents`。
- OpenAI Agents Python `AGENTS.md` 中的 code-change verification 要求。

