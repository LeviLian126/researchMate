# 范围裁剪与规格说明

将已完成的发现裁剪至能测试最高风险假设的最小产品。然后编写 Node02 将消费的规格说明。

## MVP 纳入规则

一个功能进入 MVP 仅当以下至少一项为真：

1. 没有它，核心任务无法完成。
2. 没有它，最高风险假设无法测试。
3. 没有它，产品不安全、不合法或不可信。
4. 没有它，测量的用户行为会产生误导。

如果功能不满足任何一项，它归入范围外或非目标。

## 范围裁剪质询

对于每个候选功能，问：

> 如果移除它，用户还能完成核心任务吗？

- 能：范围外，可能以后做。
- 不能，但存在手动替代方案：范围外，使用替代方案。
- 不能且无替代方案：在范围内。

然后问：

> 此功能是否引入了新的用户类型、平台、数据类型、集成或商业模式？

如果是，重新考虑。它可能是扩大产品边界的范围泄漏。

当这些选择能保持被测试的价值主张时，优先选择临时手动操作、单一平台、单一语言、单一工作流和受控的入门流程。不要在信任、安全、隐私、法律、支付或不可逆数据行为上造假。

## 编写规格说明

将质询综合为以下文档。当证据薄弱时保持各节简洁。不要用通用语言填充篇幅。

```markdown
# Product Spec: [Name]

## Problem statement
Who, what pain, how they cope today, why solve this now.

## Target audience
### Primary audience
Behavior: situation, frequency, severity, current alternative, reachable channel.
### Excluded audience
Explicitly not supported.

## Core user journey
Trigger -> entry -> required input -> core action -> result -> user next step ->
return loop.

A core flow is incomplete if it produces output but does not help the user act,
decide, save, share, recover, or return.

## Alternatives and differentiation
| Alternative | What it covers | Why users have not switched | Our difference |
|---|---|---|---|

Write the differentiation as a specific trade-off, not "AI-powered" or "simpler."

## Scope
### In scope
Each feature with the inclusion rule it satisfies (1, 2, 3, or 4).
### Out of scope (this version)
Features deferred. Each with a revisit trigger: what event or evidence would bring
it back.
### Non-goals
What the product is intentionally not becoming. Use non-goals to prevent scope drift.

## Acceptance criteria
1. [Testable, pass/fail condition]
2. [...]

No "works correctly" or "handles edge cases." State the observable behavior.

## Risk assumptions
| Assumption | What happens if false | Cheapest test |
|---|---|---|

## Decision
- [ ] GO: proceed to Node02 for architecture design
- [ ] VALIDATE: run the cheapest test first (name it)
- [ ] NO_GO: current evidence does not support continuing
```

## 需求变更

当用户在 Node01 期间变更需求时，不要对变更进行分类。问它影响哪些已决定的条目：受众、核心旅程或范围。只对受影响的部分重新质询。更新规格说明。保持简单。

## 不应做的事

- 不要在未指明满足哪条纳入规则的情况下纳入功能。
- 不要将"快"、"简单"、"安全"或"直观"列为需求。替换为可衡量或可观察的条件。
- 不要在规格说明中规定架构。陈述任务和约束。
- 不要让验收标准保持主观。
- 不要跳过非目标。没有它们，范围会悄然漂移。