# 客户证据、实验与下一个切片

当健康状况稳定后，使用本指南来综合客户价值证据、选择一个有界实验或 next slice，并保留由此产生的运营决策，而不创建历史堆积。

## 章节

- [客户价值、funnel 与证据综合](#customer-value-funnel-and-evidence-synthesis)
- [实验、next slice 与 founder 决策](#experiments-next-slice-and-founder-decision)
- [ops learning 状态与 review 交接](#ops-learning-state-and-review-handoff)

## 客户价值、funnel 与证据综合

#### 1. 定义问题与 cohort

1. 重述目标 segment、用户 job/pain、产品承诺、activation 定义、time-to-value、retention 或 conversion 预期，以及相关 trust guardrail。
2. 提出一个决策问题，并按 launch、来源、plan、segment、onboarding 路径、feature 接触面、account age 或一个明确说明的手动样本来选择 cohort。
3. 说明比较依据与局限：baseline、先前 cohort、working path，或无可用比较。不要合并不可比的 cohort 来构造一个看似便利的叙事。

#### 2. 沿最小有用价值路径跟进

1. 只检查回答该问题所需的路径：acquisition -> intent -> signup -> activation/time-to-value -> repeat/retention -> conversion -> expansion/referral -> churn/refund/support。
2. 当 trust、provider 成本、support 负担或 workflow 替换对此产品有意义时，将它们用作价值信号。不要为每个决策都要求完整的 funnel。
3. 在 routing 之前，先区分 acquisition mismatch、comprehension/trust 摩擦、UX 摩擦、missing value、pricing 犹豫、reliability defect 和 provider-cost 问题。

| 症状 | 最可能的首位 owner |
| --- | --- |
| 有流量但 trust action 低 | Node01 或 Node04 |
| 有 signup 但无 activation | Node04 或 Node03 |
| 有 activation 但无 repeat 使用 | Node01 或 Node07 实验 |
| 有 retention 但无 purchase | Node01 pricing/promise review，然后 Node04 |
| checkout/payment 失败 | Node03、Node05 和 Node06 |
| 使用量高但 provider 成本激增 | Node02、Node03 和 Node07 watch |
| 用户质疑安全性或合法性 | Node01、Node04 和 Node05 |

#### 3. 将数字与具体证据配对

1. 只收集安全、相关的来源：带日期的 analytics、logs、support 记录、opt-in 访谈、sales 笔记、reviews、社区讨论、churn/refund 原因、usage 记录，以及当当前条件相关时谨慎范围之内的公开市场证据。
2. 将比率/计数与具体 session、account、workaround 或用户语言配对。一个数字可以指明该看哪里，但极少能单独解释原因。
3. 记录证据来源、日期、segment、样本局限、隐私处理方式，以及是 observed、estimated 还是 self-reported。
4. 永远不要在持久项目状态中存储原始 PII、私密对话、支付详情、机密 prompt 或客户内容。

#### 4. 按 job 与矛盾进行综合

1. 按 job/pain、失败结果、workaround、触发因素、付费意愿和受影响 segment 对证据分组，而不是按所请求的 feature 标签分组。
2. 评估行为、金钱、频率、紧迫性、成本、segment 契合度与矛盾。已付费/续费/迁移/邀请的行为，比单次请求或赞美更有说服力。
3. 指出看似合理的替代解释：错误流量、季节性、onboarding 新奇效应、近期 release regression、support 介入、样本偏差，或一个不同的用户 job。
4. 对结果分类：bug、UX 困惑、docs/onboarding、trust、missing value、pricing、机会、research gap、park 或 reject。没有判别性证据的结论只是一个假设，不能成为 roadmap 条目。

## 实验、next slice 与 founder 决策

#### 1. 选择正确的决策路径

1. 确认 health 稳定、segment 与问题已定义，并且可用证据能够区分一个实验与一个已知 defect 或缺失的产品决策。
2. 当对 message、channel、onboarding 理解度、手动交付、support/docs、engagement 意愿，或一个有界行为变更存在不确定性时，使用实验。
3. 当工作是已确认的 bug、安全议题、payment/data 风险、architecture 问题、release 议题或 product-scope 决策时，改为直接 routing。
4. 一个 pricing、positioning、target user、product promise，或实质性 business-model 变更，在实验推进之前必须先回到 Node01。

#### 2. 设计一个实验

1. 写下：`如果我们对 segment Y 改变 X，信号 Z 应该因 R 而移动。`
2. 定义当前 baseline 或无 baseline、允许的变更幅度、success metric、guardrail、cohort、duration 或样本 caveat、stop/kill 条件、readout 时间，以及 owner。
3. 只选一个主要变更：onboarding 文案、文档、opt-in research、手动 concierge、support macro、一个有限 channel message，或一个已 pre-approved 并 routing 至其实现 owner 的 product surface。
4. Guardrails 可包括 error/support 负担、refund/churn、成本、延迟、trust、accessibility、consent，以及 target-user 伤害。一个实验必须有 stop path。
5. 不要捆绑变量。如果多步变更不可避免，将其标注为 exploratory，并且不要推断单一因果结论。

#### 3. 执行最小实验动作

当满足以下条件时，Node07 可执行测试当前假设所需的最小动作：

- 可逆、低量、非代码、且 non-destructive；
- 不涉及 PII、payment、pricing、合同、生产配置，以及 provider side effects；
- 真实、涉及用户联系时 opt-in，并与既有承诺一致；
- 由具名的 audience、channel、duration、owner、stop 条件和 readout 界定。

示例：support macro 试用、文档实验、手动 concierge 提议、opt-in 访谈邀请，或一个有限 channel message。website/page 变更 routing 至 Node04，product 行为至 Node03/04，instrumentation 至 Node02/03/04，release 或 provider 动作至 Node06。

永远不要发送垃圾信息、爬取私密数据、冒充他人、做无支撑的宣称、使用 dark pattern、向用户收费、更改 price/entitlement，或将一次手动试用转为自动化。

#### 4. 诚实读取结果

1. 将观察到的结果与 guardrails，同原始假设、cohort、baseline 和已知 confounds 比较。当短定性样本能解释行为时，收集之。
2. 选择一个结果：continue、expand、revise、narrow、pause、kill、revert 或 route。
3. 不要把一个无结论的样本称作 win 或 loss。说明实验是否降低了不确定性、还有什么未知，以及下一步所需的最小证据。

#### 5. 将证据转化为一个 next slice

1. 排序：主动伤害、security/privacy、activation/payment 完整性、support/retention、付费意愿、provider cost/reliability、strategic wedge，然后是 polish。
2. 创建一个单一 handoff：source/evidence、期望结果、owning node、size/risk、non-goals、acceptance 或 success signal，以及 revisit trigger。
3. 只有在存在具体触发因素（如重复需求、付费 pilot、metric 阈值、访谈证据、风险下降，或时间）时才 park。公开 reject 不匹配的、仅与竞品相关的、或工作量不成比例的事项。

## ops learning 状态与 review 交接

#### 1. 只在事实变化时更新持久状态

1. 使用既有 HTML 项目 command board 与 output ownership：将 operations、growth 和 release 事实保留在其 owning board 区域；只在必要时使用一条简洁的 traceability 注记。
2. 当 health、incident posture、客户证据、实验结果、next decision、active concern 或 owner 发生实质性变化时，更新持久页面。不要仅因进行了一次运营 review 就重写稳定的产品或 architecture 页面。
3. 保留稳定的 board 事实，避免并行 roadmap 页面、gstack JSONL memory、个人 builder profile，或另一个并行项目笔记本。

#### 2. 写一份当前运营 checkpoint

1. 记录 release/context、health 状态、受影响用户或 segment、决策问题、证据来源与质量、confidence、实验状态、decision、owner/route、active concern、revisit trigger，以及下次 review 时间。
2. 使用与当前事实相符的 status vocabulary：`HEALTHY`、`WATCH`、`INCIDENT`、`MITIGATED`、`NEEDS_INSTRUMENTATION`、`NEEDS_USER_RESEARCH`、`LEARNING_FOUND`、`EXPERIMENT_ACTIVE`、`NEXT_SLICE`、`PARKED`、`REJECTED` 或 `BLOCKED`。
3. 当属实时说 `owner missing` 或 `signal unavailable`。永远不要在没有实际 owner 和新鲜证据的情况下，暗示存在自动 monitoring 或已解决决策。
4. 脱敏客户姓名、email、ID、支付信息、私密内容、provider payload、prompt，以及机密 support 上下文。

#### 3. 运行一次聚焦的 founder review

1. 只在能产生决策时进行周期性 review。恢复前次 checkpoint、release 上下文、health/incident 变化、客户证据、实验 readout、support 主题、cost/reliability 议题，以及 accepted/parked/rejected 的工作。
2. 使用可比时间窗与来源质量识别有意义的趋势或 regression；不要默认创建一个固定 health score 或 code-quality 回顾。
3. 以以下之一收尾：keep watching、instrument/research、运行一次实验、route 一个 next slice、修订产品前提、contain 一个 incident，或显式带触发因素地 defer。

#### 4. 重新验证既往 learning

1. 在依赖一条较早的 insight 之前，检查其 release、cohort、来源、product 行为、客户 segment 或市场条件是否仍然适用。
2. 当某条 learning 的支撑来源已消失、产品已变化，或一个更新的结果与之矛盾时，将其标记为 stale。保留当前 confidence 和原因，而不要删除有用的不确定性。
3. 通过收集判别性证据、将 claim 收窄至其 cohort/时间窗，或 routing 一个 research/instrumentation 问题来化解矛盾。不要对互相冲突的 claim 取平均。

#### 5. 审慎 handoff

1. 向 owning node 传递最小充分上下文：evidence、decision、outcome、non-goals、risk、acceptance/success signal、constraints，以及 revisit trigger。
2. 将持续运营观察 routing 至一个真实 owner 或已批准的自动化。Node07 不承诺在 session 之间进行后台 monitoring。
3. release 动作 routing 至 Node06，quality/ship 状态至 Node05，已变更的 product truth 至 Node01。
