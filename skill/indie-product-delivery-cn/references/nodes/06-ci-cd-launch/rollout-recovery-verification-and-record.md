# Rollout、恢复、验证与记录

使用本指南来执行 rollout 或 migration、验证实际目标、控制失败范围、关闭即时观察窗口，并为运维记录持久的 release 状态。之所以采用这样谨慎的顺序，是为了限制 blast radius，并在实际结果与计划不符时保留可恢复的解释依据。

## 章节

- [Rollout、Migration、Provider 与恢复执行](#rollout-migration-provider-and-recovery-execution)
- [部署后 Smoke、Watch 与事件路由](#post-deploy-smoke-watch-and-incident-routing)
- [Release 状态、记录与 Node07 交接](#release-state-notes-and-node07-handoff)

## Rollout、Migration、Provider 与恢复执行

#### 1. 恢复当前执行切片

1. 对 slice 进行分类：简单 deploy、additive schema、expand/contract、破坏性
   migration、backfill、provider/webhook、job/cron、payment/entitlement、DNS/CDN、cache、
   feature flag、import/export，或 incident recovery。
2. 在执行之前，阅读 Node02 的 evolution/compatibility 与 recovery 决策、Node03 的实现
   证据，以及 Node05 的 proof 状态。
3. 对每个 slice 说明其旧/新状态、受影响的消费者、兼容窗口、
   前置条件、预期 observable、停止条件，以及 recovery 负责人。
4. 不要仅因为多个变更可以通过一条命令发布，就将独立可逆或独立高风险的变更合并在一起。当 blast radius 或 recovery 方式不同时，应拆分 runbook。

#### 2. 定义可执行 sequence

1. 按顺序列出各 action，标明 source ref/artifact、确切 target、安全输入、预期
   output、checkpoint，以及哪些步骤可自动执行、哪些需手动执行。
2. 在每个不可逆或对外计费的效果之前定义 checkpoint。在每个
   checkpoint 处，先检查预期 observable 再继续。
3. 当设计有要求时，准备好所需的 backup/snapshot、dry-run、idempotency key、
   batch/progress 记录、rate/cost 限制，或 provider sandbox 证据。
4. 记录哪些 action 可重试、哪些仅能安全执行一次、如何识别重复 callback，
   以及 reconciliation 或手动修复从何处开始。

| Slice | 典型已批准 sequence |
| --- | --- |
| compatible deploy | verify artifact -> deploy -> smoke -> short watch |
| additive schema | backup/preflight -> expand -> compatible deploy -> smoke |
| expand/contract | expand -> dual read/write -> backfill -> cutover -> later cleanup |
| provider/webhook | compatible receiver -> safe test event -> switch -> reconcile -> smoke |
| job/cron | deploy -> controlled manual run -> enable schedule -> watch first run |
| payment/entitlement | verified test evidence -> deploy -> webhook/entitlement smoke -> active watch |
| DNS/CDN/flag | confirm previous state -> small switch -> propagation/behavior check -> disable path |

#### 3. 以证据执行，而非乐观推进

1. 在执行之前立即再次确认确切的 target、source 和 action。
2. 一次只运行一个 sequence 步骤；捕获实际 output，并在运行下一步之前
   与预期 checkpoint 进行比较。
3. 除非当前 slice 明确需要且 recovery 仍然可行，否则不要在首次
   release 中进行破坏性 cleanup、contract 移除或旧数据删除。
4. 当某一步骤偏离预期时，停止 sequence，保留证据，并使用计划好的
   disable、rollback、forward-fix 或手动 recovery 路径。不要临时处置数据修复。

#### 4. 从实际状态决定 recovery

1. 优先选择危害最小的可用控制方式：feature flag/config disable、job pause、
   provider switch、traffic reduction、artifact rollback、restore，然后是 forward-fix。
2. 仅当 application output 仍与当前数据和
   provider 状态兼容时，才对其进行 rollback。在不可逆的 schema/data 变更之后，forward-fix 可能更安全。
3. 如果某个 provider、migration 或 reconciliation 步骤需要人工介入，则在恢复之前记录
   确切观察到的状态、安全的下一步 action、owner，以及所需证据。
4. 在即时控制决策完成之后，将失败的 recovery 或不确定的用户/数据影响
   视为 Node05-quality 与 Node07-incident 的事项。

## 部署后 Smoke、Watch 与事件路由

#### 1. 确立实际 post-deploy target

1. 确认环境、URL 或 endpoint、已 deploy 的 ref/artifact/version、release
   时间戳、安全的测试账户/数据、provider 模式，以及预期的用户可见变更。
2. 验证 deploy 状态或 artifact 身份与预期 source 一致。仅凭
   workflow 变绿并不能证明预期 artifact 已经到达目标环境。
3. 根据变更和风险从以下表格中选择最小且充分的 smoke matrix：

| Change/risk | 最小即时证据 |
| --- | --- |
| static/docs/config | target 可用性及受影响的 route 或配置检查 |
| normal feature | 可用性、primary action、相关 API/data 结果、logs 或 error signal |
| frontend surface | 受影响的 route、primary action/state、相关情况下的小 viewport、console/network |
| auth/tenant/private data | 在安全前提下验证账户边界及拒绝/所有权行为 |
| migration/backfill | 预期 schema/state checkpoint、兼容的 read/write、recovery signal |
| provider/job/webhook | 安全的 trigger/status/callback 或 reconciliation 证据、error signal、first-run watch |
| payment/entitlement | 非计费证据，或带有已验证金额、收款方、provider 和 webhook/result 证据的真实路径 |

#### 2. 有意识地运行 smoke

1. 等待项目定义的信号表明 target 已就绪，然后先检查
   渲染或返回的状态，再基于其采取行动。
2. 默认使用非破坏性读取和安全的测试数据。对于涉及资金的 action，
   验证金额、收款方、provider 和最终计费状态。将 secret/API key
   排除在 logs 和记录之外。
3. 对于 UI 路径，检查渲染后的 DOM/state，执行预期交互，然后在
   相关时收集 console/network 证据并进行小范围的 desktop/mobile 检查。
4. 对于 backend、data、job 或 provider 路径，记录 endpoint/status、持久 state、
   correlation ID 或脱敏后的 log signal，以及可见结果。将私有标识符排除
   在持久的 release 记录之外。
5. 将实际结果与 release 预期进行对比。将每个 proof 标记为 `pass`、`concern`、
   `fail` 或 `not run`，并附上原因和安全的下一步 action。

#### 3. 先遏制再扩展调查

1. 发生关键失败时，首先保留有用且最小的证据：target/ref、
   时间戳、error output、观察到的状态，以及受影响的用户路径。
2. 应用危害最小的可用控制方式：flag/config disable、job pause、provider
   switch、traffic reduction、rollback，或 forward-fix。不要持续对有害路径进行探测。
3. 对于非关键失败，reproduce 一次，对比最近的可工作路径或上一个
   release，追踪 data/request 边界，形成一个假设，并执行最小的
   聚焦式验证或修复。
4. 每次修复后，重跑受影响的 smoke 以及邻近的 regression proof。当再次
   尝试无法提供新证据，或证据揭示出共享耦合、contract
   冲突或无效的 runtime 前提时，回到 Node02/03/04/05，而不是再叠加
   一次 release patch。
5. 在即时控制、release-state 捕获和 owner 路由完成之后，
   生产事故即转为 Node07 的工作。

#### 4. 关闭即时 watch 窗口

1. 根据 blast radius 选择观察时长：static 变更采取即时观察，normal
   feature 采取短期 log/support 窗口，auth、payment、data、provider
   或 job 变更采取首个真实事件或首次 scheduled run。
2. 只观察能够证伪 release 声明的信号：可用性、错误率、
   queue/job 状态、provider 失败、support 反馈、cost/rate 信号，或关键路径。
3. 如果窗口干净关闭，则将持续的健康状况和学习问题移交给
   Node07。如果未能干净关闭，则维持控制，并将
   incident 路由给其实现、质量或架构 owner。

## Release 状态、记录与 Node07 交接

#### 1. 仅在事实变化时更新持久 truth

1. 仅当 release、环境行为、recovery 姿态、运维依赖或 named concern 具有持久性且
   对未来工作有用时，才更新 HTML 项目 command board 的 Release/Validation 或 Control Room 区域。
2. 保留稳定的 board 事实及其既定的页面归属。遵循
   `../08-agent-context-html/README.md`；不要仅因为发生了一次 release 就重写稳定的架构或产品页面。
3. 使用当前的 command output、workflow 结果、deploy/provider 状态和 smoke 证据
   作为源材料。未执行的计划 action 仍然是计划，而不是 release 状态。

#### 2. 编写 release record

1. 描述事实性的 release 结果。以下词汇在需要时可以使用，
   但并非必需的全局 status schema：

| Status | 含义 |
| --- | --- |
| preparation only | 未发生任何外部 release action。 |
| `READY_TO_EXECUTE` | 所有已知 gate 通过，action 已就绪可运行。 |
| `EXECUTED_AND_VERIFIED` | action 已运行且所需的即时 proof 通过。 |
| `EXECUTED_WITH_NAMED_CONCERNS` | 有界 concern 已具备 owner、trigger、mitigation 和 watch。 |
| `ROLLBACK_OR_DISABLE_ACTIVE` | 控制已改变 live state，后续跟进仍未完成。 |
| `BLOCKED` | release 无法安全继续或恢复。 |

2. 记录：release slice、环境、source ref/artifact、target 身份、Node05 和
   CI 证据、已执行 sequence、migration/provider/config 变更、smoke 结果、
   disable/rollback 或 forward-fix 路径、watch 窗口、operator，以及下一个 owner。
3. 对 secret 值、客户数据、私有标识符、脆弱的实现
   细节、payment 数据、原始 provider payload，以及私有 incident 证据进行脱敏。在
   复制不如链接安全时，链接到授权的内部证据。
4. 保持 `known concerns` 具体可执行：影响边界、owner、trigger、mitigation、revisit
   condition，以及后续跟进归属 Node07 还是前序 node。

#### 3. 编写面向读者的 note

1. 面向用户的 note 描述人们现在可以做什么、变更后的行为、停机、
   限制、所需 action，或坦诚的已知问题。不要把内部 refactoring
   和基础设施机制变成产品声明。
2. 维护者 note 描述受影响的 modules/contracts/config、source/target、证据、
   support 处理、运维依赖、recovery 控制，以及未解决的风险。
3. 仅在有用时才对材料进行分组：`Added`、`Changed`、`Fixed`、`Security`、
   `Operational` 和 `Known concerns`。保留之前的 release 历史；不要
   从 release 摘要中重新生成或覆盖它。

#### 4. 交接给 Node07

1. 将 release 状态、即时 watch 结果、预期早期信号、support 或
   incident context、active concern，以及明确的 revisit trigger 传递给 Node07。
2. 将持续的可用性、首次真实使用、scheduled-job 结果、反馈、
   retention、conversion、cost 和 experiment 学习路由给 Node07。
3. 对新的 deploy、rollback 或 migration 执行，保留 Node06 的 ownership。Node07 可以
   检测到需求，但不负责发明或执行 release action。
