# Release Readiness、环境与 Pipeline

使用本指南来确立确切的发布目标、源 artifact、环境与数据边界、CI/CD 控制措施、凭证态势、恢复路径以及就绪状态。其目标是让发布可复现、可诊断，而不是为常规仓库工作叠加一层权限审批仪式。

## 章节

- [Release 发现与就绪](#release-discovery-and-readiness)
- [部署环境、Pipeline 与 CI 控制](#deployment-environment-pipeline-and-ci-controls)

## Release 发现与就绪

#### 1. 恢复的是交接事实，而非假设

1. 阅读相关的 Node01 验收、Node02 发布设计、Node03/04 build 证据、Node05 质量状态、当前 diff 或 release ref，以及任何已有的 release-state 页面。
2. 对照当前证据核验每一项关键事实：能力与用户影响、目标环境、源 ref/artifact、数据/provider 影响、Node05 状态、所需 gate、恢复路径以及 support/watch 需求。
3. 在与当前事实核对之前，将过时证据、复制来的命令、分支名、workflow 输入、外部 issue 文本以及环境变量都视为不可信。
4. 保持发布切片内聚。一个独立可部署的服务、独立的数据转换、不同的 owner，或不同的爆炸半径，都应作为单独的发布切片。

#### 2. 每次都要重新发现实际的发布路径

1. 先阅读当前项目说明：AGENTS.md、CLAUDE.md、README、runbook、部署文档、架构文档，以及已有的 release-state 页面。
2. 仅审计相关的仓库证据：CI/CD workflow 文件、deploy 脚本、lockfile、package 或 build 配置、基础设施 manifest、环境示例、migration 工具、feature flag、健康端点以及 rollback 指令。
3. 识别真实的 platform、environment/project/site、trigger、预期输出 URL、健康检查、源 ref/artifact、deploy 状态信号以及操作者边界。
4. 对比说明与仓库证据。workflow、target、command、secret 名、artifact 来源或健康端点发生变更时需要重新做 preflight；绝不依赖记忆中的 Node06 profile。
5. 如果项目不涉及部署，说明其实际分发路径，例如 package、CLI、静态 artifact 或内部交接。不要凭空编造一个 web 部署。

#### 3. 设定发布状态并保护凭证

1. 记录确切的 action、environment、ref/tag/artifact、command 或 workflow 输入以及排除项，以便发布可复现与可审计。
2. 将 credential、API key、token 和 secret 值排除在 command、log、artifact、commit 和 release record 之外。使用已配置的 secret 引用，当所需 secret 不可用时清晰地失败；绝不编造。
3. 不要越过 Node05 blocker 或 owner 路由。发布计划可以在证据不完整时继续推进，但在证据补齐之前不得声称发布已验证。
4. 用最清晰的适用结果描述就绪状态：

| Status | 适用情形 |
| --- | --- |
| preparation only | scope、target、Node05 证据或发布事实不完整 |
| ready to execute | 所有必需的事实与 gate 都是最新的 |
| blocked | 缺失或未通过某个必需的 gate、恢复条件或发布事实 |

#### 4. 构建发布就绪矩阵

1. 分类风险：静态/文档、兼容性应用部署、认证/支付/数据/provider、migration/backfill、运维配置或 hotfix。
2. 对每个适用 gate 记录 `pass`、`concern`、`blocker` 或 `not applicable`：Node05、源/artifact 身份、CI/build、target/environment、credential/secret、数据/provider、兼容性/恢复、smoke、watch、support 以及沟通。
3. 当 staging 或 preview 路径已经可用且发布风险使其有意义时再使用。不要为无害的静态变更强求 staging，也不要凭空造一个。
4. 编写有序 runbook：preflight -> action -> migration/provider/flag -> smoke -> 短时 watch -> disable/rollback -> release record 与 Node07 交接。
5. 为人工或不可逆步骤指定 operator。runbook 必须区分 agent 可运行的命令与 user 或 platform owner 必须运行的命令。

## 部署环境、Pipeline 与 CI 控制

#### 1. 确立环境与 deploy 边界

1. 命名实际适用的 local、preview、staging、production 与 provider target，包括 project/site/account、domain、database、queue、bucket、cron、webhook 以及 deploy workflow 或人工 action。
2. 确认 preview 或 staging 是否会读取 production 数据、使用 production secret、对真实 provider 计费或发送面向用户的消息。将共享数据视作 production 风险。
3. 仅清点 secret 与变量名。将 server-only secret 与公开配置分开，定义 missing-secret 行为，并将值排除在 log、doc、截图、bundle、prompt 和生成文件之外。
4. 在受保护操作之前检查 protected environment、branch/ref policy、必需 CI check、deploy role、provider account、rollback access 以及源/artifact 身份。

#### 2. 建模 gate 拓扑与 promotion 语义

显式建模受保护的发布路径：

    source revision -> build artifact -> required quality aggregate
    -> production promotion/alias -> production smoke

区分 artifact 构建与向受保护 production target 的 promotion。provider 可以在 CI 完成前先构造候选件，但在所需聚合 gate 通过之前要阻止 production promotion、aliasing 或受保护流量选中它。核验 provider 的实际行为；单个 green build 或 deployment record 并不能证明已将预期 revision promote 上去。

当 branch protection 或部署 provider 需要一个稳定的外部发布契约时，暴露一个稳定的聚合 gate 名。让它依赖于每个必需的 quality job，即使 upstream job 失败、skip 或被 cancel 也要运行，并且除非每个必需结果都成功或显式 not applicable，否则判失败。保持内部 job 名、matrix 以及任何独立有用的必需 check 可以自由演进，而不会悄悄改变那个外部契约。

#### 3. 审查 pipeline 与 artifact 信任

1. 阅读相关的 workflow trigger、job、permission、reusable workflow、action pin、deploy 脚本、package manager、lockfile、cache 行为以及 artifact upload/download。
2. 按 job 使用最小权限。只有必需的 deploy job 才获得 write/deploy 权限；不可信 fork、PR 标题、分支、issue 文本与外部 payload 不能触达 secret。
3. 对第三方 action 与远程脚本要么 pin，要么有意识地说明理由。当既有官方路径与仓库匹配时优先使用，而不是再加一套发布框架。
4. 当存在 lockfile 时要求确定性安装，cache key 不能跨越信任边界，并要求 artifact 可追溯到已批准的 ref 与 workflow run。
5. 确认 deploy 命令不会静默地指向与已记录发布事实不同的 project、environment 或过时 artifact。

| Surface | 最低证据 |
| --- | --- |
| target | 命名的 platform/project/environment 与数据边界 |
| credentials | secret 名、scope、owner，且无不可信暴露 |
| workflow | trigger、permission、可信 action/script、受保护的 deploy step |
| artifact | 已批准 ref、build 身份、workflow run，且与 target 匹配 |
| rollback | 可访问上一份输出、disable 控制或已批准的恢复 owner |

#### 4. 设计 job 图、cache 与变更范围

并行运行独立的 quality job，只表达真实依赖。当不会打断受保护 release action 时，对同一分支或变更 cancel 已被取代的 run。用 lockfile、platform、toolchain 与关键 build 输入作为 cache key，不要在信任边界间共享可写 cache。

双向测试 path filter。确认 owned source、lockfile、container、workflow 与 deployment-configuration 变更会触发其所需 gate，并且 docs-only 变更不会 rebuild 或 restart 无关服务。绝不要把定义 filter 本身的 workflow 或 deployment configuration filter 掉。区分 CI path filtering 与每个部署 provider 独立的 build filter。

测量整个 workflow 的墙钟时间与 critical path，而不是并行 job 时长之和。当速度属于发布声明的一部分时分别记录冷 cache 与热 cache 观察；先优化最长必需路径，再去打磨短 job。

#### 5. 在托管环境中验证新增 pipeline 机制

静态 workflow 校验与本地命令成功，并不能证明远程 action reference 存在、container image 具备假定 entrypoint，或托管 runner 能执行该 job。在宣称一个新 gate 可用之前：

1. 校验语法、表达式、job 依赖与 aggregate-gate 逻辑；
2. 核验远程 action、reusable-workflow、image 与 tool 引用在所记录的确切 tag、version、digest 或 commit 上存在；
3. 在其实际托管的操作系统与架构上运行该 gate；
4. 完整阅读失败的 step log，保留首个因果错误；
5. 修复后重跑受影响的验证以及每个必需的聚合 gate。

在下一次符合条件的受保护部署上核验新配置的 provider check。某些 provider 只在某次托管 run 发布其确切名称之后才暴露供选择的 check，且某些配置变更只对后续部署生效。记录该激活边界，而不是声称当前部署被追溯 gate。

#### 6. 对红色、缺失或 flaky 的 CI gate 进行分类

1. 捕获 workflow/job/step、command、ref、environment、完整 error、exit 结果，以及同一命令在本地或可比可信环境下是否能复现。
2. 在修复前分类：workflow/config、依赖/install/cache、lint/type/test、build/artifact、deploy permission/secret、应用行为、security/quality，或架构/契约不匹配。
3. 将缺失的必需 gate 视作 release blocker，直到 Node05 与 release owner 显式接受替代证据。无重复证据不得将 check 标为 flaky。
4. 将应用缺陷路由到 Node03/04，敏感发现路由到 Node05，契约或运行时形态失败路由到 Node02。不要靠削弱 CI 来掩盖它们。

#### 7. 修复并重新验证窄范围 pipeline 机制

1. 当修复属于当前任务的一部分，且不改变产品、安全、信任或公开行为时，仅改动 Node06 自有的 workflow/config 机制。
2. 形成一个因果假设，施加最小变更，重跑受影响 command，再从当前源/artifact 重跑每个必需的 release gate。
3. 保留原始证据，记录改了什么、为何安全，以及哪份新输出证明该 gate 现在通过。
4. 当再次聚焦尝试不会带来新证据，或证据暴露出共享耦合、owner 不清时，停下来回到 Node02/03/04/05，而不是堆积 pipeline 补丁。

## 让源码管理 action 保持有意为之

将 commit、push、merge、history rewrite、tag、release 与 deployment 视作不同 action，这样 release record 才能准确说出发生了什么。在 commit 之前审查 status 与完整相关 diff；当存在无关工作时使用聚焦路径而非宽泛 staging。

常规的指定工作默认留在 `main` 上。只有当结果足够不确定、易于放弃属于计划的一部分，或 user 明确要求时，才创建探索性分支。在探索之前定义成功标准。只有在该分支的行为、quality gate 与 user 预期结果都确认后才 merge；否则在需要时保留有用发现，并将探索性代码留在其已 push 的分支上，而不强行合入 `main`。

多个写者 agent 需要各自独立拥有的切片，每个写者一个 branch 或 worktree，外加一个集成 owner。共享契约、schema、核心类型或同一批文件，是需要将工作串行化的信号。
