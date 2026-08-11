# 契约、数据与信任

为每条跨越边界的接口、数据实体和信任边界定义显式契约。设计演进和迁移策略。Node03/04 不应需要猜测行为。Node06 应有可执行的清晰策略。

## 步骤 1：构建能力脊柱

将 Node01 规格说明中每条已批准的 capability 沿系统映射：

```
capability -> entry -> interface/access -> domain policy -> data/provider
-> observable result or recoverable failure -> local proof
```

在每个箭头处命名现有的所有者，或标记为 new。缺失所有者是一个设计信号，而不是把所有行为塞进某个 controller 的许可。

## 步骤 2：定义接口契约

对每条跨越所有权或信任边界的接口（HTTP 路由、CLI 命令、事件、webhook、admin 操作）：

| 契约字段 | 必须定义 |
|---|---|
| caller | user、admin、service、CLI、provider 或 job |
| input | 来源、允许的字段、归一化、大小或速率边界 |
| identity | session、token、signature、service identity 或 command context |
| scope | tenant、account、owner、object、role、entitlement |
| success | 结果形态、redirect 或 event、持久副作用 |
| errors | validation、unauthenticated、denied、absent、conflict、provider、internal |
| idempotency | 重复请求时会发生什么（dedup key？重复数据？双重扣费？） |

**核心规则：**
- UI 守卫不是 auth 执行点。服务端必须独立验证 identity 和 scope。
- 客户端提供的 role、owner、price 和 entitlement 值在执行点确认之前是不可信的。
- 不要因为 happy path 简单就从新入口返回不一致的 ad hoc 对象。使用仓库已有的 error mapper。
- 在不可信边界处进行归一化和校验。将 request body、query 参数、cookie、header、form action、CLI 参数、webhook 载荷、上传和模型输出在验证之前视为不可信。

## 步骤 3：定义数据模型

对每个持久化实体（table、document、object 或 provider-backed record）：

```markdown
## [Entity name]
- Meaning and owner: product meaning, owning module, tenant scope
- Identity: primary key, external ID, uniqueness, duplicate behavior
- Fields: type, nullable or default, sensitivity
- States: allowed states, transition owner, terminal or retryable states
- Lifecycle: create, read, list, update, delete, export, retention
- Relationships: cardinality, ownership, cascade behavior
- Integrity: constraints, concurrency rule, idempotency rule
- Visibility: subject scope, admin access, redaction
```

对于重要的读操作，定义：filter、sort、pagination、permission filter、empty state、stale state 和 index pressure。除非该选择在架构层面重要，否则不要选择具体的 index 或 query 实现。

对每个驱动产品工作流的 query，命名其一致性预期：刚完成的写入是否必须立即出现、短暂的 stale 视图是否可接受、以及数据赶上时用户看到的是哪个状态。

## 步骤 4：定义信任边界

对每个受保护的读、list、mutation、admin path、job、provider callback 或 upload：

```
subject -> resource -> action -> scope -> enforcement -> failure -> evidence
```

| 关注点 | 回答 |
|---|---|
| identity | 谁或什么在行动：user、tenant、admin、service、provider、job？ |
| scope | 适用于哪个 account、org、object、plan 或 region？ |
| enforcement | 决策在哪里执行？调用方能否绕过？ |
| untrusted input | 哪些 client、callback、upload 或模型输出必须检查？ |
| failure | 什么被拒绝？什么可见？什么被安全地记录？谁可恢复？ |

**对于 AI 和 LLM 路径：** prompt、检索到的内容和模型输出是 proposal，从来不是 authority。在任何 AI 衍生的副作用之前，确定性的服务端策略必须重新建立 identity、scope、permission 和参数约束。Prompt 指令或模型置信度不能替代该执行。

## 步骤 5：演进与兼容性清单

这是架构级的策略设计。Node06 按此策略执行迁移和 rollout，但策略在这里决定。

仅当变更涉及 breaking change 时运行此清单。不适用时标记 N/A。

对每处公开契约变更：

| 变更类型 | 是否 breaking？ | 必须做 |
|---|---|---|
| 新增可选字段或动作 | 否（增量） | 记录语义，保留既有行为 |
| 新增必填字段 | 是（可能） | 列出受影响的调用方，定义默认值或兼容路径 |
| 重命名或位置变更 | 是（除非保留旧 alias） | 定义 alias、迁移通知、移除条件 |
| enum 或 state 扩展 | 对消费者敏感 | 验证调用方容忍未知或新 state |
| error 形态或 code 变更 | 对消费者敏感 | 保留可恢复含义，更新 error-to-fix 指引 |
| auth 或 authz 变更 | 影响信任 | 重新评估 access、失败行为和审批 |
| 时序或异步变更 | 影响行为 | 定义 pending、completion、callback 和 timeout 语义 |
| idempotency 变更 | 影响数据 | 定义 replay 安全性和持久化重复 identity |
| 移除或弃用 | breaking | 盘点消费者，定义迁移、弃用路径和审批 |

**一条 breaking change 必须有：** 消费者盘点、兼容窗口、迁移路径和回滚计划。一条不可逆变更必须有备份和 roll-forward 计划。

**迁移设计（架构级）：** 对于涉及数据迁移的变更，设计 expand-and-contract 策略：先扩展兼容 schema，再迁移读写，最后清理旧结构。说明回滚是否安全。Node06 按此策略执行具体的迁移操作。

## 步骤 6：记录 ADR

仅当以下三条全部为真时记录 ADR（来自 domain-modeling）：

1. **难以逆转** — 后来改变此决策的代价是可观的。
2. **无上下文时令人惊讶** — 未来的读者会问"他们为什么这样做？"
3. **真实权衡** — 确实存在备选方案，且你出于具体理由选择了一个。

如果三条中任一缺失，跳过 ADR。

ADR 格式：
``+Context -> decision -> options rejected -> evidence -> consequences ->
cost and exit -> compatibility -> revisit trigger -> approval state
``

让 ADR 可从项目看板发现。除非用户要求或理由需要持久的独立检索，否则不要新增独立的 ADR artifact。

## 步骤 7：维护领域词汇表

如果设计产生或精炼了领域术语：

- 某术语与已有 CONTEXT.md 措辞冲突 — 立即标出。
- 某术语模糊或被重载 — 提出一个精确的规范术语。
- 某术语被解决 — 立即更新 CONTEXT.md，不要批量处理。

CONTEXT.md 只是词汇表，不是 spec 或草稿本。不含实现细节。

## 步骤 8：生成交接

将所有步骤综合为 `README.md` 中定义的架构交接文档。

## 契约完成时

- 每条已批准的 capability 都有能力脊柱。
- 每条跨边界接口都有完整的契约定义。
- 每个持久化实体都有数据模型。
- 每条信任边界都有执行定义。
- Breaking change 有兼容、迁移和回滚策略（架构级；执行路由到 Node06）。
- ADR 只记录满足三条的决策。
- 每个未决事项都有所有者和最晚安全决策点。
