# 范围裁剪与规格说明

将完成的发现裁剪到足以测试最高风险假设的最小产品。然后编写 Node02 将消费的规格说明。

## MVP 纳入规则

一个功能只有满足以下任一条件才进入 MVP：

1. 没有它，核心任务无法完成。
2. 没有它，最高风险假设无法被测试。
3. 没有它，产品不安全、不合法或不可信。
4. 没有它，被衡量的用户行为会产生误导。

如果一个功能都不满足，归入范围外或非目标。

## 范围裁剪质询

对每个候选功能，问：

> 如果移除它，用户仍能完成核心任务吗？

- 是：范围外，可能以后再做。
- 否，但存在人工替代：范围外，用替代方案。
- 否且无替代方案：范围内。

然后问：

> 这个功能是否引入新的用户类型、平台、数据类型、集成或商业模式？

如果是，重新考虑。它可能是扩展产品边界的范围泄漏。

在这些选择仍能保持被测试的价值主张的前提下，优先选用临时人工操作、单一平台、单一语言、单一工作流和受控的引导。不要伪造信任、安全、隐私、法律、支付或不可逆的数据行为。

## 编写规格说明

将质询综合为以下文档。证据薄弱时保持各节简洁。不要用通用语言填充篇幅。

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

当用户在 Node01 阶段变更某项需求时，不要对变更进行分类。询问它影响的是哪些已决定的条目：受众、核心旅程，还是范围。只重新质询受影响的部分。更新规格说明。保持简单。

## 不应做的事

- 不要在未命名所满足的纳入规则的情况下包含功能。
- 不要将"快"、"简单"、"安全"或"直观"列为需求。替换为可衡量或可观察的条件。
- 不要在规格说明中规定架构。陈述任务和约束。
- 不要让验收标准保持主观。
- 不要省略非目标。没有它们，范围会悄悄漂移。
