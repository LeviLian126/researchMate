# 后端构建

## 阅读相关 workflow

对于任何非平凡的实现工作,首先阅读 `slice-framing.md`。然后只阅读与你的切片所涉及的层相匹配的文件。

| 需求 | 阅读 |
|---|---|
| 框架化已批准的切片;恢复实现真相;构建实现主干 | `slice-framing.md` |
| 实现领域行为、用例所有权、状态转换、策略 | `domain-build.md` |
| 实现 HTTP、CLI、event 或 webhook 边界;validation、auth enforcement、error mapping | `interface-build.md` |
| 实现 repository、查询、transaction、schema 演进、并发 | `persistence-build.md` |
| 实现 provider adapter、job、callback、idempotency、对账 | `provider-async-build.md` |
| 实现 LLM、RAG、agent loop、tool-calling、MCP、evaluation 或 AI 可观测性分支 | `ai-application-build.md` |
| 锁定核心行为、从真实边界调试、添加相称的可观测性 | `proof-debug-observability.md` |

当产品含义或公共 contract 仍未确定时,返回 Node01 或 Node02。Node03 编写并验证高质量实现代码;Node05 负责独立质量审查,Node06 负责发布执行。

## 输出 contract

返回变更后的后端接口、所属模块和 contract、data/provider/async 效果、核心代码测试和验证运行、已添加或缺失的可观测性、文档影响,以及剩余的实现风险或阻塞项。

设置一个实现状态:

| 状态 | 使用时机 |
|---|---|
| `BUILT` | 请求的实现和必需的 hermetic 验证已完成。已部署或环境证据中已命名的缺口已列出,但不阻塞实现声明。 |
| `BLOCKED` | 一个必需的实现事实、安全验证、凭证或环境不可用。说明缺失了什么以及尝试了什么。 |
| `NEEDS_CONTRACT` | 一个 contract、边界、runtime、兼容性或恢复设计必须在实现能够正确继续之前改变。说明必须改变什么并路由到 Node02。 |

不要从 Node03 发布质量或发布裁决。