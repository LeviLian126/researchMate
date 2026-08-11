# 接口构建

使用本指南实现 HTTP、CLI、event 或 webhook 入口边界:输入 validation、身份强制执行、稳定的结果和错误映射。如果尚未框架化切片,请先阅读 `slice-framing.md`。

Node02 定义 interface contract(字段、auth、错误、演进)。本文件实现它。不要因为实现捷径方便而改变状态码、公共字段名、错误结构、分页行为、认证要求、时序或 idempotency 语义——这些是需要 Node02 的 contract 变更。

## 章节

- [还原 Interface Contract](#还原-interface-contract)
- [在不可信边界处规范化和验证](#在不可信边界处规范化和验证)
- [在服务端强制执行身份和访问](#在服务端强制执行身份和访问)
- [映射稳定的结果和失败](#映射稳定的结果和失败)
- [反模式:静默错误吞没](#反模式静默错误吞没)
- [面向查询的接口行为](#面向查询的接口行为)

## 还原 Interface Contract

对于每个变更的入口,捕获 contract 字段并在 handler 中实现。使用现有的路由或 action 模式,除非 Node02 明确批准了新接口。

一个完整的 handler 在代码中展示每个 contract 字段:

```typescript
// PATCH /subscriptions/:id/cancel
// Contract:
//   caller:     authenticated user (auth middleware sets req.auth)
//   input:      path param :id, optional body { reason?: string }
//   identity:   session token verified by auth middleware -> req.auth.userId
//   scope:      user must own the subscription (checked in domain layer)
//   success:    200 { status: 'cancelling', cancelsAt: string }
//   errors:     400 validation, 401 unauthenticated, 403 denied, 404 not_found,
//               409 conflict, 502 provider_error, 500 internal
//   compat:     additive (new endpoint, no existing consumers)
//   proof:      behavior test through SubscriptionService with in-process fake

async function cancelSubscription(req: AuthedRequest, res: Response) {
  // 1. 验证输入结构
  const id = req.params.id;
  if (!id || typeof id !== 'string') {
    return res.status(400).json({ error: 'invalid_id' });
  }
  const reason = req.body?.reason;
  if (reason !== undefined && typeof reason !== 'string') {
    return res.status(400).json({ error: 'invalid_reason' });
  }

  // 2. 可信身份(来自 middleware,不是 request body)
  const userId = req.auth.userId;

  // 3. 调用 domain(所有权在内部检查)
  const result = await subscriptionService.cancel(id, userId, { reason });

  // 4. 将 domain 结果映射为稳定的 HTTP 响应
  mapCancelResult(res, result);
}

function mapCancelResult(res: Response, result: CancelResult) {
  switch (result.kind) {
    case 'ok':
      res.status(200).json({ status: 'cancelling', cancelsAt: result.cancelsAt.toISOString() });
      break;
    case 'not_found':
      res.status(404).json({ error: 'not_found' });
      break;
    case 'denied':
      res.status(403).json({ error: 'denied' });
      break;
    case 'conflict':
      res.status(409).json({ error: 'conflict', current_state: result.currentState });
      break;
    case 'provider_error':
      res.status(502).json({
        error: 'provider_error',
        retryable: result.retryable,
        correlation_id: result.correlationId,
      });
      break;
  }
}
```

handler 不包含业务规则。它解析、验证结构、调用领域 use-case 并映射结果。

## 在不可信边界处规范化和验证

将 request body、query/path 值、cookie、header、CLI 参数、webhook payload、上传文件、模型输出和导入文件视为不可信,直到边界验证它们。validation 防止格式错误的意图;它不决定 actor 是否被允许。

### 结构验证

在值到达领域逻辑之前,验证类型、必填/可选字段、嵌套结构和大小。

```typescript
function parseCancelBody(body: unknown): { reason?: string } | { error: string } {
  if (body === undefined || body === null) return {};
  if (typeof body !== 'object') return { error: 'body_must_be_object' };
  const b = body as Record<string, unknown>;
  if (b.reason !== undefined && typeof b.reason !== 'string') {
    return { error: 'reason_must_be_string' };
  }
  if (typeof b.reason === 'string' && b.reason.length > 500) {
    return { error: 'reason_too_long' };
  }
  return { reason: b.reason };
}
```

### Allowlist:只接受客户端可设置的字段

按 contract 拒绝或忽略未知字段。永远不要将原始 request body 直接传递给领域方法或 repository。

```typescript
// 好的做法:显式 allowlist
const ALLOWED_FIELDS = ['reason'] as const;
function sanitizeCancelBody(body: Record<string, unknown>) {
  const picked: Record<string, unknown> = {};
  for (const key of ALLOWED_FIELDS) {
    if (key in body) picked[key] = body[key];
  }
  return picked;
}

// 错误的做法:展开整个 body,让调用方可以设置服务端拥有的字段
const subscription = { ...req.body, userId: req.auth.userId };
await repo.save(subscription);
// 调用方可以通过在 body 中包含 userId、price、state 或任何列来覆盖它们
```

### 服务端拥有的值:从可信状态派生

owner、tenant、role、price、quota、entitlement、provider ID、时间戳和受控状态必须从服务端可信状态派生,而不是从请求输入。

```typescript
// 好的做法:price 和 plan 来自服务端查找
const plan = await planRepo.findById(subscription.planId);
const amount = plan.price;   // 服务端,可信

// 错误的做法:price 来自 request body
const amount = req.body.price;   // 不可信,调用方可以设置任意价格
```

### 动态查询:allowlist 排序和过滤 token

当客户端控制排序或过滤表达式时,将公共 token 映射到已知列和操作符。永远不要将原始输入插值到查询字符串中。

```typescript
const SORT_COLUMNS: Record<string, string> = {
  created: 'created_at',
  updated: 'updated_at',
  name: 'name',
};

function resolveSort(sortParam: string | undefined): { column: string; dir: 'asc' | 'desc' } {
  if (!sortParam) return { column: 'created_at', dir: 'desc' };   // 安全默认值
  const [token, dir] = sortParam.split(':');
  const column = SORT_COLUMNS[token];
  if (!column) throw new ValidationError('invalid_sort_field');
  if (dir !== 'asc' && dir !== 'desc') throw new ValidationError('invalid_sort_dir');
  return { column, dir };
}
// 使用解析后的列进行参数化查询 -- 参见 persistence-build.md
```

### 规范化

只在 contract 允许且保留有意义的区别时进行 trim 或 canonicalize。不要静默规范化掉有意义的差异。

```typescript
// 安全:email 按约定是大小写不敏感的
const email = req.body.email.trim().toLowerCase();

// 不安全:trim 一个可能有前导零或重要空格的 code
const code = req.body.code.trim();   // '  007' 变成 '007' -- 可能破坏验证
```

## 在服务端强制执行身份和访问

在实际执行点实现 Node02 的信任链:

```
subject -> resource -> action -> scope -> enforcement -> safe failure -> evidence
```

在受保护访问之前进行认证。从可信身份和服务端查找解析 resource scope,然后在读取、变更、导出、provider action 或私有字段披露之前进行授权。UI guard、调用方提供的 owner ID 或隐藏路由不是执行点。

### Tenant-scoped 查询:安全 vs 不安全

```typescript
// 安全:tenant scope 来自已认证的 session,在查询中应用
async function listSubscriptions(userId: string, tenantId: string) {
  return await db.subscriptions.findMany({
    where: { userId, tenantId },   // scope 在数据查询中强制执行
    limit: 50,
  });
}

// 不安全:信任调用方提供的 tenant_id,无服务端验证
async function listSubscriptions(req: Request) {
  return await db.subscriptions.findMany({
    where: { tenant_id: req.query.tenant_id },   // 不可信,绕过 scope
  });
}
```

### 不存在 vs 被拒绝:保护隐私

当用户请求一个不属于他们的 resource 时,返回与 resource 不存在相同的响应。不要泄漏存在性。

```typescript
// 好的做法:404 同时用于"未找到"和"找到但不属于你"
case 'not_found':
case 'denied':
  res.status(404).json({ error: 'not_found' });   // 两者返回相同响应
  break;

// 错误的做法:403 暴露 resource 存在
case 'denied':
  res.status(403).json({ error: 'forbidden' });   // 调用方得知 resource 存在
  break;
```

例外:当 contract 明确要求 403 时(例如 admin 操作),遵循 contract。这是 Node02 的决策,不是实现默认值。

## 映射稳定的结果和失败

在一个已建立的地方将领域结果转换为当前公共表示。将传输格式化排除在领域 service 和 provider adapter 之外。

```typescript
// 中央 error mapper -- 整个模块的一个地方
function mapDomainError(res: Response, error: DomainError) {
  const MAPPINGS: Record<string, { status: number; body: (e: DomainError) => object }> = {
    validation:   { status: 400, body: e => ({ error: 'validation', field: e.field, message: e.message }) },
    unauthenticated: { status: 401, body: () => ({ error: 'unauthenticated' }) },
    denied:       { status: 403, body: () => ({ error: 'denied' }) },
    not_found:    { status: 404, body: () => ({ error: 'not_found' }) },
    conflict:     { status: 409, body: e => ({ error: 'conflict', current_state: e.currentState }) },
    provider_error: { status: 502, body: e => ({ error: 'provider_error', retryable: e.retryable, correlation_id: e.correlationId }) },
    internal:     { status: 500, body: () => ({ error: 'internal' }) },   // 不暴露 stack、SQL、内部信息
  };

  const mapping = MAPPINGS[error.kind] ?? MAPPINGS.internal;
  res.status(mapping.status).json(mapping.body(error));
}
```

每个错误响应传达发生了什么、为什么、以及如何修复或安全恢复——不暴露内部细节。internal 错误情况返回通用消息;真正的诊断信息进入日志,而不是给调用方。

## 反模式:静默错误吞没

LLM 经常将不同的失败模式折叠为单一的 catch-all,对调用方和调试隐藏实际问题。

```typescript
// 错误的做法:吞没一切,调用方对所有失败类型得到 500
async function cancelSubscription(req: Request, res: Response) {
  try {
    const result = await subscriptionService.cancel(req.params.id, req.auth.userId);
    res.status(200).json(result);
  } catch (e) {
    res.status(500).json({ error: 'something went wrong' });
    // validation 错误、auth 失败、conflict、provider timeout -- 全部变成 500
    // 调用方无法区分"输入错误"和"服务器坏了"
    // 日志可能不会捕获真正的错误类型
  }
}

// 更糟:返回 null,调用方不知道发生了什么
async function cancelSubscription(req: Request, res: Response) {
  try {
    const result = await subscriptionService.cancel(req.params.id, req.auth.userId);
    res.status(200).json(result);
  } catch (e) {
    res.status(200).json({ error: null });   // 看起来像成功,隐藏了失败
  }
}
```

修复:领域方法返回类型化结果(对于预期结果不 throw),handler 通过中央 error mapper 映射每个变体。意外 exception 仍然进入 500 handler,但它们是例外,不是默认值。

```typescript
// 好的做法:domain 返回类型化结果,handler 映射每个变体
const result = await subscriptionService.cancel(id, userId, { reason });
mapCancelResult(res, result);   // 处理 ok、not_found、denied、conflict、provider_error
```

## 面向查询的接口行为

当公共入口读取集合时,实现商定的过滤、排序、分页、权限过滤、空状态和速率/成本边界。

- 在数据查询中应用权限过滤,而不是在获取所有行之后。参见上面的 tenant-scoped 查询示例。
- 不要承诺 persistence 层无法安全支持的 total count、cursor、page size 或过滤能力。
- 检查无界响应、用户控制的排序表达式、逐项查询序列化和嵌套私有字段。
- 将存储、index 或一致性决策路由回 Node02;在 `persistence-build.md` 中实现选定的查询结构。

```typescript
// 好的做法:有界、scoped、参数化
async function listOrders(req: AuthedRequest, res: Response) {
  const userId = req.auth.userId;
  const page = clamp(parseInt(req.query.page) || 1, 1, 1000);
  const limit = clamp(parseInt(req.query.limit) || 20, 1, 100);
  const sort = resolveSort(req.query.sort);   // allowlist 映射

  const orders = await orderRepo.findMany({ userId, page, limit, sort });
  res.status(200).json({
    items: orders.map(mapOrderSummary),
    page,
    limit,
    has_more: orders.length === limit,
  });
}
```

`has_more` 是安全信号。除非 contract 要求且 persistence 层能高效计算,否则不返回 `total_count`。
