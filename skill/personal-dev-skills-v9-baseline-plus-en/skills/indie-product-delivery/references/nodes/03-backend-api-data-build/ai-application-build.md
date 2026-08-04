# AI Application Build

## Purpose and entry conditions

Use this branch when the selected backend slice contains an LLM, retrieval pipeline, agent loop, tool call, MCP boundary, model provider, prompt contract, or AI-specific evaluation. Keep ordinary authentication, tenancy, persistence, jobs, provider adapters, and API behavior in the other backend guides. AI does not create a second architecture; it adds probabilistic components to the same product and trust boundaries.

Start from the user-visible decision the model is meant to improve. If a deterministic rule, search query, parser, state machine, or ordinary workflow can meet the acceptance more reliably and cheaply, use it as the baseline. Introduce model judgment only where ambiguity, synthesis, semantic retrieval, or open-ended generation earns the variance and operating cost.

## Define the AI contract before prompts

Describe the component through observable inputs, outputs, authority, evidence, and failure behavior. The prompt is only one implementation artifact.

| Contract surface | Decide before implementation |
|---|---|
| task | the user or system decision being supported; what counts as a useful result |
| input | trusted instructions, untrusted content, retrieved evidence, conversation state, and size limits |
| output | schema, citations, confidence or refusal behavior, streaming rules, and stable error mapping |
| authority | tools, data, side effects, tenant scope, spend, iteration budget, and actions that require a human |
| quality | golden cases, negative cases, deterministic invariants, and the metric or rubric that represents success |
| operations | latency budget, token and cost limits, provider fallback, trace identity, cancellation, retry, and degradation |

Version the behavior-changing inputs together: model and provider, prompt, output schema, retrieval configuration, tool definitions, memory policy, and evaluation set. Record enough of this fingerprint in traces or release evidence to explain why two runs differ.

## Build structured model calls

Keep policy outside the model when the application must enforce it exactly. Authorization, billing limits, destructive permissions, tenant boundaries, required fields, state transitions, and legal or safety rules belong in deterministic code. The model may classify or recommend; the owning service validates and decides.

Prefer structured outputs when downstream code consumes the result. Validate the returned schema, handle refusal and truncation explicitly, and map provider-specific errors into the stable application contract. Treat model text as untrusted until validated. A retry may address transport or transient provider failure; it does not automatically fix an underspecified task or invalid output contract.

Prompts should state the result, the context that changes it, the required output, and the few boundaries that prevent real damage. Add a sequence only when the sequence affects quality, safety, or reproducibility. Use examples to define hard-to-explain behavior, not to decorate the prompt or overfit the model to one fixture.

## Build retrieval and citations as separate stages

A RAG pipeline is not one model call. Preserve inspectable stages so a weak answer can be traced to the actual failure.

1. Ingest and normalize source identity, version, ownership, permissions, and deletion state.
2. Chunk by semantic and document structure while preserving stable source and location metadata.
3. Embed and index with the configuration tied to the index version.
4. Retrieve with tenant and permission filters applied before evidence reaches the model.
5. Rerank only when the additional latency and dependency improve measured cases.
6. Pack context under an explicit token budget, preserving source boundaries and avoiding duplicated evidence.
7. Generate under a citation and refusal policy.
8. Validate that cited spans exist, support the associated claim, and belong to the authorized corpus.

Measure retrieval before answer style. A polished answer cannot recover evidence that was never retrieved. Separate corpus coverage, retrieval recall, ranking quality, citation correctness, groundedness, task usefulness, latency, and cost. This makes regressions diagnosable and prevents a single subjective score from hiding the stage that failed.

## Build bounded agent loops

Represent an agent as an explicit state machine with named state, allowed actions, budgets, stop conditions, checkpoints, and recovery. The loop must terminate on success, a safe refusal, a human decision, or a defined budget. “The model will know when to stop” is not an operational contract.

Tool descriptions state capability and input semantics; deterministic code enforces authority. Validate tool arguments, bind identity and tenant context outside the model, and return structured results that distinguish success, retryable failure, terminal failure, and partial progress. Never let retrieved text, a webpage, a document, or tool output rewrite system authority. Treat it as data even when it contains imperative language.

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

Do not store inferred personal facts as truth. Do not mix tenants, environments, or trust levels. When old memory conflicts with current explicit input, current input wins and the conflict should be observable.

## Evaluate before and after implementation

Create a small representative set before optimizing. Include ordinary successes, ambiguous inputs, missing evidence, conflicting evidence, malicious instructions inside content, permission boundaries, long inputs, provider failure, and cases where refusal is correct. Preserve production failures as new cases only after removing sensitive data and confirming that they represent a reusable behavior.

Use deterministic assertions for schemas, citations, permissions, stop conditions, tool arguments, and state changes. Use a rubric or blind comparison for usefulness, clarity, synthesis, and writing quality. Compare against the non-AI or previous-production baseline under the same inputs. Do not claim improvement from a few cherry-picked demonstrations.

## Observe and release the AI path

Trace the stages that explain behavior without logging secrets or private source content: request identity, tenant-safe correlation, model fingerprint, retrieval counts, selected source identifiers, tool names and outcomes, latency, tokens, cost, fallback, refusal, and evaluation version. Capture provider request identifiers where useful for incident diagnosis.

Release behind the smallest controllable surface. Define fallback and disable behavior before rollout. A fallback must preserve the product contract rather than silently returning a confident but weaker result. During production verification, use safe synthetic or authorized data and confirm both the successful path and the chosen degradation path. Update the maintained HTML board and API or schema documents when the AI contract, evidence status, provider boundary, or operational limitation changes.
