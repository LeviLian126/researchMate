# 验证、调试和可观测性

使用本指南验证已实现的后端切片、从真实边界调试失败、添加相称的可观测性,并在不声称发布就绪的情况下准备质量证据。

## 章节

- [拆分 Hermetic 和 Deployed 验证](#拆分-hermetic-和-deployed-验证)
- [验证交付的制品](#验证交付的制品)
- [风险分级测试](#风险分级测试)
- [从根因调试](#从根因调试)
- [添加安全可观测性](#添加安全可观测性)
- [在声称完成之前验证](#在声称完成之前验证)
- [状态报告](#状态报告)

## 拆分 Hermetic 和 Deployed 验证

从 Node02 contract 和实现主干开始。对于每个变更的行为,选择能展示实际边界的最小验证。优先使用现有的测试框架、fixture、helper 和命令。

当测试通过有意义的边界执行生产行为时,它是有用的。不要测试 mock、私有实现琐事或 test-only 生产 seam 而非 contract。手动安全检查仅在自动化缺失或验证需要真实边界时可接受;说明其限制。

### Hermetic 本地验证:通过真实所有者和进程内 fake 的单元测试

```typescript
describe('SubscriptionService.cancel', () => {
  let service: SubscriptionService;
  let fakeRepo: FakeSubscriptionRepo;
  let fakeEmail: FakeEmailQueue;
  let fakeBilling: FakeBillingAdapter;

  beforeEach(() => {
    fakeRepo = new FakeSubscriptionRepo([
      { id: 'sub_1', userId: 'user_1', state: 'active', periodEndDate: new Date('2025-12-31') },
    ]);
    fakeEmail = new FakeEmailQueue();
    fakeBilling = new FakeBillingAdapter();
    service = new SubscriptionService(fakeRepo, fakeEmail, fakeBilling);
  });

  it('cancels an active subscription', async () => {
    const result = await service.cancel('sub_1', 'user_1');

    expect(result.kind).toBe('ok');
    expect(result.cancelsAt.toISOString()).toBe('2025-12-31T00:00:00.000Z');
    expect(fakeRepo.saved.state).toBe('cancelling');
    expect(fakeEmail.enqueued).toHaveLength(1);
    expect(fakeBilling.scheduledCancellations).toContain('sub_1');
  });

  it('rejects cancel for another user subscription', async () => {
    const result = await service.cancel('sub_1', 'user_2');
    expect(result.kind).toBe('denied');
    expect(fakeRepo.saved).toBeNull();   // 无状态变更
  });

  it('rejects cancel for already-cancelling subscription (idempotent)', async () => {
    fakeRepo.subscriptions[0].state = 'cancelling';
    const result = await service.cancel('sub_1', 'user_1');
    expect(result.kind).toBe('ok');         // 返回当前状态
    expect(fakeEmail.enqueued).toHaveLength(0);   // 无重复邮件
  });
});
```

此测试通过公共接口执行真实的 `SubscriptionService.cancel` 方法。Fake 替代外部依赖。无网络、无数据库服务器、无真实 provider。测试快速、确定性,并验证领域逻辑。

### Deployed 验证:通过真实边界的集成检查

当行为依赖真实数据库、provider 或 queue 时,针对已授权环境运行集成验证。命名已部署的 commit、环境、安全数据集、受保护的依赖、配额限制和清理期望。

```typescript
describe('Subscription cancellation integration', () => {
  // 这些测试需要 TEST_DATABASE_URL 和 STRIPE_TEST_KEY
  // 运行: npm run test:integration

  it('persists cancellation state in the real database', async () => {
    const res = await request(app)
      .patch('/subscriptions/sub_test_1/cancel')
      .set('Authorization', `Bearer ${testToken}`)
      .expect(200);

    expect(res.body.status).toBe('cancelling');

    // 验证持久状态
    const row = await db.query('SELECT state FROM subscriptions WHERE id = $1', ['sub_test_1']);
    expect(row.rows[0].state).toBe('cancelling');

    // 清理
    await db.query("UPDATE subscriptions SET state = 'active' WHERE id = $1", ['sub_test_1']);
  });
});
```

如果所需环境不可用,将集成声明保持为显式未验证,而不是发明一个等价环境。不要为了方便而弱化一个显式的 server-only 规则。

对于没有 server-only 集成策略的 repository,使用最小的已授权验证环境并保持本地基础设施相称。

## 验证交付的制品

对于每个可部署的 package、workspace member、executable、library、plugin 或 service 制品,在干净环境中复现 repository 锁定的 restore/install 和构建路径。然后通过其真实的语言/runtime 机制加载产出的制品。

- [ ] **依赖解析**:使用已提交的 lock 或不可变依赖模式。拒绝未记录的重新解析。(`npm ci` with `package-lock.json`, not `npm install`)
- [ ] **Package/build 元数据**:确认每个预期交付物被构建系统、workspace、module、manifest 或 package-discovery 规则包含。(`ls dist/` or `npm pack --dry-run`)
- [ ] **制品创建**:在适用时运行交付使用的相同 compile、bundle、package 或 publish-dry-run 路径。(`npm run build`, `tsc --noEmit`)
- [ ] **可加载性**:使用生产 runtime import、require、load、link 或执行每个可部署制品。(`node -e "require('./dist/index.js')"`)
- [ ] **Entrypoint**:调用声明的命令、module、handler 或 service 启动,足够远以检测缺失的代码或 runtime 依赖。(`npm start` with a health check)
- [ ] **平台/源选择**:保持架构、registry/index/source、CPU/GPU、native-library 和 toolchain 选择显式且可复现。

resolver 或 installer 成功只证明了它执行的依赖操作。它不证明拥有的源进入了制品、制品可以被加载、或其 entrypoint 可用。将本地开发者状态、全局安装的 package、先前构建输出和热缓存排除在此验证之外。

当完整验证对每次变更来说太昂贵时,定义一个更便宜的 pull-request 目标,并在发布或定时门禁处保留完整验证;将较便宜的结果标记为 partial。

## 风险分级测试

对于新增或变更的后端行为,首先用现有测试风格表达预期行为。运行它并确认它因预期的缺失行为而失败,然后实现使测试通过的最小变更。

### 什么是好的测试

测试通过公共接口验证行为,而非实现细节。代码可以完全改变;测试不应该。好的测试读起来像规范——"用户可以取消活跃订阅"准确告诉你存在什么能力——并且因为它不关心内部结构而在重构后存活。

### 产生无用测试的三个反模式

**实现耦合**:mock 内部协作者,测试私有方法,或通过侧信道验证。当你重构但行为未变时测试会断裂。

```typescript
// 错误的做法:mock 内部 repository 调用,测试 mock 而非行为
it('cancels subscription', () => {
  const mockRepo = sinon.mock(subscriptionService['repo']);   // 伸入私有字段
  mockRepo.expects('save').once();
  // ... 调用 cancel ...
  mockRepo.verify();
  // 如果你将 'save' 重命名为 'update',即使行为完全相同,此测试也会断裂
});

// 好的做法:通过公共接口测试可观察行为
it('cancels subscription', async () => {
  const result = await service.cancel('sub_1', 'user_1');
  expect(result.kind).toBe('ok');
  expect(result.cancelsAt).toBeDefined();
  // 验证结果,而非内部调用序列
});
```

**同义反复**:断言用与代码相同的方式重新计算预期值,所以它构造上通过且永远无法不一致。

```typescript
// 错误的做法:断言使用与实现相同的逻辑
it('calculates discount', () => {
  const cart = { items: [{ price: 10 }, { price: 20 }] };
  const result = calculateDiscount(cart);
  expect(result).toBe(cart.items.reduce((s, i) => s + i.price, 0) * 0.1);
  // 如果实现错了,测试以同样的方式错 -- 永远通过
});

// 好的做法:预期值来自独立来源(已知正确的字面量)
it('calculates discount', () => {
  const cart = { items: [{ price: 10 }, { price: 20 }] };
  const result = calculateDiscount(cart);
  expect(result).toBe(3);   // 30 的 10% = 3,手动验证
});
```

**水平切片**:先写所有测试,然后写所有实现。批量测试验证想象的行为——事物的形状而非面向用户的行为。改为在垂直切片中工作:一个测试,一个实现,重复。

### 在预先商定的 seam 处测试

seam 是你观察行为而不深入内部的公共边界。测试在 seam 处进行,绝不对内部。在编写测试之前,识别 seam 并确认它们。

对于后端切片,典型的 seam 是:
- domain service 公共方法(带 fake 的单元测试)
- HTTP handler endpoint(带真实 app 的集成测试)
- repository contract(带真实或测试数据库的集成测试)

不要在比必要更深的 seam 处测试。如果 domain service 有干净的 interface,在那里测试——不要也测试它调用的私有 helper。

### Red-Green 循环

- **Red**:编写一个描述你想要行为的失败测试。运行它。确认它因正确的原因失败(缺失行为,而非语法错误)。
- **Green**:编写使测试通过的最小实现。不要预期未来的测试或添加推测性功能。
- **重复**:每循环一个测试,一个实现。每个测试是响应上一个循环所教内容的追踪弹。

重构不是循环的一部分。它属于单独的审查步骤。

### 覆盖率指南

覆盖切片变更的核心业务行为。目标是对用户和数据重要的决策和状态转换有信心,而非一个聚合数字。

优先:领域规则、authorization 决策、状态转换、失败处理、idempotency、金钱/quota 逻辑和变更的分支。不要为了增加百分比而为琐碎的胶水代码、生成代码、样式或简单 pass-through 添加测试。

当现有 repository 有覆盖率基线时,有界变更不应降低它,且必须覆盖它变更的核心行为。仅在质量或测试加固任务期间提出更广泛的缺口。

## 从根因调试

当行为、测试、migration、provider 或性能证据失败时,不要堆叠修复。遵循这个六阶段 workflow。仅在明确说明理由时跳过阶段。

### 阶段 1:构建紧凑反馈循环

这是核心技能。其他一切都是机械的。如果你有一个针对 bug 的紧凑 pass/fail 信号——一个在此 bug 上变红的信号——你会找到原因。如果没有,盯着代码看再久也无济于事。

构建反馈循环。大致按此顺序尝试:

1. **失败测试**在任何能到达 bug 的 seam 处——单元、集成、e2e。
2. **curl / HTTP 脚本**对运行中的 dev server。
3. **CLI 调用**用 fixture 输入,将 stdout 与已知良好的 snapshot 对比。
4. **Headless 浏览器脚本**(Playwright / Puppeteer)——驱动 UI,对 DOM/console/network 断言。
5. **回放捕获的 trace**——保存真实的网络请求、payload 或 event 日志;通过代码路径隔离回放。
6. **临时 harness**——启动最小子集(一个 service,mock 依赖),用单次函数调用执行 bug 代码路径。
7. **Property / fuzz 循环**——如果 bug 是"有时输出错误",运行 1000 个随机输入寻找失败模式。
8. **二分 harness**——如果 bug 出现在两个已知状态之间(commit、dataset、version),自动化"在状态 X 启动,检查,重复",这样你可以 `git bisect run` 它。
9. **差异循环**——将相同输入通过旧版本 vs 新版本运行并 diff 输出。
10. **HITL bash 脚本**——最后手段。如果必须人工点击,用结构化脚本驱动他们,使循环仍然可控。

阶段 1 完成当你能命名一个命令——一个脚本路径、一个测试调用、一个 curl——你已至少运行过一次,且它是:

- [ ] **能变红**——它驱动实际的 bug 代码路径并断言用户的精确症状。不是"运行不出错"——它必须能捕获这个特定的 bug。
- [ ] **确定性**——每次运行相同结论(不稳定 bug:固定的高复现率)。
- [ ] **快速**——秒级,非分钟级。
- [ ] **Agent 可运行**——你可以无人值守地运行它。

如果你发现自己在该命令存在之前读代码构建理论,停止。没有能变红的命令,就没有阶段 2。

### 阶段 2:复现和最小化

运行循环。观察它变红。确认:

- [ ] 循环产生用户描述的失败模式——不是附近不同的失败。
- [ ] 失败在多次运行中可复现。
- [ ] 你已捕获精确症状(错误消息、错误输出、慢时序)。

然后最小化:将复现缩小到仍然变红的最小场景。逐个削减输入、调用方、配置、数据和步骤,每次削减后重新运行循环。只保留对失败有支撑作用的元素。完成当每个剩余元素都是支撑性的——移除任何一个都会使循环变绿。

### 阶段 3:假设

在测试任何假设之前生成 3-5 个排序的假设。单一假设生成会锚定在第一个看似合理的想法上。

每个假设必须是可证伪的:

> "如果 <X> 是原因,那么 <改变 Y> 会使 bug 消失 / <改变 Z> 会使它恶化。"

如果你无法陈述预测,假设只是一种感觉——丢弃或锐化它。

在测试之前向用户展示排序列表。他们通常有能立即重排序的领域知识。不要阻塞——如果用户不在,按你的排序继续。

### 阶段 4:插桩

每个探针必须映射到阶段 3 的特定预测。一次改变一个变量。

工具偏好:如果环境支持,使用 debugger 或 REPL 检查。一个断点胜过十条日志。如果需要日志,在区分假设的边界处使用针对性日志。永远不要"记录一切然后 grep"。

为每条调试日志标记唯一前缀:

```typescript
console.log('[DEBUG-a4f2] subscription state before cancel:', sub.state);
console.log('[DEBUG-a4f2] billing result:', billingResult);
console.log('[DEBUG-a4f2] email queue length:', fakeEmail.enqueued.length);
```

清理时变成单次 grep: `grep '[DEBUG-' src/`。未标记的日志存活;已标记的日志消亡。

对于性能回归,日志通常是错误的。改为:建立基线测量(时序 harness、`performance.now()`、profiler、query plan),然后二分。先测量,后修复。

### 阶段 5:修复和回归测试

在修复之前编写回归测试——但仅当存在正确的 seam。正确的 seam 是测试在调用点执行真实 bug 模式的 seam。如果唯一可用的 seam 太浅,那里的回归测试给出虚假信心。如果不存在正确的 seam,这本身就是发现——记录它,代码库架构阻止了 bug 被锁定。

如果存在正确的 seam:

1. 将最小化复现转换为该 seam 处的失败测试。
2. 观察它失败。
3. 应用修复。
4. 观察它通过。
5. 针对原始(未最小化)场景重新运行阶段 1 反馈循环。

### 阶段 6:清理和复盘

在声明完成之前必需:

- [ ] 原始复现不再复现(重新运行阶段 1 循环)。
- [ ] 回归测试通过(或 seam 缺失已记录)。
- [ ] 所有 `[DEBUG-...]` 插桩已移除(`grep '[DEBUG-' src/`)。
- [ ] 临时原型已删除或移至明确标记的调试位置。
- [ ] 最终证明正确的假设在 commit 或 PR 消息中陈述。

然后问:什么会阻止这个 bug?如果答案涉及架构变更(没有好的测试 seam、纠缠的调用方、隐藏耦合),标记给 Node02。

### 在困难调试期间保持假设台账

```
Observation:       cancel returns 500 for subscription sub_1 but 200 for sub_2
Proposed cause:    sub_1 has state 'past_due', transition rule missing
Discriminating
  check:           add 'past_due' to ALLOWED_TRANSITIONS, re-run test
Result:            test passes -- hypothesis confirmed
Next conclusion:   add 'past_due' -> 'cancelling' transition, add test for past_due cancel
```

运行能区分竞争原因的最廉价检查。仅在实际改变诊断的地方添加临时插桩,然后在交接前移除它或将其转换为有意的可观测性。

### 何时停止本地修补

当另一次尝试不会添加新证据时停止。如果证据揭示共享状态、跨模块耦合、不兼容的 runtime 假设或反复出现的新症状,带着证据返回 Node02,而不是继续推测性修复。

## 添加安全可观测性

只添加理解变更后生命周期在运行中所需的诊断。可观测性必须保留访问和隐私 contract;它不是记录 payload、secret、token、原始 provider 响应或私有标识符的理由。

### 安全结构化日志

```typescript
// 安全:correlation ID、outcome 类、retryability、耗时 -- 无 secret
logger.info('subscription_cancelled', {
  correlation_id: requestId,
  subscription_id: sub.id,        // 安全:内部 ID,非客户数据
  outcome: 'ok',
  previous_state: 'active',
  new_state: 'cancelling',
  retryable: false,
  elapsed_ms: Date.now() - startTime,
  billing_provider_ref: billingResult.providerRef,
});
```

### 不安全日志

```typescript
// 不安全:记录 request body、auth token、原始 provider 响应
logger.info('cancel_request', {
  body: req.body,                 // 可能包含 PII 或用户内容
  auth_token: req.headers.authorization,   // 凭证泄漏
  stripe_response: rawStripeResponse,      // 可能包含客户数据
  user_email: sub.email,                   // PII
});
```

当 request、job、callback、provider 或多写路径跨越边界时添加 correlation ID。当 domain、provider 或 migration 行为有有意义的失败类别时添加结构化 outcome。当 async、migration、对账或恢复变更持久状态时添加状态转换日志。当列表、搜索、导出、fanout 或查询路径可能增长时添加性能测量。

检查变更的数据路径是否有 N+1 查询循环、无界集合、缺失查询边界、过度 provider fanout、请求路径中的阻塞工作和重复序列化查找。修复明确的本地实现缺陷;将容量、存储、queue、缓存或架构选择返回 Node02。

## 在声称完成之前验证

完成声明需要来自当前工作树的新证据。识别证明每个声明的具体命令或安全观察,运行它,阅读其完整结果和退出码,然后只报告证据所确立的内容。

- [ ] **目标行为有效**:相关测试或复现命令显示预期结果。(`npm test -- --grep 'cancel'`)
- [ ] **范围内无回归**:受影响的现有测试或 characterization 验证通过。(`npm test`)
- [ ] **Migration 机制就绪**:hermetic 文件或 preflight 验证加上任何所需的已部署 migration 证据满足陈述条件。(`npm run migrate:up --dry-run`)
- [ ] **Provider contract 安全**:无网络 fake 或 fixture 验证签名、映射、失败或去重行为。(provider-adapter 单元测试通过)
- [ ] **重构保留了行为**:锁定基线证据在前后对比,或聚焦的 characterization 验证。(在变更前后运行 characterization 测试)
- [ ] **文档反映当前真相**:受影响的 module、API 或后端状态页面已更新或有意识地确认不需要。

不要因为代码看起来合理、部分命令通过或 agent 报告成功而报告 DONE。将未验证的远程、生产、负载、浏览器、安全或发布事实作为命名缺口陈述并路由给其所有者。

## 状态报告

基于证据设置一个实现状态:

**`BUILT`** -- 请求的实现和必需的 hermetic 验证已完成。已部署或环境证据中已命名的缺口已列出,但不阻塞实现声明。示例:"cancel subscription 已实现,单元测试通过,集成测试等待 TEST_DATABASE_URL。"

**`BLOCKED`** -- 一个必需的实现事实、安全验证、凭证或环境不可用。说明缺失了什么以及尝试了什么。示例:"BLOCKED: Stripe test key 不可用,无法验证 webhook 签名处理。尝试:搜索 .env 文件,未找到 key。需要:STRIPE_TEST_KEY 或部署到配置了 webhook 的 staging。"

**`NEEDS_CONTRACT`** -- 一个 contract、边界、runtime、兼容性或恢复设计必须在实现能够正确继续之前改变。说明必须改变什么并路由到 Node02。示例:"NEEDS_CONTRACT: billing provider 没有 'cancel at period end' API。必须决定:立即取消并退还会按比例的金额,或在周期结束时保持订阅活跃而不涉及 provider。路由到 Node02。"

不要从 Node03 发布质量或发布裁决。将质量或安全判断路由到 Node05,发布执行路由到 Node06。
