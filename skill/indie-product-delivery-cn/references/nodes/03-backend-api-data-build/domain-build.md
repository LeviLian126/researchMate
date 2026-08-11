# 领域构建

使用本指南将业务行为放置在正确的所有者中,并实现领域逻辑:use-case 所有权、状态转换、策略强制执行和副作用协调。如果尚未框架化切片,请先阅读 `slice-framing.md`。

Node02 定义 contract(状态机、invariant、失败行为)。本文件实现它们。如果需要 Node02 未定义的新状态、费用规则、公共错误、恢复动作或兼容性行为,停止——这是系统决策,不是实现默认值。

## 章节

- [定位 use-case 所有者](#定位-use-case-所有者)
- [编写可执行的 use-case 路径](#编写可执行的-use-case-路径)
- [保持策略、状态和副作用的一致性](#保持策略状态和副作用的一致性)
- [反模式:过度抽象](#反模式过度抽象)
- [反模式:领域中的传输逻辑](#反模式领域中的传输逻辑)
- [基于锁定基线重构](#基于锁定基线重构)

## 定位 use-case 所有者

从实现主干开始,识别已经拥有业务结果的模块。优先扩展现有的 service 或领域模块,而非创建新的。controller、CLI 命令或 webhook handler 可以将传输转换为意图,但它不能成为可复用业务规则的归宿。

### 好的做法:领域 service 拥有规则,controller 转换传输

```typescript
// controller -- 轻量:解析、认证、调用 domain、映射结果
async function cancelSubscription(req: Request, res: Response) {
  const userId = req.auth.userId;           // 可信,来自 middleware
  const subId = req.params.id;
  const result = await subscriptionService.cancel(subId, userId);
  res.status(200).json(mapToResponse(result));
}

// domain service -- 拥有业务规则
class SubscriptionService {
  async cancel(subscriptionId: string, userId: string): Promise<CancelResult> {
    const sub = await this.repo.findById(subscriptionId);
    if (!sub) return { kind: 'not_found' };
    if (sub.userId !== userId) return { kind: 'denied' };
    if (sub.state !== 'active') return { kind: 'conflict', currentState: sub.state };

    sub.state = 'cancelling';
    sub.cancelsAt = sub.periodEndDate;
    await this.repo.save(sub);
    await this.emailQueue.enqueue({ to: sub.email, template: 'cancel-confirm' });

    return { kind: 'ok', cancelsAt: sub.cancelsAt };
  }
}
```

controller 不知道"active"意味着什么,也不知道邮件会发送。domain service 不知道 HTTP 的存在。各自只有一个变更的理由。

### 错误的做法:业务逻辑在 controller 中

```typescript
// controller -- 已经变成了领域所有者(错误)
async function cancelSubscription(req: Request, res: Response) {
  const sub = await db.subscriptions.findById(req.params.id);
  if (!sub) { res.status(404).json({ error: 'not found' }); return; }
  if (sub.userId !== req.auth.userId) { res.status(403).json({ error: 'forbidden' }); return; }
  if (sub.state !== 'active') { res.status(409).json({ error: 'conflict' }); return; }

  sub.state = 'cancelling';
  sub.cancelsAt = sub.periodEndDate;
  await db.subscriptions.save(sub);
  await sendEmail(sub.email, 'cancel-confirm');   // 直接调用 provider

  res.status(200).json({ status: sub.state, cancelsAt: sub.cancelsAt });
}
```

问题:业务规则(状态转换、idempotency、邮件触发)被埋在传输代码中。它无法在不通过 HTTP 的情况下测试。第二个入口点(CLI、webhook)会复制整个规则。provider 调用(`sendEmail`)不在 adapter 之后。

### 何时创建新 service vs 扩展现有 service

当一个新 service 拥有现有模块未覆盖的独特 invariant 时,创建它是合理的。不要为了隐藏附近模块已经拥有的一行策略而创建 service。信号是所有权,不是架构美学。

## 编写可执行的 use-case 路径

在修改实现之前,用结果语言编写预期路径。这是 Node02 已选择的状态和失败行为的实现映射:

```
validated intent -> policy and invariant -> state decision -> durable change
  or external request -> domain result -> boundary-specific response
```

命名每个行为有意义的分支。当结果可能是成功、accepted/pending、no-op 重复、conflict、validation 失败、denied、临时失败或 recovery-required 时,保留区别。将所有 exception 折叠为通用失败会擦除 contract。

```typescript
type CancelResult =
  | { kind: 'ok'; cancelsAt: Date }
  | { kind: 'not_found' }
  | { kind: 'denied' }
  | { kind: 'conflict'; currentState: string }
  | { kind: 'provider_error'; retryable: boolean; correlationId: string };
```

`cancel()` 的每个调用方必须处理每个变体。这强制 interface 层将每个结果映射到独立、稳定的响应,而不是对所有情况返回 500。

## 保持策略、状态和副作用的一致性

在能看到相关可信事实的所有者中实现策略。通过 contract 使用现有的 repository 和 adapter;不要绕过它们。

### Authorization:消费服务端决策

领域层从 interface 层接收已认证的身份。它通过比较可信状态来强制执行所有权,而不是信任调用方提供的值。

```typescript
// 好的做法:从可信状态检查所有权
const sub = await this.repo.findById(subscriptionId);
if (sub.userId !== userId) return { kind: 'denied' };   // userId 来自 auth,不是 request body

// 错误的做法:信任调用方提供的 owner
const sub = await this.repo.findById(req.body.subscriptionId);
if (sub.orgId === req.body.orgId) proceed();             // req.body.orgId 不可信
```

### 状态转换:写入前验证

只允许 contract 规定的源到目标转换。应用内存中的预检查不是持久的并发控制——参见 `persistence-build.md` 了解持久机制。但领域层必须表达规则:

```typescript
const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  active: ['cancelling', 'past_due'],
  cancelling: ['cancelled'],
  past_due: ['cancelling', 'cancelled'],
  cancelled: [],   // 终态
};

function canTransition(from: string, to: string): boolean {
  return ALLOWED_TRANSITIONS[from]?.includes(to) ?? false;
}
```

### Idempotency:协调重复身份

如果同一个取消请求到达两次,第二次调用不得发送第二封邮件或安排第二次计费停止。使用持久 idempotency key(参见 `persistence-build.md`)。在领域层,先检查当前状态:

```typescript
// 如果已经在取消中,返回当前状态 -- 不重新处理
if (sub.state === 'cancelling') {
  return { kind: 'ok', cancelsAt: sub.cancelsAt };   // idempotent 成功
}
```

### Transaction:明确什么是原子的

将必须一起成功或失败的领域变更分组。将机制委托给 persistence 层,但在领域方法中明确什么是原子的、什么最终被对账。

```typescript
async cancel(subscriptionId: string, userId: string): Promise<CancelResult> {
  return await this.tx.run(async (tx) => {
    // 原子:状态更新 + idempotency 记录必须一起成功
    const sub = await tx.subscriptions.findById(subscriptionId);
    // ... 检查 ...
    sub.state = 'cancelling';
    await tx.subscriptions.save(sub, sub.version);   // optimistic lock
    await tx.idempotency.mark(requestId, 'cancel', sub.id);

    // 最终一致:邮件入队,不是内联发送
    await this.emailQueue.enqueue({ to: sub.email, template: 'cancel-confirm' });

    return { kind: 'ok', cancelsAt: sub.cancelsAt };
  });
}
```

如果系统无法解释什么是原子的、什么最终被对账,返回 Node02 而不是近似一致性。

### 外部请求:在调用之前创建持久意图

在进行外部请求之前,创建已批准的持久意图或状态。如果 provider 调用失败,系统有记录表明什么应该发生,并可以重试或对账。

```typescript
// 好的做法:先记录意图,然后调用 provider
await tx.refunds.insert({ subscriptionId, amount, status: 'pending' });
const result = await this.billingAdapter.requestRefund(subscriptionId, amount);
await tx.refunds.update(subscriptionId, { status: result.ok ? 'completed' : 'failed' });

// 错误的做法:先调用 provider,希望写入成功
const result = await this.billingAdapter.requestRefund(subscriptionId, amount);
await tx.refunds.insert({ subscriptionId, amount, status: result.ok ? 'completed' : 'failed' });
// 如果 insert 失败,退款发生了但没有本地记录
```

## 反模式:过度抽象

LLM 经常创建只有一个实现的抽象:一个从未被继承的 `AbstractRepository<T>`,一个只有一个 provider 的 `ProviderFactory`,一个包装单个 service 的泛型 `Manager`。这些增加了没有杠杆的间接层。

### 删除测试

在添加抽象之前应用这个测试:想象删除它。如果复杂度消失了,它只是一个 pass-through。如果复杂度在 N 个调用方中重新出现,它在发挥作用。

### 一个 adapter 意味着假想的 seam。两个 adapter 意味着真实的 seam。

除非至少有两个 adapter 是合理的(通常是 production + test),否则不要引入 port 或 interface。单 adapter 的 seam 只是间接层。

```typescript
// 过度抽象:一个实现,看不到第二个 adapter
interface ISubscriptionRepository {
  findById(id: string): Promise<Subscription | null>;
  save(sub: Subscription): Promise<void>;
}
class SubscriptionRepositoryImpl implements ISubscriptionRepository { /* ... */ }
// interface 增加了一层间接,零杠杆。
// 测试可以直接 mock 具体类。

// 直接:相同行为,更少仪式
class SubscriptionRepository {
  findById(id: string): Promise<Subscription | null> { /* ... */ }
  save(sub: Subscription): Promise<void> { /* ... */ }
}
// 当第二个实现出现时(例如 test double 或不同的存储),
// 再提取 interface。不要提前。
```

当你确实需要 seam(两个真实 adapter)时,在边界处定义 interface 并注入它。参见 `provider-async-build.md` 了解 adapter 模式。

## 反模式:领域中的传输逻辑

领域 service 不得返回 HTTP 状态码、了解 JSON,或导入框架类型。传输关注点属于 interface 层。

```typescript
// 错误的做法:domain 返回 HTTP 状态
class SubscriptionService {
  async cancel(id: string, userId: string) {
    const sub = await this.repo.findById(id);
    if (!sub) throw new HttpError(404, 'not found');         // HTTP 泄漏
    if (sub.userId !== userId) throw new HttpError(403);     // HTTP 泄漏
    // ...
  }
}

// 好的做法:domain 返回领域结果,interface 映射到 HTTP
class SubscriptionService {
  async cancel(id: string, userId: string): Promise<CancelResult> {
    const sub = await this.repo.findById(id);
    if (!sub) return { kind: 'not_found' };                  // 领域语言
    if (sub.userId !== userId) return { kind: 'denied' };    // 领域语言
    // ...
  }
}
// interface 层(参见 interface-build.md)将 CancelResult 映射到 HTTP:
//   not_found -> 404, denied -> 403, conflict -> 409, ok -> 200
```

这种分离使相同的领域逻辑可以服务 HTTP、CLI、webhook 和测试调用方,而无需重复。

## 基于锁定基线重构

在后端重构之前,列出必须保持不变的行为。在聚焦变更之前和之后运行现有测试。如果没有合适的测试存在,先创建一个最小的 characterization test。

重构中需要保持的行为:

- 公共入口路径(路由、CLI 命令、event handler)
- 字段和响应结构(公共 API contract)
- 认证和 authorization 行为
- 状态转换结果
- schema 语义
- provider 请求和错误行为
- job 触发行为
- 可观测性和恢复信号

如果重构使得无法保持其中之一,那是 contract 变更,不是重构。带着证据返回 Node02。

重构期间发现的不相关技术债务应该被命名但保持不动,除非它阻塞切片。不要将一个聚焦变更变成全 repository 的清理。
