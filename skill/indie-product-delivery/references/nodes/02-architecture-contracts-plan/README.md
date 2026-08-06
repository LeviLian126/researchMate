# 系统设计

接收 Node01 的规格说明并产出可构建的架构交接文档：使用 deep-module 原则定义模块边界、明确接口契约、完成数据模型、强制信任边界、选择演化和部署策略。Node03 或 Node04 应能在不猜测系统行为的情况下实施。

## 阅读相关工作流

| 需求 | 阅读 |
| --- | --- |
| 阅读已有代码、查找复用路径、定义模块边界、依赖方向、部署拓扑 | `system-discovery-and-modules.md` |
| 定义接口契约、数据模型、信任边界、演化和迁移策略 | `contracts-data-and-trust.md` |

线性流程：先发现（理解现有系统），然后契约（设计新契约）。并非每个项目都需要完整运行两个阶段。一个只改变单个现有模块的窄功能，在快速发现确认复用路径后可以跳到契约阶段。

## 与下游节点的边界

Node02 做架构级决策。下游节点执行它们。

| Node02 决定（架构） | 下游节点执行 |
| --- | --- |
| 模块边界和接口接缝 | Node03/04 编写实现代码 |
| 部署拓扑（VPS、SQLite、adapter） | Node06 配置并运行部署 |
| 演化策略和兼容窗口 | Node06 执行迁移和发布 |
| 信任边界强制执行点 | Node05 验证强制执行有效 |
| 测试接缝和依赖类别 | Node03/04 编写测试，Node05 验证质量 |
| 数据模型和 schema 语义 | Node03 实现 schema，Node06 运行迁移 |

## 输出契约：Architecture Handoff

```markdown
# Architecture Handoff: [Feature Name]

## Source spec
[Node01 spec reference or summary]

## System context
[One-sentence description of the existing system + the boundary of this change]

## Module design
| Module | Interface (seam) | Depth | Adapters | Dependencies |
|---|---|---|---|---|
[Each module: interface definition, deep/shallow assessment, adapters, dependency category]

## Deployment topology
[hosting/data/backend/frontend/realtime/external service architecture choices]

## Data model
[Persistent entities, fields, states, lifecycle, relationships, constraints]

## Interface contracts
[Each cross-boundary interface: caller, input, authz, success, errors, idempotency]

## Trust boundaries
[subject -> resource -> action -> scope -> enforcement -> failure -> evidence]

## Evolution strategy
[Breaking change: compatibility window, migration path, rollback plan. Non-breaking: N/A]

## ADRs
[Only decisions meeting 3 conditions: hard to reverse + surprising + real trade-off]

## Open decisions
[Unresolved architecture questions, each with owner and latest safe decision point]

## Decision
- [ ] GO: Node03/04 can begin implementation
- [ ] NO_GO: unresolved architecture blocker, needs Node01 or user decision
```

Node03/04 在收到此交接文档后不应需要做架构决策。Node06 不应需要设计迁移或发布策略，只需执行它。