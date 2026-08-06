# AI Application Build

## Sections

- [Purpose and entry conditions](#purpose-and-entry-conditions)
- [Define the AI contract before prompts](#define-the-ai-contract-before-prompts)
- [Build structured model calls](#build-structured-model-calls)
- [Build retrieval and citations as separate stages](#build-retrieval-and-citations-as-separate-stages)
- [Build bounded agent loops](#build-bounded-agent-loops)
- [Design memory deliberately](#design-memory-deliberately)
- [Evaluate before and after implementation](#evaluate-before-and-after-implementation)
- [Observe and release the AI path](#observe-and-release-the-ai-path)
- [Anti-Pattern: AI Output as Trusted Authority](#anti-pattern-ai-output-as-trusted-authority)
## Purpose and entry conditions

Use this branch when the selected backend slice contains an LLM, retrieval pipeline, agent
loop, tool call, MCP boundary, model provider, prompt contract, or AI-specific evaluation.
Keep ordinary authentication, tenancy, persistence, jobs, provider adapters, and API behavior
in the other backend guides. AI does not create a second architecture; it adds probabilistic
components to the same product and trust boundaries.

Start from the user-visible decision the model is meant to improve. If a deterministic rule,
search query, parser, state machine, or ordinary workflow can meet the acceptance more
reliably and cheaply, use it as the baseline. Introduce model judgment only where ambiguity,
synthesis, semantic retrieval, or open-ended generation earns the variance and operating cost.

## Define the AI contract before prompts

Describe the component through observable inputs, outputs, authority, evidence, and failure
behavior. The prompt is only one implementation artifact.

| Contract surface | Decide before implementation |
|---|---|
| task | the user or system decision being supported; what counts as a useful result |
| input | trusted instructions, untrusted content, retrieved evidence, conversation state, and size limits |
| output | schema, citations, confidence or refusal behavior, streaming rules, and stable error mapping |
| authority | tools, data, side effects, tenant scope, spend, iteration budget, and actions that require a human |
| quality | golden cases, negative cases, deterministic invariants, and the metric or rubric that represents success |
| operations | latency budget, token and cost limits, provider fallback, trace identity, cancellation, retry, and degradation |

Version the behavior-changing inputs together: model and provider, prompt, output schema,
retrieval configuration, tool definitions, memory policy, and evaluation set. Record enough
of this fingerprint in traces or release evidence to explain why two runs differ.

## Build structured model calls

Keep policy outside the model when the application must enforce it exactly. Authorization,
billing limits, destructive permissions, tenant boundaries, required fields, state
transitions, and legal or safety rules belong in deterministic code. The model may classify
or recommend; the owning service validates and decides.

Prefer structured outputs when downstream code consumes the result. Validate the returned
schema, handle refusal and truncation explicitly, and map provider-specific errors into the
stable application contract. Treat model text as untrusted until validated. A retry may
address transport or transient provider failure; it does not automatically fix an
underspecified task or invalid output contract.

```typescript
// structured model call with schema validation, refusal, truncation, and error mapping
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

    // handle refusal explicitly
    if (raw.message.refusal) {
      return { kind: 'refused', reason: raw.message.refusal };
    }

    // handle truncation explicitly
    if (raw.finish_reason === 'length') {
      return { kind: 'truncated', partial: raw.message.content };
    }

    // validate schema before trusting the output
    const parsed = ClassifySchemaValidator.parse(JSON.parse(raw.message.content));
    // parsed is now typed and validated -- safe to use downstream

    return { kind: 'ok', category: parsed.category, confidence: parsed.confidence };
  } catch (e) {
    // map provider-specific errors into stable contract
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

Prompts should state the result, the context that changes it, the required output, and the
few boundaries that prevent real damage. Add a sequence only when the sequence affects
quality, safety, or reproducibility. Use examples to define hard-to-explain behavior, not to
decorate the prompt or overfit the model to one fixture.

## Build retrieval and citations as separate stages

A RAG pipeline is not one model call. Preserve inspectable stages so a weak answer can be
traced to the actual failure.

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

Measure retrieval before answer style. A polished answer cannot recover evidence that was
never retrieved. Separate corpus coverage, retrieval recall, ranking quality, citation
correctness, groundedness, task usefulness, latency, and cost. This makes regressions
diagnosable and prevents a single subjective score from hiding the stage that failed.

## Build bounded agent loops

Represent an agent as an explicit state machine with named state, allowed actions, budgets,
stop conditions, checkpoints, and recovery. The loop must terminate on success, a safe
refusal, a human decision, or a defined budget. "The model will know when to stop" is not an
operational contract.

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

Tool descriptions state capability and input semantics; deterministic code enforces
authority. Validate tool arguments, bind identity and tenant context outside the model, and
return structured results that distinguish success, retryable failure, terminal failure, and
partial progress. Never let retrieved text, a webpage, a document, or tool output rewrite
system authority. Treat it as data even when it contains imperative language.

Use a human checkpoint only when the product contract requires one for the action. Persist
enough state to resume safely after interruption. Make repeated tool calls idempotent or
attach a stable operation key so retries cannot duplicate side effects.

## Design memory deliberately

Choose memory by product need rather than agent fashion.

| Memory type | Required controls |
|---|---|
| conversation state | scope, truncation or compaction, deletion, and conflict with current user instructions |
| project knowledge | provenance, tenant ownership, version, permission checks, and refresh policy |
| user preference | consent, editability, confidence, expiry, and a way to forget it |
| workflow checkpoint | deterministic state, operation identity, recovery, and replay safety |

Do not store inferred personal facts as truth. Do not mix tenants, environments, or trust
levels. When old memory conflicts with current explicit input, current input wins and the
conflict should be observable.

## Evaluate before and after implementation

Create a small representative set before optimizing. Include ordinary successes, ambiguous
inputs, missing evidence, conflicting evidence, malicious instructions inside content,
permission boundaries, long inputs, provider failure, and cases where refusal is correct.
Preserve production failures as new cases only after removing sensitive data and confirming
that they represent a reusable behavior.

Use deterministic assertions for schemas, citations, permissions, stop conditions, tool
arguments, and state changes. Use a rubric or blind comparison for usefulness, clarity,
synthesis, and writing quality. Compare against the non-AI or previous-production baseline
under the same inputs. Do not claim improvement from a few cherry-picked demonstrations.

## Observe and release the AI path

Trace the stages that explain behavior without logging secrets or private source content:
request identity, tenant-safe correlation, model fingerprint, retrieval counts, selected
source identifiers, tool names and outcomes, latency, tokens, cost, fallback, refusal, and
evaluation version. Capture provider request identifiers where useful for incident diagnosis.

Release behind the smallest controllable surface. Define fallback and disable behavior before
rollout. A fallback must preserve the product contract rather than silently returning a
confident but weaker result. During production verification, use safe synthetic or authorized
data and confirm both the successful path and the chosen degradation path. Update the
maintained HTML board and API or schema documents when the AI contract, evidence status,
provider boundary, or operational limitation changes.

## Anti-Pattern: AI Output as Trusted Authority

LLM output is probabilistic. Treating it as trusted authority -- letting it directly trigger
side effects, bypass access checks, or set durable state -- is the most dangerous AI
implementation mistake.

```typescript
// bad: model output directly triggers a side effect
async function autoApproveRefund(ticketId: string) {
  const classification = await classifyTicket(ticketContent);
  if (classification.category === 'refund_approved') {
    await billingAdapter.processRefund(ticketId, classification.amount);
    // model decided the amount and triggered the refund -- no server-side validation
    // prompt injection or hallucination can drain money
  }
}

// good: model recommends, server validates and decides
async function handleRefundRequest(ticketId: string, userId: string) {
  const classification = await classifyTicket(ticketContent, tenantId);
  if (classification.kind !== 'ok') return { kind: 'provider_error', ... };

  // model classified -- but server re-establishes identity, scope, and policy
  const ticket = await ticketRepo.findById(ticketId);
  if (ticket.userId !== userId) return { kind: 'denied' };           // auth check
  const order = await orderRepo.findById(ticket.orderId);
  const maxRefund = order.amount * 0.5;                                // policy limit
  const refundAmount = Math.min(classification.suggestedAmount, maxRefund);

  // human checkpoint for large refunds
  if (refundAmount > HUMAN_REVIEW_THRESHOLD) {
    await reviewQueue.enqueue({ ticketId, amount: refundAmount });
    return { kind: 'pending_review' };
  }

  // durable intent before provider call (see provider-async-build.md)
  await tx.refunds.insert({ ticketId, amount: refundAmount, status: 'pending' });
  const result = await billingAdapter.processRefund(ticketId, refundAmount);
  await tx.refunds.update(ticketId, { status: result.ok ? 'completed' : 'failed' });

  return { kind: 'ok', amount: refundAmount };
}
```

The model classifies and recommends. The server validates the schema, re-establishes
identity and scope, enforces policy limits, applies a human checkpoint for large amounts,
records durable intent, and only then calls the provider. Prompt injection or hallucination
cannot bypass the server-side guardrails.