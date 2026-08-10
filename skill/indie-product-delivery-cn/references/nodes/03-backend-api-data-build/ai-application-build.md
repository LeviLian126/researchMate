# AI 应用构建

## 章节

- [目的和入口条件](#目的和入口条件)
- [在 prompt 之前定义 AI contract](#在-prompt-之前定义-ai-contract)
- [构建结构化模型调用](#构建结构化模型调用)
- [将检索和引用构建为独立阶段](#将检索和引用构建为独立阶段)
- [构建有界 agent loop](#构建有界-agent-loop)
- [刻意设计记忆](#刻意设计记忆)
- [在实现前后评估](#在实现前后评估)
- [观察和发布 AI 路径](#观察和发布-ai-路径)
- [反模式:AI 输出作为可信权威](#反模式ai-输出作为可信权威)

## 目的和入口条件

当选定的后端切片包含 LLM、retrieval pipeline、agent loop、tool call、MCP 边界、model provider、prompt contract 或 AI 特定的 evaluation 时,使用此分支。将普通的认证、tenancy、persistence、job、provider adapter 和 API 行为保留在其他后端指南中。AI 不会创建第二套架构;它向相同的产品和信任边界添加概率性组件。

从模型旨在改善的用户可见决策开始。如果确定性规则、搜索查询、解析器、状态机或普通 workflow 能更可靠、更廉价地满足验收标准,就将其作为基线。只在歧义、综合、语义检索或开放式生成值得其方差和运营成本时引入模型判断。

## 在 prompt 之前定义 AI contract

通过可观察的输入、输出、权威、证据和失败行为来描述组件。prompt 只是一个实现产物。

| Contract 面 | 实现前决定 |
|---|---|
| task | 被支持的用户或系统决策;什么算作有用的结果 |
| input | 可信指令、不可信内容、检索到的证据、对话状态和大小限制 |
| output | schema、引用、confidence 或 refusal 行为、streaming 规则和稳定的 error mapping |
| authority | tool、数据、副作用、tenant scope、spend、迭代预算和需要人工的操作 |
| quality | golden case、negative case、确定性 invariant 和代表成功的 metric 或 rubric |
| operations | 延迟预算、token 和 cost 限制、provider fallback、trace 身份、取消、retry 和降级 |

将行为变更的输入一起版本化:model 和 provider、prompt、output schema、retrieval 配置、tool 定义、memory 策略和 evaluation 集。在 trace 或发布证据中记录足够的指纹,以解释为什么两次运行不同。

## 构建结构化模型调用

当应用必须精确执行策略时,将策略保持在模型之外。authorization、计费限制、破坏性权限、tenant 边界、必填字段、状态转换和法律或安全规则属于确定性代码。模型可以分类或推荐;拥有的 service 验证并决策。

当下游代码消费结果时,优先使用结构化输出。验证返回的 schema,显式处理 refusal 和 truncation,并将 provider 特定的错误映射到稳定的应用 contract。将模型文本视为不可信,直到验证通过。retry 可以解决传输或临时 provider 失败;它不会自动修复未充分定义的任务或无效的 output contract。

```typescript
// 带有 schema 验证、refusal、truncation 和 error mapping 的结构化模型调用
async function classifyTicket(
  content: string,
  tenantId: string,
): Promise<ClassifyResult> {
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [
        { role: 'system', content: CLASSIFY_SYSTEM_PROMPT },
        { role: 'user', content: content.slice(0, MAX_INPUT_TOKENS) },
      ],
      response_format: { type: 'json_schema', json_schema: CLASSIFY_SCHEMA },
      max_tokens: 200,
      timeout: 5000,
    });

    const raw = response.choices[0];

    // 显式处理 refusal
    if (raw.message.refusal) {
      return { kind: 'refused', reason: raw.message.refusal };
    }

    // 显式处理 truncation
    if (raw.finish_reason === 'length') {
      return { kind: 'truncated', partial: raw.message.content };
    }

    // 在信任输出之前验证 schema
    const parsed = ClassifySchemaValidator.parse(JSON.parse(raw.message.content));
    // parsed 现在已类型化并验证 -- 下游使用安全

    return { kind: 'ok', category: parsed.category, confidence: parsed.confidence };
  } catch (e) {
    // 将 provider 特定的错误映射到稳定 contract
    if (e instanceof OpenAITimeoutError) {
      return { kind: 'provider_error', retryable: true, code: 'timeout' };
    }
    if (e instanceof OpenAIRateLimitError) {
      return { kind: 'provider_error', retryable: true, code: 'rate_limited' };
    }
    if (e instanceof ZodError) {
      return { kind: 'provider_error', retryable: false, code: 'invalid_output' };
    }
    return { kind: 'provider_error', retryable: false, code: 'unknown' };
  }
}
```

prompt 应该陈述结果、改变结果的上下文、所需输出和防止真正损害的少数边界。仅在序列影响质量、安全或可复现性时添加序列。使用示例来定义难以解释的行为,而不是装饰 prompt 或将模型过拟合到一个 fixture。

## 将检索和引用构建为独立阶段

RAG pipeline 不是一次模型调用。保留可检查的阶段,使一个薄弱的回答可以追溯到实际的失败。

```
1. Ingest        2. Chunk         3. Embed         4. Retrieve
   normalize       split by        vectorize        tenant +
   source ID,      semantic +      tied to          permission
   version,        document        index version    filter BEFORE
   ownership,      structure,      (re-index on     evidence reaches
   permissions,    preserve        change)          the model
   deletion        source +
   state           location
                   metadata
     |                |                |                |
     v                v                v                v
  FAILURE:          FAILURE:          FAILURE:          FAILURE:
  stale source,     lost context,     wrong embedding   missing tenant
  wrong tenant      bad boundaries    model, version    filter, returns
                                                      other tenant's data

5. Rerank       6. Pack          7. Generate        8. Validate
   only when      context under    under citation     cited spans
   additional     explicit token   and refusal        exist,
   latency +      budget,          policy             support the
   dependency     preserve source  (refuse when       claim, and
   improves       boundaries,      evidence is        belong to
   measured       avoid            insufficient)      authorized
   cases          duplication                          corpus
     |                |                |                |
     v                v                v                v
  FAILURE:          FAILURE:          FAILURE:          FAILURE:
  reranker hides     context window   hallucinated      citation points
  relevant docs,     overflow,        answer without    to non-existent
  reorders away      lost source      evidence,         span, claim
  from retrieval     boundary         unsafe content    not supported
```

在回答风格之前衡量检索。一个精美的回答无法恢复从未被检索到的证据。将 corpus 覆盖率、retrieval recall、ranking 质量、引用正确性、groundedness、任务有用性、延迟和成本分开衡量。这使回归可诊断,并防止单一主观分数隐藏失败的阶段。

## 构建有界 agent loop

将 agent 表示为具有命名状态、允许操作、预算、停止条件、checkpoint 和恢复的显式状态机。loop 必须在成功、安全 refusal、人工决策或定义的预算上终止。"模型会知道何时停止"不是操作性 contract。

```
                    +----------+
                    |  IDLE    |
                    +----------+
                         |
                    user input
                         |
                         v
                    +----------+
                    | PLANNING |-----> budget exceeded -----> REFUSE
                    +----------+
                         |
                    plan ready
                         |
                         v
              +---> +----------+
              |     | EXECUTING|-----> tool error -----> RETRY (if budget)
              |     +----------+
              |          |
              |     tool result
              |          |
              +----------+
                         |
                   goal achieved?
                    /            \
                  yes            no
                  /                \
                 v                  v
           +----------+        +----------+
           |  DONE    |        | CHECKING |
           +----------+        +----------+
                                    |
                              checkpoint
                              persist state
                                    |
                              +----------+
                              | REFUSE   |  (if no progress or
                              +----------+   budget exhausted)
```

Tool 描述陈述能力和输入语义;确定性代码执行权威。验证 tool 参数,在模型之外绑定身份和 tenant 上下文,并返回区分成功、可重试失败、终态失败和部分进展的结构化结果。永远不要让检索到的文本、网页、文档或 tool 输出重写系统权威。即使它包含命令式语言,也将其视为数据。

仅在产品 contract 要求该操作时使用人工 checkpoint。持久化足够的状态以在中断后安全恢复。使重复的 tool 调用 idempotent 或附加稳定的操作 key,使 retry 不能复制副作用。

## 刻意设计记忆

按产品需求选择记忆,而非 agent 时尚。

| 记忆类型 | 必需的控制 |
|---|---|
| conversation state | scope、truncation 或 compaction、删除以及与当前用户指令的冲突 |
| project knowledge | provenance、tenant 所有权、version、permission 检查和刷新策略 |
| user preference | 同意、可编辑性、confidence、过期和遗忘方式 |
| workflow checkpoint | 确定性状态、操作身份、恢复和重放安全 |

不要将推断的个人事实作为真相存储。不要混合 tenant、环境或信任级别。当旧记忆与当前显式输入冲突时,当前输入优先,且冲突应该是可观察的。

## 在实现前后评估

在优化之前创建一个有代表性的小集合。包括普通成功、歧义输入、缺失证据、冲突证据、内容中的恶意指令、permission 边界、长输入、provider 失败和 refusal 正确的情况。仅在移除敏感数据并确认它们代表可复用行为后,才将生产失败保留为新 case。

对 schema、引用、permission、停止条件、tool 参数和状态变更使用确定性断言。对有用性、清晰度、综合和写作质量使用 rubric 或盲比较。在相同输入下与非 AI 或先前生产基线进行比较。不要从几个精心挑选的演示中声称改进。

## 观察和发布 AI 路径

trace 解释行为的阶段,但不记录 secret 或私有源内容:request 身份、tenant 安全的关联、model 指纹、retrieval 计数、选定的 source 标识符、tool 名称和结果、延迟、token、cost、fallback、refusal 和 evaluation 版本。在有助于事件诊断时捕获 provider request 标识符。

在最小可控接口之后发布。在 rollout 之前定义 fallback 和禁用行为。fallback 必须保留产品 contract,而不是静默返回一个自信但更弱的结果。在生产验证期间,使用安全的合成或授权数据,并确认成功路径和选定的降级路径。当 AI contract、证据状态、provider 边界或运营限制变更时,更新维护的 HTML board 和 API 或 schema 文档。

## 反模式:AI 输出作为可信权威

LLM 输出是概率性的。将其视为可信权威——让它直接触发副作用、绕过访问检查或设置持久状态——是最危险的 AI 实现错误。

```typescript
// 错误的做法:模型输出直接触发副作用
async function autoApproveRefund(ticketId: string) {
  const classification = await classifyTicket(ticketContent);
  if (classification.category === 'refund_approved') {
    await billingAdapter.processRefund(ticketId, classification.amount);
    // 模型决定了金额并触发了退款 -- 无服务端验证
    // prompt injection 或 hallucination 可以抽走资金
  }
}

// 好的做法:模型推荐,服务端验证并决策
async function handleRefundRequest(ticketId: string, userId: string) {
  const classification = await classifyTicket(ticketContent, tenantId);
  if (classification.kind !== 'ok') return { kind: 'provider_error', ... };

  // 模型分类了 -- 但服务端重新确立身份、scope 和策略
  const ticket = await ticketRepo.findById(ticketId);
  if (ticket.userId !== userId) return { kind: 'denied' };           // auth 检查
  const order = await orderRepo.findById(ticket.orderId);
  const maxRefund = order.amount * 0.5;                                // 策略限制
  const refundAmount = Math.min(classification.suggestedAmount, maxRefund);

  // 大额退款的人工 checkpoint
  if (refundAmount > HUMAN_REVIEW_THRESHOLD) {
    await reviewQueue.enqueue({ ticketId, amount: refundAmount });
    return { kind: 'pending_review' };
  }

  // provider 调用之前创建持久意图(参见 provider-async-build.md)
  await tx.refunds.insert({ ticketId, amount: refundAmount, status: 'pending' });
  const result = await billingAdapter.processRefund(ticketId, refundAmount);
  await tx.refunds.update(ticketId, { status: result.ok ? 'completed' : 'failed' });

  return { kind: 'ok', amount: refundAmount };
}
```

模型分类并推荐。服务端验证 schema,重新确立身份和 scope,执行策略限制,对大额应用人工 checkpoint,记录持久意图,然后才调用 provider。prompt injection 或 hallucination 无法绕过服务端护栏。