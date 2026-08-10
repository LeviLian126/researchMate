# 系统发现与模块设计

理解现有系统，找到可复用路径，定义模块边界和依赖方向，选择部署拓扑。使用 deep-module 词汇而非抽象分类表。

## 步骤 1：阅读 Node01 规格说明

从 Node01 交接文档中提取：目标用户、核心任务、验收标准、范围（在范围内、在范围外、非目标）和风险假设。

用一句话陈述架构问题：
> 什么系统能力现在必须存在，为谁存在，在哪些约束下，什么结果必须保持可观察？

确认变更不会悄然改变产品承诺（用户、定价、隐私立场）。如果产品决策未决，路由回 Node01。

## 步骤 2：审计已有代码

仅审计与此变更相关的内容。不要做全仓库调查。

**定位热点（来自 improve-codebase-architecture）：**
- 如果用户指定了方向（模块、子系统、痛点），直接去那里。
- 否则，运行 `git log --oneline` 找到在最近提交中反复出现的文件和区域。让那些路径优先吸引你的注意力。

**检查内容：**
- 入口点：routes、actions、CLI commands、events
- 领域：use-case 所有者、state 规则、事务风格
- 数据：repositories、schema、query 过滤器、约束
- 访问：session、signature、role、tenant 强制执行
- 外部：adapters、jobs、callbacks、timeout 和 retry 约定
- 测试：framework、helpers、fixtures、断言风格
- 配置：env 名称、feature flags、当前 diff

对于每个区域，记录：它现在拥有什么？谁调用它？它能改变什么数据？哪种模式已经在运作且应被保持？

**在问用户之前先查找事实。** 可发现的事实（代码、配置、文档）不是问题。仅在产品或业务决策时路由到 Node01 或用户。

## 步骤 3：构建复用地图

对于每个子问题，在提出新层之前先找到最强的已有路径。

| 子问题 | 已有路径 | 决策 | 原因 |
|---|---|---|---|
| 能力或流程 | module、route、job、provider 或 none | reuse / extend / replace / new | repo 和产品匹配度 |

- **Reuse**：一条完整且合适的路径。直接使用它。
- **Extend**：改变一个经过验证的所有者，不创建平行概念。
- **Replace**：有已命名的缺陷和演化路径。
- **New**：检查后不存在合适的路径。

不要仅因为局部方便就创建第二个事实来源、第二个授权路径或第二个 provider adapter。

## 步骤 4：定义模块边界

使用 deep-module 词汇（来自 codebase-design）：

- **Module**：有 interface 和 implementation 的东西 — 函数、类、包或跨层切片。
- **Interface**：调用方正确使用 module 必须知道的一切：类型签名、不变量、顺序约束、error 模式、所需配置和性能特征。
- **Seam**：你可以在不编辑该处的情况下改变行为的地方 — interface 所在之处。
- **Depth**：interface 处的杠杆。调用方每学习一个单位的 interface 能行使多少行为。Deep = 小 interface 背后的大行为。
- **Adapter**：在 seam 处满足 interface 的具体事物。

**对于每个 module，问：**
- 我能减少方法数量吗？
- 我能简化参数吗？
- 我能在内部隐藏更多复杂性吗？
- 如果我删除这个 module，复杂性是消失了（pass-through，应合并到调用方）还是扩散到 N 个调用方（它在发挥作用，保留它）？

**删除测试（强制）：** 对于每个新建或变更的 module，想象删除它。如果复杂性消失，它是 pass-through — 合并到其调用方。如果复杂性扩散到多个调用方，它在发挥作用 — 保留它。删除测试不是可选的修饰。LLM 生成的代码典型地过度产生 pass-through module、过早抽象和浅 interface。删除测试在实现开始之前捕获最常见的架构失败模式。

**Seam 纪律（来自 DEEPENING）：**
- 一个 adapter 意味着假设性的 seam。两个 adapter 意味着真实的 seam。不要引入 port，除非至少有两个 adapter 是合理的（通常是生产加测试）。单 adapter 的 seam 只是间接层。
- 内部 seam（module 私有，供其自身测试使用）不会因为测试使用而通过外部 interface 暴露。

**Module 层级和依赖方向：**

| 层 | 拥有 | 可以依赖 | 不得拥有 |
|---|---|---|---|
| UI/view | 可见状态和用户意图 | client contract | 业务真相或 authz 强制执行 |
| entry/controller | 传输转换和请求边界 | service/domain | provider 特定策略 |
| service/domain | use-case 编排和不变量 | repository/provider contract | transport/UI 细节 |
| repository/data | 持久化和查询映射 | database/store | 调用方策略或外部工作流 |
| provider adapter | 外部规范化和凭证 | provider SDK/protocol | 产品或业务所有权 |
| job/script/realtime | 调度或事件生命周期 | service 和 adapter contract | 重复的领域规则 |

不要仅为了让此表看起来完整而引入 framework。在边界真正重要的地方保持 interface 稳定、机制可替换。

## 步骤 5：分类依赖，决定测试策略

对于每个 module 的依赖，分类以决定如何测试（来自 DEEPENING）：

| 类别 | 示例 | 测试策略 |
|---|---|---|
| In-process | 纯计算、内存状态、无 I/O | 直接通过 interface 测试，不需要 adapter |
| Local-substitutable | PGLite 替代 Postgres、内存文件系统 | 在测试套件中使用替代物 |
| Remote but owned | 你自己的 microservice、内部 API | 定义 port，生产用 HTTP/gRPC adapter，测试用 in-memory adapter |
| True external | Stripe、Twilio、第三方服务 | 注入 port，测试用 mock adapter |

**替换，不要叠加（来自 DEEPENING）：**
- 浅 module 上的旧单元测试在深化 module 的 interface 处有测试后变为废料 — 删除它们。
- 在深化 module 的 interface 处编写新测试。interface 是测试面。
- 测试通过 interface 断言可观察的结果，而非内部状态。
- 测试应能在内部重构后存活 — 它们描述行为，而非实现。

## 步骤 6：当存在真正的架构分叉时进行比较

并非每个变更都需要这一步。仅当合理的工程师可能选择不同的系统形态时。

- 始终将当前、原生或最小路径作为其中一个选项。
- 仅当更持久路径的天花板或退出价值可信时才添加它。
- 对于每个选项：repo 匹配度、契约覆盖、复杂性、运营成本、可逆性、验证负担。
- 推荐一个。说明被拒绝的选项为何现在不被选择，以及它们如何可以被重新审视。
- 不要制造虚假选择以显得全面。

## 步骤 7：选择部署拓扑

部署拓扑是架构决策，不是执行细节。Node06 执行配置，但拓扑形态在此决定。

**应用独立开发者基线**（仅当现有约定不安全或过时时）：

| 层 | 基线 | 重新考虑的条件 |
|---|---|---|
| hosting | 小型 VPS、Nginx | hosting、控制或合规需求不同 |
| data | SQLite with PRAGMAs、备份、迁移 | 写入争用、多实例、搜索或分析压力 |
| backend | 原生 PHP 或 Python services、repositories、cron | 重复的 middleware、validation 或 auth 需要更强支持 |
| frontend | 原生 CSS/JS | 真实的共享状态、组件或路由需要构建栈 |
| realtime | 仅在 request/response 不适用时使用原生 Node.js | realtime 或长生命周期协议实际上不需要 |
| external | 适配 Stripe、R2、OpenFreeMap（当匹配时） | 产品、合规、能力或退出需求不同 |

记录使变更有必要的条件，而非用"未来规模"作为模糊理由。当写入争用、多实例、分析或搜索需求被证明时考虑 Postgres。当需要重试、长任务、并行或持久状态时考虑 queue。当重复的路由、middleware、validation 或 auth 开销是真实的时考虑 framework。

## 发现完成时

- 现有系统和变更边界可以用一句话陈述。
- 复用地图完整（每个子问题有 reuse、extend、replace 或 new 决策）。
- 每个新建或变更的 module 已通过删除测试。
- 依赖已分类（每个外部依赖有已知的测试策略）。
- 部署拓扑已选择或确认为现有。
- 如果存在真正的架构分叉，已比较 2 到 3 个选项并选定一个。