# 生产健康与信号完整性

使用本指南来恢复实际发布的内容、验证运营信号、区分 incident 与学习问题，并在分析或实验之前路由主动伤害。

## 章节

- [发布后发现与信号完整性](#post-launch-discovery-and-signal-integrity)
- [健康、事件与恢复路由](#health-incident-and-recovery-routing)

## 发布后发现与信号完整性

#### 1. 恢复实际的 release 上下文

1. 读取 Node06 的 release-state 记录、source/target、即时 watch 结果、已知关注点、rollback 或 disable 姿态、预期早期信号、support 路径，以及任何在发布后仍然相关的 Node05 限制。
2. 分类当前模式：发布后即时 watch、稳定运营 review、活跃 incident/support 调查、学习问题、实验 readout，或周期性 founder review。
3. 在行动之前，根据当前证据核实事实。计划中的 rollout、假设的采纳、过时的 dashboard、或记忆中的 metric 都不是当前事实。
4. 当 release 关注点、关键路径、支付、provider、job、隐私或数据完整性信号提示存在主动伤害时，停止增长分析。

#### 2. 提出一个能改变决策的问题

1. 在打开 dashboard 之前先陈述决策：如果证据向任一方向移动，什么应该继续、停止、改变、调查，或下一步构建？
2. 命名目标 segment、用户 job、release/source 上下文、cohort 规则、时间窗口、baseline 或对比、预期价值信号，以及安全护栏。
3. 偏好能改变近期决策的问题。"一切进展如何？"是广泛扫描的提示，而不是一个主张或实验目标。
4. 在证据支持因果联系之前，将 acquisition、activation、retention、conversion、support 和 cost 分开保持。

#### 3. 构建最小信号卡片

在做出发布后主张之前使用此记录：

`decision question -> cohort/time window -> signal or evidence -> source -> confounds -> confidence -> owner -> next action`

| Evidence quality | 含义 | 适用主张 |
| --- | --- | --- |
| observed | 有日期的事件、可信日志、provider 记录或可复现路径 | 陈述测量结果及其范围 |
| estimated | 不完整计数、代理指标或手动重建样本 | 陈述估计及其局限 |
| self-reported | 用户、support、sales 或 founder 陈述 | 陈述谁报告了它，而不是它具有普遍性 |
| incomplete | 缺失事件、不可访问来源或样本不足 | 陈述差距并路由 instrumentation/research |

1. 记录 confounds，如发布年龄、流量来源、cohort 混合、季节性、support 介入、incident、外部活动、样本规模或 provider 变更。
2. 在安全和相称的情况下，将比率或计数与至少一个具体的 account/session/support 示例配对。从持久记录中编辑掉私有标识符。
3. 当来源无法支持时，不要强行给出 score、precision、trend 或因果叙述。

#### 4. 在缺失 instrumentation 时安全工作

1. 首先检查安全的现有证据：关键路径、日志、provider/job 状态、support 主题、已编辑的 session 证据、sales 笔记、退款/churn 原因，以及少量 opt-in 访谈。
2. 将最小的缺失测量定义为 actor、object、event、安全属性、timestamp、storage/retention、owner 和隐私边界。
3. 将 event schema、consent、identity 或 retention 设计路由到 Node02；将 backend 捕获路由到 Node03；将 frontend 交互捕获路由到 Node04；将 quality/security 证据路由到 Node05。
4. 在该路由产生证据之前，使用 `NEEDS_INSTRUMENTATION` 或 `NEEDS_USER_RESEARCH`，而不是一个自信的产品结论。

## 健康、事件与恢复路由

#### 1. 确立当前健康状态

1. 恢复 Node06 交接、release 状态、当前环境、依赖项、已知关注点、预期 watch 信号、support 通道，以及 rollback/disable 权限。
2. 只检查能改变运营决策的信号：主要用户路径、可用性、错误/正确性、体感 latency、job/webhook 成功率、支付完整性、数据持久性、provider 配额/成本，以及 support 负担。
3. 使用现有项目工具和原始输出。将不可用来源标记为 `unknown`、`skipped` 或 `unavailable`；不要用通用健康分数替代它们。
4. 告警必须意味着一个具体行动。好奇心或长期观察属于后续 review，而不是即时 incident 门槛。

#### 2. 分诊影响并分配 severity

1. 分类问题及其边界：活跃用户伤害、security/privacy、主要路径/auth/payment/data 失败、重要路径退化/support 激增、轻微 UX bug，或低优先级边缘情况。
2. 记录受影响的 segment/path、首次已知时间、release/provider/job 上下文、观察到的证据、当前用户影响，以及遏制权限。将客户标识符、密钥、支付详情和原始私有 payload 排除在持久 docs 之外。
3. 使用简短的 severity 模型：

| Severity | 含义 | 首要路由 |
| --- | --- | --- |
| `SEV0` | security、privacy、data 或 billing 完整性风险 | 立即路由到 Node05 和 Node06 |
| `SEV1` | 主要路径、auth、payment 或 data 失败 | Node06 遏制，然后 Node03/04/05 |
| `SEV2` | 重要退化、provider/job 失败、support 激增 | owner 修复并活跃 watch |
| `SEV3` | 轻微 bug、信任/UX 混乱、有界 workaround | Node03/04 或 Node01 证据路由 |
| `SEV4` | 低影响边缘或孤立请求 | 分类、搁置，或加入学习 review |

#### 3. 在广泛分析之前先遏制

1. 对于 `SEV0`/`SEV1`，保留已编辑的证据，并调用 Node06 release workflow 以通过 Node06 的 release workflow 进行 disable、rollback、job 暂停、provider 切换或流量控制。
2. Node07 可以承认影响并准备安全的 support 上下文，但它从不 deploy、rollback、更改生产配置，或编辑 provider 状态。
3. 将实现路由到 Node03/04，将 quality/security 证明路由到 Node05，将契约、恢复或共享 runtime 不确定性路由到 Node02。
4. 只沟通已确认的影响、安全的 workaround、下次更新的 owner/时间，以及任何所需的客户行动。不要在没有证据的情况下承诺 root cause 或恢复时间。

#### 4. 在遏制之后系统性地调查

1. 在可能时安全地复现，读取完整错误，比较最近的工作路径或先前 release，并追踪相关的 request/data/provider 边界。
2. 陈述一个假设："我认为 X 导致了 Y，因为 Z。"选择最小的证据收集或一个能反驳它的聚焦修复。
3. 在每次更改后复查受影响路径和邻近 regression。保留原始证据，并区分症状 workaround 与 root-cause 解决。
4. 当另一次尝试不会增加新证据，或证据暴露了共享耦合、契约冲突，或错误的 runtime 前提时，停止本地修复并返回 Node02/03/04/05。

#### 5. 将重复 support 转为学习候选

1. 按 user job、segment、频率、影响、workaround、成本和潜在原因对已解决或有界的报告进行分组，而不仅仅按请求措辞。
2. 单个报告可以继续作为 support 工作。重复的、高成本的或改变行为的证据可以在健康稳定后进入客户综合或下一个 slice 决策。
