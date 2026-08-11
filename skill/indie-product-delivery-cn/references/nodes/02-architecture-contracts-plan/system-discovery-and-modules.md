# 系统发现与模块设计

理解现有系统、寻找可复用路径、定义模块边界和依赖方向，并选择部署拓扑。使用 deep-module 词汇，而非抽象分类表。

## 步骤 1：阅读 Node01 规格说明

从 Node01 交接中提取：目标用户、核心任务、验收标准、范围（in、out、非目标）和风险假设。

用一句话陈述架构问题：
> 现在必须存在什么系统能力、为谁、在哪些约束下、并且什么结果必须保持可观察？

确认变更没有悄悄改变产品承诺（用户、定价、隐私立场）。如果产品决策未决，路由回 Node01。

## 步骤 2：审计已有代码

只审计与此变更相关的部分。不要做全仓库巡检。

**定位热点：**
- 如果用户指明了方向（模块、子系统、痛点），直接前往。
- 否则，运行 `git log --oneline` 找到在最近 commits 中反复出现的文件和区域。让那些路径先吸引你的注意力。

**检查什么：**
- 入口：路由、action、CLI 命令、事件
- 领域：use-case 所有者、状态规则、事务风格
- 数据：repository、schema、query filter、约束
- 访问：session、signature、role、tenant 执行
- 外部：adapter、job、callback、timeout 和 retry 约定
- 测试：框架、helper、fixture、断言风格
- 配置：env 名、feature flag、当前 diff

对每个区域记录：它现在拥有什么？谁调用它？它能改变什么数据？哪种模式已经在工作并应被保留？

**先查事实再问用户。** 可发现的事实（代码、配置、文档）不是问题。只有在产品或业务决策时才路由到 Node01 或用户。

## 步骤 3：构建复用映射

对每个子问题，在提出新层之前先找到最强的现有路径。

| 子问题 | 现有路径 | 决策 | 理由 |
|---|---|---|---|
| capability 或 flow | module、route、job、provider 或 none | reuse / extend / replace / new | 仓库和产品契合度 |

- **Reuse**：一条完整且合适的路径。直接使用。
- **Extend**：改变一个已证明的所有者，而不创造平行概念。
- **Replace**：已有具名的缺陷，并有演进路径。
- **New**：经检视后不存在合适路径。

不要因为局部方便就创造第二个真相源、第二条授权路径或第二个 provider adapter。

## 步骤 4：定义模块边界

使用 deep-module 词汇：

- **Module**：有 interface 和 implementation 的东西 — 函数、类、package 或跨层切片。
- **Interface**：调用方要正确使用模块所必须知道的一切：类型签名、不变量、顺序约束、错误模式、所需配置和性能特征。
- **Seam**：你可以在不就地编辑的情况下改变行为的位置 — interface 所在之处。
- **Depth**：interface 处的杠杆。调用方每学习一单位 interface 能调用多少行为。Deep = 小 interface 背后的大行为。
- **Adapter**：在 seam 处满足 interface 的具体事物。

**对每个模块，问：**
- 我能减少方法数量吗？
- 我能简化参数吗？
- 我能在内部隐藏更多复杂度吗？
- 如果我删除这个模块，复杂度会消失（pass-through，应合并进调用方）还是扩散到 N 个调用方（它在挣其薪水，保留它）？

**删除测试（强制）：** 对每个新增或变更的模块，设想删除它。如果复杂度消失，它是 pass-through — 合并进其调用方。如果复杂度扩散到多个调用方，它在挣其薪水 — 保留。删除测试不是可选的修饰。LLM 生成的代码特征性地过度产出 pass-through 模块、过早抽象和浅 interface。删除测试在实现开始之前捕获最常见的架构失败模式。

**Seam 纪律：**
- 一个 adapter 意味着假设性 seam。两个 adapter 意味着真实 seam。除非至少有两个 adapter 有正当理由（通常是生产加测试），否则不要引入 port。单 adapter 的 seam 只是一层间接。
- 内部 seam（模块私有、为其自身测试所用）不应仅因测试使用就通过外部 interface 暴露。

**模块层级与依赖方向：**

| 层级 | 拥有 | 可依赖 | 不得拥有 |
|---|---|---|---|
| UI/view | 可见状态和用户意图 | client 契约 | 业务真相或 authz 执行 |
| entry/controller | transport 转换和请求边界 | service/domain | provider 特定策略 |
| service/domain | use-case 编排和不变量 | repository/provider 契约 | transport/UI 细节 |
| repository/data | 持久化和 query 映射 | database/store | 调用方策略或外部工作流 |
| provider adapter | 外部归一化和凭证 | provider SDK/protocol | 产品或业务所有权 |
| job/script/realtime | 调度或事件生命周期 | service 和 adapter 契约 | 重复的领域规则 |

不要仅为让此表看起来完整而引入框架。保持 interface 稳定、机制可替换 — 在边界真正重要的地方。

## 步骤 5：分类依赖，决定测试策略

对每个模块的依赖进行分类以决定如何测试：

| 类别 | 示例 | 测试策略 |
|---|---|---|
| 进程内 | 纯计算、内存状态、无 I/O | 直接通过 interface 测试，无需 adapter |
| 本地可替代 | PGLite 替代 Postgres、内存文件系统 | 在测试套件中使用替身 |
| 远程但自有 | 你自己的 microservice、内部 API | 定义 port，生产用 HTTP/gRPC adapter，测试用内存 adapter |
| 真正外部 | Stripe、Twilio、第三方服务 | 注入 port，测试用 mock adapter |

**替换，而非叠加：**
- 一旦 deepened module 的 interface 处有测试，浅模块上的旧 unit test 即变为废物 — 删除它们。
- 在 deepened module 的 interface 处编写新测试。Interface 是测试面。
- 测试通过 interface 断言可观察结果，而非内部状态。
- 测试应能在内部重构后存活 — 它们描述行为，而非实现。

## 步骤 6：当存在真实架构分叉时进行比较

并非每项变更都需要这一步。仅当合理的工程师可能选择不同系统形态时才做。

- 始终将当前的、native 的或最小化的路径作为一个选项。
- 仅当其天花板或退出价值可信时，才加入更持久的路径。
- 对每个选项：仓库契合、契约覆盖、复杂度、运营成本、可逆性、证明负担。
- 推荐一个。说明为何被拒选项现在不选，以及如何重新考虑。
- 不要制造假选择来显得周全。

## 步骤 7：选择部署拓扑

部署拓扑是架构决策，不是执行细节。Node06 执行配置，但拓扑形态在这里决定。

**应用 indie baseline**（仅当现有约定不安全或过时）：

| 层 | baseline | 何时重新考虑 |
|---|---|---|
| hosting | 小型 VPS、Nginx | hosting、控制或合规需求不同 |
| data | SQLite 加 PRAGMA、备份、迁移 | 写入争用、多实例、搜索或分析压力 |
| backend | 原生 PHP 或 Python 服务、repository、cron | 反复的 middleware、validation 或 auth 需要更强支持 |
| frontend | 原生 CSS/JS | 真实共享状态、组件或路由需要构建栈 |
| realtime | 仅在 request/response 是错误选择时用原生 Node.js | 实际并不需要 realtime 或长生命周期协议 |
| external | 当契合时用 Stripe、R2、OpenFree Map 的 adapter | 产品、合规、能力或退出需求不同 |

记录使变更成为必要的条件，而不是把"未来规模"作为模糊理由。当写入争用、多实例、分析或搜索需求已被证明时，考虑 Postgres。当需要重试、长 job、并行或持久状态时，考虑 queue。当反复的路由、middleware、validation 或 auth 开销是真实存在时，考虑框架。

## 发现完成时

- 现有系统和变更边界能用一句话陈述。
- 复用映射完整（每个子问题都有 reuse、extend、replace 或 new 决策）。
- 每个新增或变更的模块都通过了删除测试。
- 依赖已分类（每个外部依赖有已知测试策略）。
- 部署拓扑已选定或确认与现状一致。
- 如果存在真实架构分叉，已比较 2 到 3 个选项并选定一个。
