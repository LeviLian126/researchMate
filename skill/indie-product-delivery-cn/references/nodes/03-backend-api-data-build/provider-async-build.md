# Provider、Async 和对账构建

使用本指南处理 provider adapter、queue、job、webhook、cron task、callback 和对账。如果尚未框架化切片,请先阅读 `slice-framing.md`。

Node02 定义外部边界 contract(trigger、adapter owner、retry、recovery、cost、evolution)。本文件实现机制。如果远程行为、恢复结果、price/quota 策略或 provider 替换决策未知,返回 Node02。不要在 retry 循环中编码猜测。

## 章节

- [恢复外部边界](#恢复外部边界)
- [Adapter 优先构建](#adapter-优先构建)
- [Async 生命周期](#async-生命周期)
- [Callback 和 Idempotency](#callback-和-idempotency)
- [特殊风险规则](#特殊风险规则)

## 恢复外部边界

在触碰 provider SDK、queue、callback 或 job 之前,识别已批准的能力、本地所有者、规范化的输入/输出、secret 边界、provider 身份、timeout、cost/quota、retry/idempotency、用户可见状态、恢复所有者和证据义务。

一个具体的 adapter 在代码中展示这些决策:

```typescript
// port(interface)-- 定义 domain 需要什么,不是 provider 如何工作
interface BillingAdapter {
  scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult>;
  requestRefund(subscriptionId: string, amount: number): Promise<BillingResult>;
}

type BillingResult =
  | { ok: true; providerRef: string }
  | { ok: false; retryable: boolean; code: string };

// production adapter -- 拥有 provider 协议、凭证、error mapping
class StripeBillingAdapter implements BillingAdapter {
  constructor(private client: StripeClient, private timeout: number = 5000) {}

  async scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult> {
    try {
      const result = await this.client.subscriptions.update(subscriptionId, {
        cancel_at_period_end: true,
      }, { timeout: this.timeout });

      return { ok: true, providerRef: result.id };
    } catch (e) {
      if (e instanceof StripeTimeoutError) {
        return { ok: false, retryable: true, code: 'timeout' };
      }
      if (e instanceof StripeRateLimitError) {
        return { ok: false, retryable: true, code: 'rate_limited' };
      }
      return { ok: false, retryable: false, code: 'provider_error' };
    }
  }

  async requestRefund(subscriptionId: string, amount: number): Promise<BillingResult> {
    // ... 类似模式
  }
}

// test double -- 满足相同 port,无网络,确定性
class FakeBillingAdapter implements BillingAdapter {
  scheduledCancellations: string[] = [];

  async scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult> {
    this.scheduledCancellations.push(subscriptionId);
    return { ok: true, providerRef: `fake_${subscriptionId}` };
  }

  async requestRefund(subscriptionId: string, amount: number): Promise<BillingResult> {
    return { ok: true, providerRef: `fake_refund_${subscriptionId}` };
  }
}
```

领域 service 依赖 `BillingAdapter`,不是 `StripeBillingAdapter`。测试注入 `FakeBillingAdapter`。production 注入 `StripeBillingAdapter`。两个 adapter 意味着 seam 是真实的。

## Adapter 优先构建

仅在 provider 协议、凭证、失败映射或替换边界确实需要保护时,才扩展现有 adapter 或创建一个。Service 接收规范化的值和领域结果,不是 SDK 对象或原始 callback payload。

### 好的做法:adapter 规范化,domain 接收干净类型

```typescript
// adapter 将 SDK 响应转换为 domain 结果
class StripeBillingAdapter implements BillingAdapter {
  async scheduleCancellation(id: string, date: Date): Promise<BillingResult> {
    const stripeResult = await this.client.subscriptions.update(id, { cancel_at_period_end: true });
    return { ok: true, providerRef: stripeResult.id };   // 规范化,无 SDK 类型泄漏
  }
}

// domain service 使用 port,从不看到 Stripe 类型
class SubscriptionService {
  constructor(private billing: BillingAdapter) {}

  async cancel(id: string, userId: string): Promise<CancelResult> {
    // ... 状态转换 ...
    const billingResult = await this.billing.scheduleCancellation(id, periodEndDate);
    if (!billingResult.ok && !billingResult.retryable) {
      return { kind: 'provider_error', retryable: false, correlationId: id };
    }
    return { kind: 'ok', cancelsAt: periodEndDate };
  }
}
```

### 错误的做法:SDK 对象泄漏到 domain

```typescript
// domain 直接调用 Stripe SDK -- 无 adapter
class SubscriptionService {
  async cancel(id: string, userId: string): Promise<CancelResult> {
    const stripe = new Stripe(process.env.STRIPE_KEY);   // secret 在领域层
    const result = await stripe.subscriptions.update(id, { cancel_at_period_end: true });
    // domain 现在知道 Stripe 类型、响应结构和错误码
    // 测试需要 mock Stripe SDK 或调用真实 API
    // 切换 provider 意味着重写 domain service
  }
}
```

### Secret 在边缘

将凭证排除在源码、URL、响应 body 和日志之外。adapter 从环境变量读取配置;domain service 从不看到 secret。

```typescript
// adapter 构造函数读取配置
class StripeBillingAdapter implements BillingAdapter {
  constructor(
    private client: StripeClient,   // 已用 key 配置
    private timeout: number = 5000,
  ) {}
}

// composition root 处的工厂 -- 唯一读取 secret 的地方
function createBillingAdapter(): BillingAdapter {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error('STRIPE_SECRET_KEY not configured');
  return new StripeBillingAdapter(new StripeClient(key));
}
```

不要因为可以想象第二个 provider 就创建抽象 provider factory。创建保护实际外部边界的最小 adapter。

## Async 生命周期

对于 job、queue、webhook、cron、realtime 工作和 provider callback,保留此生命周期。每个阶段有具体的实现职责:

```
trigger -> durable acceptance -> execution -> callback/status
  -> visible completion/failure -> reconciliation -> manual recovery
```

### Trigger

在接受工作之前验证资格、身份、scope 和重复 key。

```typescript
async function enqueueEmailJob(payload: EmailPayload, requestId: string) {
  // 按 request ID 去重
  const existing = await db.query(
    'SELECT id FROM email_jobs WHERE request_id = $1', [requestId]
  );
  if (existing.rows.length > 0) return existing.rows[0].id;

  const result = await db.query(
    'INSERT INTO email_jobs (request_id, payload, status, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id',
    [requestId, JSON.stringify(payload), 'pending']
  );
  await queue.publish('email', { jobId: result.rows[0].id });
  return result.rows[0].id;
}
```

### 持久接受

当 contract 要求时,在工作开始之前存储 pending 或 intent 状态。如果 app 在 trigger 之后崩溃,job 记录保留且可以重试。

### 执行

使用规范化输入、timeout、有界 retry 和安全的速率/成本控制。

```typescript
async function processEmailJob(jobId: string) {
  const job = await db.query('SELECT * FROM email_jobs WHERE id = $1 FOR UPDATE', [jobId]);
  if (job.rows[0].status !== 'pending') return;   // 已处理或正在处理

  await db.query('UPDATE email_jobs SET status = $1, started_at = NOW() WHERE id = $2', ['processing', jobId]);

  try {
    await emailProvider.send(JSON.parse(job.rows[0].payload));
    await db.query('UPDATE email_jobs SET status = $1, completed_at = NOW() WHERE id = $2', ['completed', jobId]);
  } catch (e) {
    await db.query(
      'UPDATE email_jobs SET status = $1, error = $2, attempts = attempts + 1 WHERE id = $3',
      ['failed', e.message, jobId]
    );
    if (isRetryable(e) && job.rows[0].attempts < 3) {
      await queue.publish('email', { jobId }, { delay: backoff(job.rows[0].attempts) });
    }
  }
}
```

### Callback

验证签名/来源、安全关联、容忍重放和乱序送达。参见下方的[Callback 和 Idempotency](#callback-和-idempotency)。

### 状态

只持久化有效的状态转换。暴露已批准的用户可见结果。

### Retry

命名 retry 所有者、尝试限制、backoff、终止条件和重放安全。除非 provider 和本地持久 key 使重放安全,否则不要重试非 idempotent 的远程操作。

### 对账

比较本地和远程权威。记录不匹配。调用设计的修复路径。不要在实现期间发明对账逻辑——如果不匹配处理未被 Node02 定义,带着证据返回。

### 手动恢复

暴露最小的运维证据,没有隐藏的绕过路径。运维人员应该能看到当前状态、最后一次尝试和安全的下一步操作——没有跳过 contract 的秘密后门。

## Callback 和 Idempotency

一个无法验证、关联、去重或映射到允许状态的 callback 必须安全失败。除非 provider 和本地持久 key 使重放安全,否则不要重试非 idempotent 的远程操作。

### Callback 验证

```typescript
async function handleStripeWebhook(req: Request, res: Response) {
  // 1. 验证签名 -- 拒绝未验证的 callback
  const sig = req.headers['stripe-signature'];
  let event: StripeEvent;
  try {
    event = stripe.webhooks.constructEvent(req.rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (e) {
    return res.status(400).json({ error: 'invalid_signature' });
  }

  // 2. 关联到本地记录
  const localPayment = await paymentRepo.findByExternalId(event.data.object.id);
  if (!localPayment) {
    return res.status(404).json({ error: 'unmatched_event' });
  }

  // 3. 去重 -- 检查此 event 是否已处理
  const alreadyProcessed = await webhookEventRepo.exists(event.id);
  if (alreadyProcessed) {
    return res.status(200).json({ received: true });   // idempotent 确认
  }

  // 4. 记录 event
  await webhookEventRepo.insert({ eventId: event.id, type: event.type, status: 'processing' });

  // 5. 应用前检查当前状态(参见 persistence-build.md)
  if (localPayment.status === 'completed') {
    await webhookEventRepo.update(event.id, { status: 'completed', note: 'already_completed' });
    return res.status(200).json({ received: true });
  }

  // 6. 应用变更
  await db.transaction(async (tx) => {
    await tx.payments.update(localPayment.id, { status: 'completed', completedAt: new Date() });
    await tx.webhookEvents.update(event.id, { status: 'completed' });
  });

  res.status(200).json({ received: true });
}
```

关键点:签名验证发生在任何可能泄漏信息的数据库查找之前。Event ID 去重防止重复处理。当前状态检查防止重新应用已完成的支付。

### 重放处理

当同一个 callback 到达两次时(Stripe 重试 webhook),第二次到达必须是安全的。Event ID 去重(步骤 3)和当前状态检查(步骤 5)的组合处理了这种情况。callback 两次都返回 200,但支付只更新一次。

## 特殊风险规则

这些接口有额外的实现约束,因为它们的失败模式是不可逆的或影响信任的。

### 支付

- 在服务端查找 plan 和 price;永远不信任客户端提供的 price 或 amount
- 尽可能使用托管流程(Stripe Checkout、PayPal)-- 不要处理原始卡数据
- 在处理支付 event 之前验证 webhook 签名
- 按 provider event ID 去重 event
- 在标记 completed 之前验证 amount、recipient 和 provider 状态与本地记录匹配
- Entitlement 状态必须足够确定才能授予访问权限

```typescript
// 支付验证:amount 必须与本地记录匹配
if (callback.amount !== localPayment.amount) {
  throw new ConflictError('amount_mismatch');
  // 不标记 completed -- 支付金额不匹配
}
```

### 上传

- 在存储之前验证文件类型、大小、内容和所有权
- 在服务端生成存储 key;不信任客户端提供的文件名或路径
- 保留可见性和生命周期 contract(谁可以访问,保留多久)

```typescript
async function handleUpload(req: AuthedRequest, res: Response) {
  const userId = req.auth.userId;
  const file = req.file;
  if (!ALLOWED_MIME_TYPES.has(file.mimetype)) throw new ValidationError('invalid_file_type');
  if (file.size > MAX_UPLOAD_SIZE) throw new ValidationError('file_too_large');
  const key = `uploads/${userId}/${uuid()}-${sanitizedFilename}`;   // 服务端生成的 key
  await storage.put(key, file.buffer, { contentType: file.mimetype });
  await fileRepo.insert({ key, userId, size: file.size, expiresAt: expiryDate });
}
```

### Webhook

- 在处理之前验证签名、时间戳和来源
- 按 event 身份去重
- 避免调用方控制的 resource 查找 -- 不要在未验证关联的情况下使用 webhook payload 字段查找 resource

### 定时 Job

- 明确调度资格(运行时必须满足什么条件)
- 处理重叠:防止同一个 job 的两个实例同时运行(使用 lock 或去重 key)
- 设置显式 timeout
- 处理过期运行:如果 job 已调度但状态自调度以来已改变,执行前检查当前状态

### Realtime

- 认证连接
- 将 subscription scope 限制在已认证用户的 tenant/owner
- 限制 fanout:限制接收广播的连接数量
- 按 Node02 的设计保留有序和重复语义

这些是实现保障措施。将 secret 和 API key 排除在代码和日志之外,在将金钱相关效果视为成功之前进行验证。