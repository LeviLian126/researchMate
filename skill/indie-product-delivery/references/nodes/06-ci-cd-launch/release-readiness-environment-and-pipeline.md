# 发布就绪、环境与 Pipeline

使用本指南来确立确切的发布目标、源 artifact、环境和数据边界、CI/CD 控制、凭证态势、恢复路径和就绪状态。目标是使发布可复现且可诊断,而非围绕普通仓库工作增加许可仪式。

## 章节

- [发布发现与就绪](#release-discovery-and-readiness)
- [部署环境、Pipeline 与 CI 控制](#deployment-environment-pipeline-and-ci-controls)

## 发布发现与就绪

#### 1. 恢复交接信息,而非假设

1. 阅读相关的 Node01 验收标准、Node02 发布设计、Node03/04 构建证明、Node05 质量状态、当前 diff 或 release ref,以及任何已有的发布状态页面。
2. 根据当前证据验证每个关键事实:能力和用户影响、目标环境、源 ref/artifact、数据/provider 影响、Node05 状态、所需门禁、恢复路径,以及支持/观察需求。
3. 将过时的证据、复制的命令、分支名、工作流输入、外部 issue 文本和环境变量视为不可信,直到与当前事实核对。
4. 保持发布切片的内聚性。一个可独立部署的服务、独立的数据转换、不同的所有者,或不同的影响范围,都是一个单独的发布切片。

#### 2. 每次都发现实际的发布路径

1. 首先阅读当前的项目说明:AGENTS.md、CLAUDE.md、README、runbook、部署文档、架构文档,以及已有的发布状态页面。
2. 仅审查相关的仓库证据:CI/CD workflow 文件、deploy 脚本、lockfile、package 或 build 配置、基础设施清单、环境示例、migration 工具、feature flag、健康端点和 rollback 指令。
3. 识别真实的平台、环境/project/site、触发器、预期输出 URL、健康检查、源 ref/artifact、deploy 状态信号,以及操作者边界。
4. 比较说明和仓库证据。已变更的 workflow、目标、命令、secret 名称、artifact 来源或健康端点需要新的预检;切勿依赖记忆中的 Node06 profile。
5. 如果项目不进行部署,说明其实际分发路径,如 package、CLI、静态 artifact 或内部交接。不要虚构一个 Web 部署。

#### 3. 设定发布状态并保护凭证

1. 记录确切的操作、环境、ref/tag/artifact、命令或工作流输入,以及排除项,以便发布可复现和审计。
2. 将凭证、API key、token 和 secret 值排除在命令、日志、artifact、commit 和发布记录之外。使用已配置的 secret 引用,当所需 secret 不可用时明确失败;切勿虚构。
3. 不要覆盖 Node05 的 blocker 或所有者路由。发布计划可以在证据不完整时继续,但在证据存在之前不要声称发布已验证。
4. 用最清晰的适用结果描述就绪状态:

| 状态 | 使用场景 |
| --- | --- |
| 仅为准备 | 范围、目标、Node05 证据或发布事实不完整 |
| 可执行 | 所有必需的事实和门禁均为最新 |
| 阻塞 | 缺少或失败所需的门禁、恢复条件或发布事实 |

#### 4. 构建发布就绪矩阵

1. 分类风险:静态/文档、兼容的应用 deploy、认证/支付/数据/provider、migration/backfill、运维配置或 hotfix。
2. 为每个适用门禁记录 `pass`、`concern`、`blocker` 或 `not applicable`:Node05、源/artifact 身份、CI/build、目标/环境、凭证/secret、数据/provider、兼容性/恢复、smoke、watch、支持和沟通。
3. 当 staging 或 preview 路径已可用且发布风险使其有用时,使用该路径。不要为无害的静态变更要求 staging 或虚构一个。
4. 编写有序的 runbook:预检 -> 操作 -> migration/provider/flag -> smoke -> 短时观察 -> 禁用/rollback -> 发布记录和 Node07 交接。
5. 为手动或不可逆步骤指名操作者。runbook 必须区分 agent 可运行的命令和用户或平台所有者必须运行的命令。

## 部署环境、Pipeline 与 CI 控制

#### 1. 确立环境和部署边界

1. 命名实际适用的 local、preview、staging、production 和 provider 目标,包括 project/site/account、域名、数据库、队列、bucket、cron、webhook 和 deploy workflow 或手动操作。
2. 确认 preview 或 staging 是否能读取生产数据、使用生产 secret、向真实 provider 收费或发送面向用户的消息。将共享数据视为生产风险。
3. 仅盘点 secret 和变量名称。将仅服务器端的 secret 与公开配置分开,定义缺失 secret 的行为,并将值排除在日志、文档、截图、bundle、prompt 和生成文件之外。
4. 在受保护的操作之前,检查受保护环境、分支/ref 策略、所需 CI 检查、deploy 角色、provider 账户、rollback 访问权限,以及源/artifact 身份。

#### 2. 建模门禁拓扑和提升语义

显式建模受保护的发布路径:

    源修订 -> build artifact -> 所需质量聚合门禁
    -> 生产提升/alias -> 生产 smoke

将 artifact 构建与向受保护生产目标的提升区分开来。provider 可以在 CI 完成之前构建候选,但在所需的聚合门禁通过之前,阻止生产提升、alias 或受保护流量选择它。验证 provider 的实际行为;绿色的 build 或 deployment 记录本身不能证明预期的修订已被提升。

当分支保护或部署 provider 需要一个稳定的外部发布契约时,暴露一个稳定的聚合门禁名称。使其依赖于每个所需的质量 job,即使上游 job 失败、跳过或被取消也运行,并且除非每个所需结果成功或明确不适用,否则失败。保持内部 job 名称、矩阵和任何独立有用的所需检查可自由演进,而不会静默更改该外部契约。

#### 3. 检查 pipeline 和 artifact 信任

1. 阅读相关的 workflow 触发器、job、权限、可复用 workflow、action pin、deploy 脚本、包管理器、lockfile、缓存行为,以及 artifact 上传/下载。
2. 按 job 使用最小权限。仅所需的 deploy job 获得写入/部署权限;不受信任的 fork、PR 标题、分支、issue 文本和外部 payload 无法触及 secret。
3. Pin 或有意识地证明第三方 action 和远程脚本的合理性。当成熟的官方路径与仓库匹配时,优先使用它们,而非添加发布框架。
4. 当存在 lockfile 时要求确定性安装,缓存 key 不能跨越信任边界,并且 artifact 可追溯到已批准的 ref 和 workflow run。
5. 确认 deploy 命令不会静默指向与记录的发布事实不同的 project、环境或过时 artifact。

| 面 | 最低证据 |
| --- | --- |
| 目标 | 命名的平台/project/环境和数据边界 |
| 凭证 | secret 名称、范围、所有者,且无不受信任的暴露 |
| workflow | 触发器、权限、受信任的 action/脚本、受保护的 deploy 步骤 |
| artifact | 已批准的 ref、build 身份、workflow run 和目标匹配 |
| rollback | 对先前输出的访问、禁用控制或已批准的恢复所有者 |

#### 4. 设计 job 图、缓存和变更范围

并行运行独立的质量 job,仅表达真实的依赖关系。当不会中断受保护的发布操作时,取消同一分支或变更的已被取代的 run。用 lockfile、平台、工具链和关键 build 输入作为缓存 key,不要跨信任边界共享可写缓存。

双向测试路径过滤器。确认拥有的源、lockfile、容器、workflow 和部署配置变更会触发其所需的门禁,而纯文档变更不会重建或重启无关服务。切勿过滤掉定义过滤器本身的 workflow 或部署配置。将 CI 路径过滤与每个部署 provider 独立的 build 过滤区分开来。

测量整个 workflow 的墙钟时间和关键路径,而非并行 job 时长的总和。当速度是发布声明的一部分时,分别记录冷缓存和热缓存的观察结果;在打磨短 job 之前优化最长所需路径。

#### 5. 在托管环境中验证新的 pipeline 机制

静态 workflow 验证和本地命令成功不能证明远程 action 引用存在、容器镜像具有假定的 entrypoint,或托管 runner 能执行该 job。在声称新门禁可用之前:

1. 验证语法、表达式、job 依赖关系和聚合门禁逻辑;
2. 验证远程 action、可复用 workflow、镜像和工具引用在确切的记录 tag、version、digest 或 commit 处存在;
3. 在其实际托管的操作系统和架构上运行门禁;
4. 阅读完整的失败步骤日志并保留第一个因果错误;
5. 修复后,重新运行受影响的验证和每个所需的聚合门禁。

在下一次符合条件的受保护部署上验证新配置的 provider 检查。某些 provider 仅在托管 run 发布其确切名称后才暴露可供选择的检查,某些配置变更仅适用于后续部署。记录该激活边界,而非声称当前部署被追溯门禁。

#### 6. 分类红色、缺失或不稳定的 CI 门禁

1. 捕获 workflow/job/step、命令、ref、环境、完整错误、退出结果,以及同一命令是否在本地或可比的可信环境中复现。
2. 在修复前分类:workflow/config、依赖/安装/缓存、lint/type/test、build/artifact、deploy 权限/secret、应用行为、安全/质量或架构/契约不匹配。
3. 将缺失的所需门禁视为发布阻塞项,直到 Node05 和发布所有者明确接受替代证明。不要在没有重复证据的情况下将检查标记为不稳定。
4. 将应用缺陷路由到 Node03/04,敏感发现路由到 Node05,契约或运行时形态失败路由到 Node02。不要通过削弱 CI 来隐藏它们。

#### 7. 修复并重新验证窄范围 pipeline 机制

1. 仅当该修复是当前任务的一部分且不改变产品、安全、信任或公开行为时,才更改 Node06 拥有的 workflow/config 机制。
2. 形成一个因果假设,应用最小变更,重新运行受影响的命令,然后从当前源/artifact 重新运行每个所需的发布门禁。
3. 保留原始证据并记录更改了什么、为何安全,以及哪个新的输出证明门禁现在通过。
4. 当另一次聚焦尝试不会增加新证据,或证据暴露了共享耦合或不明确的所有权时,停止并返回 Node02/03/04/05,而非累积 pipeline 补丁。

## 保持源代码控制操作有意为之

将 commit、push、merge、历史重写、tag、release 和 deployment 视为不同的操作,以便发布记录可以准确说明发生了什么。在 commit 之前检查状态和完整的相关 diff;当存在无关工作时使用聚焦路径而非广泛暂存。

普通的指定工作默认留在 `main` 上。仅当结果足够不确定以至于轻松放弃是计划的一部分,或用户要求时,才创建探索性分支。在探索之前定义成功。仅在其行为、质量门禁和用户预期结果确认后才合并分支;否则如有需要保留有用的发现并放弃代码,而不强行合入 `main`。

多个写入 agent 需要独立拥有的切片,每个写入者一个分支或 worktree,以及一个集成所有者。共享契约、schema、核心类型或相同文件是需要序列化工作的信号。