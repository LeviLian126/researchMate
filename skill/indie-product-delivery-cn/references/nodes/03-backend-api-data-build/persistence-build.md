# 持久化构建

使用本指南处理 repository 和数据访问机制:安全查询、transaction、并发、schema 演进和持久 invariant。如果尚未框架化切片,请先阅读 `slice-framing.md`。

Node02 定义数据生命周期、完整性规则和演进分类。本文件实现机制。如果查询结构、index、存储策略或一致性模型未决定,带着具体问题返回 Node02。

## 章节

- [恢复持久 Contract](#恢复持久-contract)
- [构建安全查询](#构建安全查询)
- [反模式:N+1 和过度获取](#反模式n1-和过度获取)
- [使 Invariant 持久化](#使-invariant-持久化)
- [反模式:缺失 Transaction 边界](#反模式缺失-transaction-边界)
- [Schema 和数据演进](#schema-和数据演进)

## 恢复持久 Contract

Node02 定义数据生命周期和完整性规则。在编写 repository 代码之前,对照当前 contract 和 repository 证据确认这五个事实:

1. **所有者**:哪个 repository 或存储边界已经拥有这些数据?使用已建立的边界;不要创建平行的数据访问路径。
2. **身份**:主键、外部 ID、唯一性规则和重复行为是什么?是否有 idempotency key?
3. **Scope**:每个查询和变更中必须出现什么 tenant、owner 或 account 过滤?
4. **可见性**:调用方被允许看到哪些字段?只返回那些字段。
5. **生命周期**:哪些状态、转换、保留和删除行为已批准?

不要因为当前调用方稍后过滤就让 repository 返回无限制的行。数据 scope 和字段可见性必须在未来的调用方中保持有效。

## 构建安全查询

将查询机制与业务策略分离,但确保 repository 接收可信的 scope 和已授权的过滤集。安全地绑定值。永远不要将原始输入插值到查询字符串中。

### Owner/tenant 绕过

```typescript
// 安全:scope 在查询中强制执行
const subs = await db.query(
  'SELECT id, state, period_end_date FROM subscriptions WHERE user_id = $1 AND tenant_id = $2',
  [userId, tenantId]
);

// 不安全:无 scope 过滤,任何调用方都可以读取任何订阅
const subs = await db.query(
  'SELECT * FROM subscriptions WHERE id = $1',
  [req.params.id]
);
```

### 大批量披露

```typescript
// 安全:只选择允许的字段,通过响应 allowlist 映射
const rows = await db.query(
  'SELECT id, state, period_end_date FROM subscriptions WHERE user_id = $1 LIMIT $2',
  [userId, limit]
);
return rows.map(toSubscriptionSummary);   // 丢弃内部列

// 不安全:SELECT * 暴露内部列(created_by、deleted_at、provider_internal_id)
const rows = await db.query('SELECT * FROM subscriptions WHERE user_id = $1', [userId]);
return rows;   // 原始实体泄漏给调用方
```

### 无界集合

```typescript
// 安全:带最大 limit 的分页
const limit = Math.min(requestedLimit ?? 20, 100);   // 上限 100
const rows = await db.query(
  'SELECT id, state FROM subscriptions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3',
  [userId, limit, (page - 1) * limit]
);

// 不安全:无 limit,返回整个表
const rows = await db.query('SELECT * FROM subscriptions WHERE user_id = $1', [userId]);
```

### 不安全的排序/过滤

```typescript
// 安全:将公共 token 映射到已知列,使用参数化查询
const SORT_COLUMNS = { created: 'created_at', name: 'name', updated: 'updated_at' };
const col = SORT_COLUMNS[sortToken] ?? 'created_at';
const rows = await db.query(
  `SELECT id, name FROM items WHERE tenant_id = $1 ORDER BY ${col} DESC LIMIT $2`,
  [tenantId, limit]
);   // col 来自固定 allowlist,不是用户输入

// 不安全:插值原始用户输入
const rows = await db.query(
  `SELECT * FROM items WHERE tenant_id = $1 ORDER BY ${req.query.sort} DESC`,
  [tenantId]
);   // 通过 sort 参数进行 SQL 注入
```

### 循环中查询

```typescript
// 安全:批量获取
const orders = await orderRepo.findManyByUserIds(userIds);   // 一次查询
// SELECT * FROM orders WHERE user_id = ANY($1)

// 不安全:N+1 -- 每个用户一次查询
for (const user of users) {
  user.orders = await orderRepo.findByUserId(user.id);   // N 次查询
}
```

## 反模式:N+1 和过度获取

LLM 在构建关联数据时经常写出 N+1 查询。查询数量随集合大小线性增长,随着用户和数据增长,将快速页面变成慢页面。

```typescript
// N+1:先获取用户,然后每个用户一次查询获取其订单
const users = await userRepo.findMany({ tenantId });
for (const user of users) {
  user.orders = await orderRepo.findByUserId(user.id);   // 1 + N 次查询
}

// 批量:一次查询获取用户,一次查询获取所有订单
const users = await userRepo.findMany({ tenantId });
const userIds = users.map(u => u.id);
const allOrders = await orderRepo.findManyByUserIds(userIds);   // 总共 2 次查询
const ordersByUser = groupBy(allOrders, o => o.userId);
for (const user of users) {
  user.orders = ordersByUser[user.id] ?? [];
}
```

批量版本无论用户数量多少都是 2 次查询。N+1 版本是 N+1 次查询。100 个用户时,就是 2 次查询 vs 101 次。

过度获取是读取侧的等价物:只需要 3 列时选择所有列,或调用方只需要摘要时返回完整实体。两者都浪费带宽并增加意外数据泄漏的面。

## 使 Invariant 持久化

使用数据库或存储机制使批准的 invariant 成为现实。应用内存中的预检查不是持久的重复防护或并发控制。

### 多写 invariant:带 rollback 边界的 transaction

```typescript
async function transferCredits(fromId: string, toId: string, amount: number) {
  return await db.transaction(async (tx) => {
    const from = await tx.query('SELECT credits FROM accounts WHERE id = $1 FOR UPDATE', [fromId]);
    if (from.rows[0].credits < amount) throw new ConflictError('insufficient_credits');

    await tx.query('UPDATE accounts SET credits = credits - $1 WHERE id = $2', [amount, fromId]);
    await tx.query('UPDATE accounts SET credits = credits + $1 WHERE id = $2', [amount, toId]);
    await tx.query(
      'INSERT INTO transfers (from_id, to_id, amount, created_at) VALUES ($1, $2, $3, NOW())',
      [fromId, toId, amount]
    );
    // 如果任何语句失败,整个 transaction 回滚
    // 没有部分状态:credits 不会只扣除不增加
  });
}
```

### 重复请求:唯一 key 或 idempotency 记录

```typescript
async function cancelSubscription(id: string, requestId: string) {
  return await db.transaction(async (tx) => {
    // 先插入 idempotency 记录;如果 requestId 已存在,返回之前的结果
    try {
      await tx.query(
        'INSERT INTO idempotency_keys (key, entity_type, entity_id) VALUES ($1, $2, $3)',
        [requestId, 'subscription_cancel', id]
      );
    } catch (e) {
      if (e.code === '23505') {   // 唯一约束冲突
        return await getIdempotentResult(tx, requestId);
      }
      throw e;
    }

    // 继续实际的取消操作
    const result = await doCancel(tx, id);
    await saveIdempotentResult(tx, requestId, result);
    return result;
  });
}
```

### 过期更新:optimistic 并发控制

```typescript
// 好的做法:条件更新检查 version,过期则失败
const result = await db.query(
  'UPDATE subscriptions SET state = $1, version = version + 1 WHERE id = $2 AND version = $3',
  ['cancelling', id, currentVersion]
);
if (result.rowCount === 0) {
  throw new ConflictError('stale_update');   // 其他人修改了它
}

// 错误的做法:盲覆盖,丢失并发变更
await db.query('UPDATE subscriptions SET state = $1 WHERE id = $2', ['cancelling', id]);
```

### Job/webhook 状态:带去重的持久转换

```typescript
async function handleWebhookEvent(event: WebhookEvent) {
  return await db.transaction(async (tx) => {
    // 按 event ID 去重
    const existing = await tx.query(
      'SELECT status FROM webhook_events WHERE event_id = $1', [event.id]
    );
    if (existing.rows.length > 0) {
      return { status: existing.rows[0].status };   // 已处理
    }

    // 以 pending 状态记录 event
    await tx.query(
      'INSERT INTO webhook_events (event_id, type, status, received_at) VALUES ($1, $2, $3, NOW())',
      [event.id, event.type, 'processing']
    );

    // 处理 event...
    await tx.query(
      'UPDATE webhook_events SET status = $1, processed_at = NOW() WHERE event_id = $2',
      ['completed', event.id]
    );
    return { status: 'completed' };
  });
}
```

## 反模式:缺失 Transaction 边界

LLM 经常在不使用 transaction 的情况下编写多步操作,如果某一步失败,系统会处于不一致状态。

```typescript
// 错误的做法:无 transaction -- 如果邮件入队失败,订阅处于半取消状态
async function cancel(id: string, userId: string) {
  const sub = await repo.findById(id);
  sub.state = 'cancelling';
  await repo.save(sub);                        // 步骤 1:状态更新
  await emailQueue.enqueue({ ... });            // 步骤 2:邮件入队(可能失败)
  await billingAdapter.scheduleStop(id);        // 步骤 3:计费停止(可能失败)
  // 如果步骤 2 或 3 失败:状态是 'cancelling' 但没发邮件,没停止计费
}

// 好的做法:transaction 包裹原子部分;async 工作在 transaction 内入队
async function cancel(id: string, userId: string) {
  return await db.transaction(async (tx) => {
    const sub = await tx.subscriptions.findById(id);
    // ... 检查 ...
    sub.state = 'cancelling';
    sub.cancelsAt = sub.periodEndDate;
    await tx.subscriptions.save(sub, sub.version);    // 与 idempotency 记录原子
    await tx.idempotency.mark(requestId, 'cancel', id);
    await tx.outbox.enqueue({ type: 'cancel_email', payload: { ... } });
    // 全部成功或全部回滚
    // outbox 模式确保邮件在 commit 后发送,app 崩溃时不会丢失
  });
}
```

### Callback 到达两次:应用前检查当前状态

当 webhook 或 callback 到达时,不要盲目应用它。先检查当前持久状态:

```typescript
async function handlePaymentCallback(callback: PaymentCallback) {
  return await db.transaction(async (tx) => {
    const payment = await tx.payments.findByExternalId(callback.payment_id);
    if (!payment) throw new NotFoundError('payment');

    // 已处理?返回当前状态
    if (payment.status === 'completed') {
      return { status: 'completed' };   // idempotent:不重新处理
    }

    // 验证 callback 属于此支付且有效
    if (payment.amount !== callback.amount) {
      throw new ConflictError('amount_mismatch');   // 不处理错误金额
    }

    // 转换为 completed
    await tx.payments.update(payment.id, {
      status: 'completed',
      completed_at: new Date(),
      version: payment.version + 1,
    });

    return { status: 'completed' };
  });
}
```

## Schema 和数据演进

Node02 分类演进(additive、transforming、destructive、provider-state)。本文件实现机制。遵循 Node02 的演进记录;不要用通用 migration 脚本替代它。

典型的 additive migration:添加一个 nullable 列,分批 backfill 现有行,然后添加约束。每一步可独立安全运行且可恢复。

```sql
-- 步骤 1:添加 nullable 列(additive,无停机)
ALTER TABLE subscriptions ADD COLUMN cancellation_reason TEXT;

-- 步骤 2:分批 backfill(可恢复,idempotent)
-- 每批足够小,不会长时间锁表
-- 跟踪进度,使失败的批次可以恢复
UPDATE subscriptions
SET cancellation_reason = 'unknown'
WHERE id IN (
  SELECT id FROM subscriptions
  WHERE cancellation_reason IS NULL
  LIMIT 1000
);
-- 重复直到没有 NULL 行

-- 步骤 3:添加约束(仅在所有行都有值之后)
ALTER TABLE subscriptions ALTER COLUMN cancellation_reason SET NOT NULL;
```

对于每个演进步骤,说明:
- **preflight**:现有行、消费者、feature/config 状态和所需 app 权限
- **compatibility**:新/旧读/写行为和混合版本假设
- **backfill**:批次身份/顺序、有界工作、可恢复性、idempotency、进度证据
- **validation**:dry-run、样本/计数检查和预期成功条件
- **repair**:安全重运行、forward-fix、手动所有者和保留证据
- **removal**:允许删除旧字段的条件;Node06 执行它

对于新的必填字段,在添加强制约束之前决定现有行如何达到有效值(上面的步骤 1-3)。对于重命名或类型转换,保留批准的兼容性窗口。对于大型或未知数据,避免单次无界写入,并记录具体的锁/停机/吞吐量风险供发布 workflow 使用。

Node03 可以添加 migration、安全 preflight 检查、dry-run 模式、backfill 代码、repair 命令、fixture 和本地验证。将 production migration 执行、destructive 清理和远程对账保留在 Node06 的发布 workflow 中。