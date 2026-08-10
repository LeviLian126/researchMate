# 契约、数据与信任

为每个跨边界接口、数据实体和信任边界定义明确的契约。设计演化和迁移策略。Node03/04 不应需要猜测行为。Node06 应有清晰的策略来执行。

## 步骤 1：构建能力脊柱

将 Node01 规格说明中每个已批准的能力映射穿过系统：

```
capability -> entry -> interface/access -> domain policy -> data/provider
-> observable result or recoverable failure -> local proof
```

在每个箭头处命名现有的所有者，或标记为新建。缺失所有者是一个设计信号，不是将所有行为放入 controller 的许可。

## 步骤 2：定义接口契约

对于每个跨越所有权或信任边界的接口（HTTP 路由、CLI 命令、事件、webhook、管理操作）：

| 契约字段 | 必须定义 |
|---|---|
| caller | user、admin、service、CLI、provider 或 job |
| input | 来源、允许的字段、规范化、大小或速率边界 |
| identity | session、token、signature、service identity 或 command context |
| scope | tenant、account、owner、object、role、entitlement |
| success | 结果形状、重定向或事件、持久化副作用 |
| errors | validation、unauthenticated、denied、absent、conflict、provider、internal |
| idempotency | 重复请求时会发生什么（去重键？重复数据？双重收费？） |

**核心规则：**
- UI 守卫不是认证强制执行点。服务端必须独立验证 identity 和 scope。
- 客户端提供的 role、owner、price 和 entitlement 值在强制执行点确认之前是不可信的。
- 不要因为 happy path 简单就从新入口返回不一致的临时对象。使用 repository 已有的 error mapper。
- 在不可信边界处进行规范化和验证。将 request body、query param、cookie、header、form action、CLI arg、webhook payload、upload 和 model output 视为不可信，直到验证通过。

## 步骤 3：定义数据模型

对于每个持久化实体（table、document、object 或 provider 支持的记录）：

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

对于重要的读取，定义：过滤、排序、分页、权限过滤、空状态、过期状态和索引压力。不要选择具体的索引或查询实现，除非该选择对架构有重大影响。

对于驱动产品工作流的每个查询，命名其一致性期望：刚完成的写入是否必须立即出现、短暂的过期视图是否可接受、以及用户在数据追赶期间看到什么状态。

## 步骤 4：定义信任边界

对于每个受保护的读取、列表、变更、管理路径、job、provider 回调或上传：

```
subject -> resource -> action -> scope -> enforcement -> failure -> evidence
```

| 关注点 | 回答 |
|---|---|
| identity | 谁或什么在行动：user、tenant、admin、service、provider、job？ |
| scope | 哪个 account、org、object、plan 或 region 适用？ |
| enforcement | 决策在哪里强制执行？调用方能否绕过它？ |
| untrusted input | 哪些 client、callback、upload 或 model output 必须被检查？ |
| failure | 什么被拒绝？什么可见？什么被安全记录？谁能恢复？ |

**对于 AI 和 LLM 路径：** prompt、检索到的内容和 model output 是提案，绝非权威。在任何 AI 衍生的副作用之前，确定性的服务端策略必须重新确立 identity、scope、permission 和参数约束。prompt 指令或 model 置信度不能替代该强制执行。

## 步骤 5：演化和兼容性检查清单

这是架构级策略设计。Node06 按此策略执行迁移和发布，但策略在此决定。

仅当变更涉及 breaking change 时运行此检查清单。不适用时标记 N/A。

对于每个公开契约变更：

| 变更类型 | 是否 breaking？ | 必须做 |
|---|---|---|
| 新增可选字段或操作 | 否（增量） | 记录语义，保持先前行为 |
| 新增必填字段 | 是（可能） | 列出受影响的调用方，定义默认值或兼容路径 |
| 重命名或位置变更 | 是（除非保留旧别名） | 定义别名、迁移通知、移除条件 |
| enum 或 state 扩展 | 消费方敏感 | 验证调用方能容忍未知或新 state |
| error 形状或 code 变更 | 消费方敏感 | 保持可恢复的语义，更新 error-to-fix 指引 |
| auth 或 authz 变更 | 信任影响 | 重新评估访问、失败行为和审批 |
| 时序或 async 变更 | 行为影响 | 定义 pending、completion、callback 和 timeout 语义 |
| idempotency 变更 | 数据影响 | 定义重放安全性和持久化去重标识 |
| 移除或弃用 | breaking | 盘点消费方，定义迁移、弃用路径和审批 |

**一个 breaking change 必须有：** 消费方盘点、兼容窗口、迁移路径和回滚计划。一个不可逆变更必须有备份和前滚计划。

**迁移设计（架构级）：** 对于涉及数据迁移的变更，设计扩展-收缩策略：先扩展兼容的 schema，然后迁移读写，最后清理旧结构。说明回滚是否安全。Node06 按此策略执行具体的迁移操作。

## 步骤 6：记录 ADR

仅当以下三个条件全部为真时才记录 ADR（来自 domain-modeling）：

1. **难以逆转** — 后续改变决策的成本是实质性的。
2. **没有上下文会令人困惑** — 未来的读者会想"他们为什么这样做？"
3. **真实的权衡** — 存在真正的替代方案，你出于特定原因选择了一个。

如果三者之一缺失，跳过 ADR。

ADR 格式：
``+Context -> decision -> options rejected -> evidence -> consequences ->
cost and exit -> compatibility -> revisit trigger -> approval state
``

保持 ADR 可从项目看板发现。除非用户要求或理由需要持久的独立检索，否则不要添加单独的 ADR 产物。

## 步骤 7：维护领域术语表

如果设计产生或细化了领域术语：

- 一个术语与已有 CONTEXT.md 语言冲突 — 立即指出。
- 一个术语模糊或重载 — 提出精确的规范术语。
- 一个术语已确定 — 立即更新 CONTEXT.md，不要批量处理。

CONTEXT.md 仅是术语表，不是规格说明或草稿本。不含实现细节。

## 步骤 8：产出交接文档

将所有步骤综合为 `README.md` 中定义的 Architecture Handoff 文档。

## 契约完成时

- 每个已批准的能力都有能力脊柱。
- 每个跨边界接口都有完整的契约定义。
- 每个持久化实体都有数据模型。
- 每个信任边界都有强制执行定义。
- breaking change 有兼容性、迁移和回滚策略（架构级；执行路由到 Node06）。
- ADR 仅记录满足 3 个条件的决策。
- 每个未决决策都有所有者和最晚安全决策点。