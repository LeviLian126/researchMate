# 切片框架

在编写代码之前使用本指南。它将已批准的后端切片框架化为一个紧凑的实现计划,使后续的 workflow 文件(domain、interface、persistence、provider、proof)拥有它们所需的一切。

对于平凡修复(单行变更,无 contract 影响),跳过本文件并直接进入相关的构建文件。对于任何涉及 contract、状态、数据或外部边界的变更,先进行框架化。

## 章节

- [还原实现真相](#还原实现真相)
- [构建实现主干](#构建实现主干)
- [选择构建模式](#选择构建模式)
- [挑战范围](#挑战范围)
- [框架化构建](#框架化构建)

## 还原实现真相

阅读 Node01/02 的交接文档,将切片重述为一个可观察的结果。然后检查 repository,在基于事实实现之前验证每一个关键事实。不要把这变成全 repository 的考古项目——只审计相关路径的入口点、直接调用方、领域所有者、repository、访问强制执行、error mapper 和测试工具。

通过一个具体示例来理解。假设切片是"用户取消订阅"。

**重述结果**:一个已认证的用户取消自己的订阅。订阅进入 `cancelling` 状态。计费在周期结束时停止。用户看到确认信息。发送一封取消确认邮件。

**在 repository 中验证**(阅读实际代码,不要假设):

1. **入口**:找到现有的订阅路由。它有 `PATCH /subscriptions/:id` 还是 `POST /subscriptions/:id/cancel`?阅读路由文件及其 handler。注意传输约定(REST、RPC、event-driven)。

2. **领域所有者**:哪个模块拥有订阅状态?寻找 `SubscriptionService`、`SubscriptionDomain` 或类似模块。如果没有所有者,这是一个设计信号——切片可能需要一个新的所有者,这意味着返回 Node02。

3. **Repository**:订阅数据如何访问?找到 repository 或数据访问模块。存在哪些查询模式?是否已有 tenant/owner scoping?

4. **访问强制执行**:authorization 在哪里检查?寻找 middleware、decorator 或 handler 内检查。是否有类似 `requireOwnership(subscriptionId, userId)` 的模式?

5. **Error mapper**:错误如何返回?找到错误处理模式。是否有中央 mapper,还是 handler 临时构造错误响应?

6. **测试**:使用什么测试框架?找到最近的订阅行为测试。存在哪些 fixture 和 helper?

对每个事实进行分类:**从代码验证**(你读过)、**从 contract 验证**(Node02 文档记录了)、或**假设**(你推断的)。关于公共字段、schema 语义、tenancy、authorization、provider 行为或恢复的假设,必须在实现前对照已批准的来源确认。本地命名、fixture 值和日志措辞可以使用可逆的默认值。

## 构建实现主干

在选择文件或类之前,先追踪已批准的行为。主干通过每个所有者将能力连接到验证:

```
capability -> entry -> interface/access -> domain policy -> data/provider
           -> observable result or recoverable failure -> local proof
```

对于每个箭头,命名现有的所有者或明确标记为 `[NEW]`。缺失的所有者是一个设计信号,不是将所有行为放入 controller 的许可。

"用户取消订阅"的主干示例:

```
[Cancel subscription]
    |
    v
PATCH /subscriptions/:id/cancel          <-- entry (现有路由)
    |
    v
validate input + authenticate user       <-- interface (现有 auth middleware)
    |
    v
resolve subscription + check ownership   <-- access (现有 requireOwnership)
    |
    v
SubscriptionService.cancel()             <-- domain [现有所有者上的新方法]
  - verify current state is 'active'
  - transition to 'cancelling'
  - schedule billing stop at period end
  - enqueue cancellation email
    |
    v
SubscriptionRepository.update()          <-- data (现有 repo)
    |
    v
return { status: 'cancelling',           <-- result (稳定响应)
          cancelsAt: periodEndDate }
    |
    v
test: cancel active subscription         <-- proof
      -> state becomes 'cancelling'
      -> billing stop scheduled
      -> email enqueued
      -> cancel already-cancelled -> conflict
```

这个主干不是逐文件的代码计划。它防止实现者在变更已经扩散到 repository 之后才发现 contract。

## 选择构建模式

使用覆盖实现风险的最窄模式。

**扩展现有模块**——最常见的模式。一个现有模块已经拥有相关行为;你向它添加一个方法或分支。示例:向已有的 `SubscriptionService`(已有 `create()` 和 `renew()`)添加 `cancel()`。阅读 `domain-build.md` 了解所有者放置,如果入口变更则阅读 `interface-build.md`。

**新边界**——一个真正的新能力,没有现有模块拥有。示例:当没有导出模块时添加导出功能。这需要证据证明不存在合适的路径,以及 Node02 批准的模块边界。阅读 `domain-build.md` 了解所有者设计,`interface-build.md` 了解入口,如果需要新数据访问则阅读 `persistence-build.md`。

**回归修复**——观察到的行为错误或测试失败。在修改代码之前先复现。阅读 `proof-debug-observability.md` 了解调试 workflow,然后 在最窄的所有者处修复。

当切片真正跨越多个边界时,模式可以组合。如果变更扩展为多个独立结果、信任模型、数据生命周期或发布风险,返回 Node02 做切片决策,而不是悄悄扩大实现。

## 挑战范围

在实现之前,回答这五个问题。它们防止范围蔓延和不必要的抽象:

1. **实现已批准结果的最小垂直变更是什么?**如果答案涉及多个用户可见结果,切片太宽了。

2. **现有的路由、service、repository、adapter、job 或测试是否已经解决了部分问题?**在创建之前先复用。命名你正在扩展的具体模块和方法。

3. **提议的抽象是在保护一个真实的边界还是在隐藏不确定性?**应用删除测试:如果你删除了抽象,复杂度会消失(它只是一个 pass-through)还是会在 N 个调用方中重新出现(它在发挥作用)?

4. **哪些工作明确不在范围内,应该保持延迟?**命名它,这样它就不会在实现过程中悄然混入。

5. **这条新路径在生产中可能造成什么现实故障,之后的哪个验证能将它与猜测区分开?**命名故障模式和能捕获它的测试。

## 框架化构建

在编辑之前生成一个紧凑的实现框架。这不是逐文件计划——它记录防止实现者猜测的决策。

- **outcome**:正在实现的可观察行为(一句话)
- **owners**:现有或新的 entry、domain、data 和 docs 所有者(命名的模块)
- **invariant**:在变更之前、期间和之后必须保持为真的条件
- **allowed change**:可能变更的文件或模块及原因(命名它们)
- **non-goals**:刻意保留不动的相关工作
- **local proof**:展示 contract 的针对性测试、复现或安全观察
- **side-effect limit**:此切片不得跨越的凭证、数据、provider、migration 或环境边界
- **escalation**:需要 Node01(产品含义)、Node02(contract)、Node05(质量/安全)或 Node06(发布)重新介入的证据

"用户取消订阅"的框架示例:

- **outcome**:已认证用户取消自己的活跃订阅;状态转为 `cancelling`;计费在周期结束时停止;发送确认邮件
- **owners**:`SubscriptionService`(domain,新方法)、`SubscriptionController`(entry,新 handler)、`SubscriptionRepository`(data,现有)、`EmailQueue`(async,现有)
- **invariant**:订阅只能从 `active` 转换到 `cancelling`;计费不得在周期结束日期之后收费;取消是 idempotent 的(取消一个已经在取消中的订阅返回当前状态,而非错误)
- **allowed change**:`SubscriptionService`(添加 `cancel` 方法)、`SubscriptionController`(添加 cancel 路由)、订阅测试文件(添加行为测试)
- **non-goals**:退款逻辑、计划降级、UI 变更、邮件模板变更
- **local proof**:通过 `SubscriptionService.cancel` 的单元测试,使用进程内 fake repository;验证状态转换、计费停止、邮件入队和 idempotent 重复取消
- **side-effect limit**:测试中不发送真实邮件;不调用真实 billing provider;不进行 schema migration
- **escalation**:如果 billing provider 没有"在周期结束时停止"的 API,返回 Node02 做 contract 决策;如果取消需要退款,返回 Node01 做产品决策
