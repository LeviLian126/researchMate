---
name: indie-product-delivery
description: "用于以结果为先、证据支撑的自建软件产品交付与评审。适用于产品决策、架构、后端或前端实现、质量、发布、维护或代码/文档评审。当任务使项目的产品、架构、实现、证据或发布事实过时,更新 docs/ 下的项目 HTML 项目看板。"
---

# Indie Product Delivery

## Context

在检查事实之前，先读取 `../human.md` 并遵循其输出风格和交付纪律规则。这些规则适用于本会话中的所有响应。

检查能改变结果的最小一组当前事实:

- 仓库、产品界面、环境和相关现有行为;
- 已确认的需求、非目标、验收标准和未决决策;
- 当前源代码、配置、测试、维护的文档和适用的仓库指令;
- 可用的工具、凭证、runtime、账号、数据和证据。

不要要求用户重述可以安全发现的事实。优先使用当前用户指令、仓库指令、源代码和配置、测试和维护的本地文档。对于版本敏感的 provider 或框架行为,使用已安装版本及其官方文档。发现冲突时应指出,而不是静默选择方便的来源。

识别拥有当前请求的 node,读取该 node 的 README,然后只读取该 README 路由到的工作流文件。这使工作上下文足够小,让 agent 能推理实际请求而不是对整个交付系统做仪式性调查。除非该 node 的输出明确将工作路由到其他地方,否则留在该 node 内。

## Boundaries

保留用户声明的约束,区分本地工作与外部影响。

- 使用 agent 默认可用的仓库访问和外部操作权限来操作。当用户明确请求 plan、grilling/review 或 approval-first 工作时,在继续之前先询问。否则自主完成目标,包括 commit、push 和真实 server 或 production 验证(当环境支持时),并在最后报告所选择的默认值。
- 不要暴露或猜测 secret、API key、token 或未披露的凭证。如果多次基于证据的尝试无法达到请求的结果,不要通过 jailbreak、cheat 或伪造证据来绕过约束:说明阻塞并提供最接近的安全替代方案。

对涉及的产品边界使用相关的工作流。当生产行为可能损害用户、数据、金钱、隐私、安全或可用性时,在追求增长或优化之前先控制损害并收集直接证据。

在本地和适用的 server 环境中测试可运行的工作。本地测试时,安装必要依赖即可,但对数据库、消息队列等中间件使用测试类的 mock 而非启动本地服务;前端改进需在浏览器中渲染,验证视觉和交互的正确性。

对于小型变更,只验证变更的行为及其受影响的 server 路径;对于大型 refactor、
`HIGH_RISK` 变更或 release,验证相关核心流程和发布证据。按环境标记证据,不要将本地
成功视为 server 成功。如果在合理的设置尝试后目标环境确实不可用,记录确切的证据缺口
并使用所有安全的替代方案继续。

对于大型 refactor、`HIGH_RISK` 变更和 pre-release 验证,默认使用独立的 subagent
或新会话。两阶段使用同一个 subagent 以保留上下文并节约 token。第一阶段:提供
目标、接口签名、schema、验收标准和风险分类,并禁止其阅读实现源码,使其只能
从公开契约设计契约优先的测试。第二阶段:解除源码限制,提供实现 diff、第一阶段
测试和 runtime 证据,使其能审查源码并确认覆盖缺口。对于小型本地变更,默认不开启
独立会话;完成适用的本地检查和受影响的 server 检查即可。

当工作有助于完成请求时,你可以在列出的步骤之外进行调查、实现、测试或改进质量。不要静默扩大产品含义或协作系统范围。

## Output

产出一个用户可用的结果,由最窄的有意义证据支撑。

- 没有所需的 runtime、账号、数据集、browser 或环境时,只做可用证据支持的声明。
- 除非命令或外部观察实际证明了它,否则不要将操作描述为已执行。
- 当当前研究不可用时,将时间敏感的市场或 provider 结论标记为假设。

当一条路径失败时,尝试另一条路径或收集新证据。不要在没有学到新东西的情况下重复相同的尝试。目标是通过改变的假设、路径或证据来取得进展——不是在死循环中坚持。

自然地返回结果。明确交付或决定了什么、什么证据支撑它、执行了什么外部影响、以及什么关注或阻塞仍然存在。除非帮助用户理解决策,否则不要暴露内部路由注释。

## Choose the current node

选择拥有当前决策或操作的 node。Node 编号标识领域,不是强制的生命周期。遵守该 node 的 README 和输出契约;除非当前 node 路由到其他地方,否则不要导入另一个 node 的 checklist。

| 当前需求 | 读取 |
|---|---|
| 目标用户、问题、承诺、定价、定位、MVP/MAP、验证、验收 | `references/nodes/01-market-mvp-scope/README.md` |
| 系统边界、API/data/permission/provider 契约、架构、兼容性、migration 或 build 计划 | `references/nodes/02-architecture-contracts-plan/README.md` |
| backend、API、data、auth、job、provider、async、reconciliation 或 observability 实现 | `references/nodes/03-backend-api-data-build/README.md` |
| frontend 流程、内容、视觉方向、组件、响应式/无障碍行为或 browser 验证 | `references/nodes/04-frontend-ux-ui-build/README.md` |
| 评审、测试策略、runtime QA、可靠性、security/privacy、证据或发布判断 | `references/nodes/05-qa-review-security-hardening/README.md` |
| CI/CD、发布准备、deploy、rollout、migration 执行、recovery 或生产验证 | `references/nodes/06-ci-cd-launch/README.md` |
| 生产健康、客户证据、实验、学习或下一个运营决策 | `references/nodes/07-ops-growth-iteration/README.md` |
| 空间比较、模块或架构图、交互式原型、项目状态看板或维护的 HTML 证据界面 | `references/nodes/08-agent-context-html/README.md` |


在每次 commit 或 push 之前,将最新源代码和配置与 `docs/` 下的
HTML 项目看板进行比较。仅当此任务使其重要的产品、架构、实现、证据、发布、
风险或下一步行动事实过时时,进入 Node08 并更新看板;否则不要修改它。
当看板更新时,在其技术事实和结构稳定后运行 `human` skill。
保留有意义的产品和数据事实;省略琐碎的实现细节,如按钮尺寸,除非它是
真实设计契约的一部分。

## Apply the minimum delivery standard

所选工作流中的适用要求是最低交付标准,因为它们保护 node 的预期结果;它们不是仪式性 checklist 或必需的最终响应格式。

- 完成适用于当前任务和事实的每个要求。
- 跳过真正不适用的检查;不要仅为完成仪式而执行它们。
- 不要利用任务的小规模来跳过适用的 security、permission、state、error、accessibility、compatibility、recovery 或 verification 要求。
- 用有意义的单元测试覆盖核心业务代码。目标是对可能 corrupt state、grant access、charge money 或改变用户结果的决策有信心——不是覆盖率数字。优先覆盖业务规则、authorization 决策、state transition、failure 处理、idempotency、money/quota 逻辑和变更分支。不要仅为提高百分比而为 trivial glue、generated code、styling 或简单 pass-through 添加测试;当单元测试会歪曲 boundary 时,使用 contract、integration、browser 或 runtime 证明。遵循仓库中存在的更高阈值。
- 当额外工作实质性地改善请求结果且仍在产品目标范围内时,超越工作流。
- 不要向用户背诵工作流 checklist;满足它并报告结果和证据。

对于跨多个产品模块且承载发布的复杂变更,除非具体依赖要求否则按此顺序:设计、源代码实现、维护的 HTML/OpenAPI(如适用)、本地 hermetic 检查、cloud CI 和模块验证、commit 和 push 到仓库的预期分支、migration、deployment、生产 smoke 和 rollback 判断。此顺序使广泛变更从意图到活证据可追溯,并在现实偏离时留下清晰的恢复决策。对于小型本地变更,只使用能影响正确性的步骤。无论大小,检查最终 diff、commit 变更并在完成前 push;push 是完成的一部分,不是可选的 release 步骤。将普通工作 push 到 `main`;将探索性工作 push 到其探索性分支,并仅根据下面的分支规则将其合并到 `main`。如果 push 需要缺失的凭证或 API key,报告该具体阻塞而不是伪造访问。从仓库配置、runtime 要求和现有所有权选择部署平台。`docs/` 下的项目看板 HTML 记录所选平台及其背后的证据。

## Keep modules cohesive and review size as a signal

保持模块内聚,使每个文件有清晰的变更理由,业务规则不会变成冗长、纠缠的流程。仅将 size 用作检查内聚的提示,不是机械的拆分阈值。

| 产物 | 审查信号 | 必需响应 |
|---|---|---|
| 实质性 Markdown reference | 变得难以扫描或回答多个不相关的读者问题 | 保持一个连贯的读者问题;仅在有真实概念边界时拆分 |
| 编写的产源代码 | 变得难以推理或因不相关原因而变更 | 在拆分前检查 ownership、state flow 和依赖方向 |
| 编写的非 generated 产源代码 | 积累分支、重复 policy 或跨层知识 | 仅在减少耦合时提取内聚 boundary,而不是创建碎片 |

不要仅为满足数量而创建小文件,也不要为避免一个而合并不相关行为。优先高内聚模块、窄契约、明确 ownership、组合和 provider adapter。将 generic `utils`、`common` 或 `helpers` 增长、重复的跨层条件语句和大型 if/else dispatch 树视为 policy 或 ownership 可能错位的证据。期望的结果是更少的可理解 boundary,不是最大的文件粒度。

## Write code for understanding and change

代码质量目标是让下一个变更明显且局部。将这些原则作为判断指南应用,不是引入仪式或抽象的理由:

- 保持每个模块、类和函数负责一个连贯的结果。将业务规则与 infrastructure 和 presentation 分离,使规则有一个清晰的 owner。
- 优先使用可读的名称、小型聚焦函数、简单的控制流和明确的依赖,而非 cleverness、深层嵌套、global state、隐藏的 side effect 或过早的模式。注释解释 why、约束或 invariant——不是代码已说明的 what。
- 当改善一致性时移除重复的 policy,但在真实 seam 或重复行为出现之前不要创建抽象。保持 interface 稳定,在 boundary 重要处保持机制可替换。
- 显式处理错误:保留有用的上下文,对无效 state 快速失败,永远不要静默丢弃 exception 或意外的 provider 结果。
- 使核心业务逻辑通过清晰的输入和输出易于测试。测试变更的业务规则、failure 路径、state transition 和 compatibility 行为;当单元隔离会歪曲真实系统时使用合适的 boundary 测试。

在 handoff 之前,问:每个组件是否有一个清晰的职责,依赖方向是否可理解,核心行为是否可以在没有脆弱耦合的情况下测试,下一个 feature 是否需要本地扩展而非重写不相关的代码?

## Edit in place and reuse existing code

优先复用已有函数、抽象和模式,而非引入新的。在编写新代码之前,先在仓库中搜索是否已有函数或模块已解决该问题,或可以通过小型、内聚的变更扩展。复用使代码库可理解,避免同一 policy 的并行实现导致的漂移。

在修改已有文件时——无论是文档还是源代码——不要仅为便利而将新内容追加到文末。将文件视为一篇有逻辑的文章:将新内容穿插到它所属的 section,并重新编号或重构后续 section 使整个文件保持连贯。例如,当添加一个逻辑上属于第二节和第三节之间的新内容时,将其作为新的第三节插入,并将后续所有 section 顺延一节。目标是保留文件的叙事流和可维护性,而非最小化 diff 的大小。

## Choose branches and worktrees deliberately

默认将普通指定工作用于 `main`。在变更文件之前确认请求的结果和重要要求;不要为普通工作或因为 branching 可用而创建分支。

仅当任务真正是探索性的或用户明确要求时,才创建探索性分支。在实现之前定义成功条件,push 分支供评审,仅在证据表明改进满足用户预期结果后才合并到 `main`。当不满足条件时,将探索性代码和发现保留在该 pushed 分支上;不要强制其进入 `main`。

在同一个 thread 内,修改文件之前先开一个 worktree。所有后续 subagent 和主 agent 都在该 worktree 内工作——subagent 不得另开 worktree。在 worktree 内完成所有实现和验收后,合并回 `main`,确认无冲突再 commit 和 push,然后删除该 worktree。

## Maintain useful source commentary

对每个编写或修改的源代码/配置文件遵循仓库既定的文档风格。开头注释和聚焦的业务测试的目的是让下一个 agent 可以发现 ownership 和重要行为,不是装饰文件或测试实现琐事:

- 当格式支持注释时,每个新编写或修改的源代码/配置文件以简洁的英文注释开头,说明其主要职责或 boundary。不要向 Markdown、strict JSON、lockfile、generated 文件或 vendor 产物添加注释。
- 对于核心业务逻辑,用有意义的测试覆盖主要函数。在 docstring 或文档注释解释公共契约、invariant、非显而易见的约束或 ownership boundary 的地方添加;不要注释每个 trivial 函数或组件。
- 保持注释和文档对公共契约、invariant 和非显而易见的约束的准确性,并在行为变更时更新过时的注释。
