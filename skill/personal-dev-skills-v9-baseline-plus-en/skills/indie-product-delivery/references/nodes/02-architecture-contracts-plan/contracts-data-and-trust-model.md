# Contracts, Data, and Trust Model

## Contracts, Data, and Trust Model

#### 1. Build the capability spine

Map each approved capability through the whole system before detailing one endpoint or table in isolation.

| Capability | Actor and entry | Outcome | Owning module | Data | Action or event | Permission | Provider/job | Failure | Architecture proof |
|---|---|---|---|---|---|---|---|---|---|

Every capability must trace to a Node01 outcome or a trust/safety obligation. Mark a capability `defer` when it is useful but not required by the active slice. Reject an item that only supplies imagined future reuse or duplicates a path already captured by the leverage map.

For non-trivial flows, state the lifecycle in plain language:

```text
intent -> validation -> authorization -> state change or provider work -> visible result -> recovery or next action
```

Use this spine to find missing ownership, hidden side effects, untrusted inputs, and no-owner failures before adding technology.

#### 2. Define the domain and data lifecycle

For each persistent entity, table, document, object, or provider-backed record, define only fields and rules
needed to make system behavior unambiguous.

| Data concern | Required design decision |
|---|---|
| meaning and owner | product meaning, owning module, tenant or account scope |
| identity | primary identity, external identity, uniqueness, duplicate behavior |
| fields | type, nullable/default policy, sensitivity, source of truth |
| states | allowed states, transition owner, terminal/retryable states |
| lifecycle | create, read, list, update, delete, export, retention, backup |
| relationships | cardinality, ownership, cascade or preserve behavior |
| integrity | constraints, normalization, concurrency or idempotency rule |
| visibility | subject scope, admin access, redaction, audit need |

For important reads, define filter, sort, pagination, permission filter, empty state, stale state, and index
pressure. Do not choose a concrete index or query implementation unless that choice is architecture-significant.
Record the condition that would require a different storage/query strategy.
For each query that drives a product workflow, also name its consistency expectation:
whether a just-completed write must appear immediately, whether a short stale view is
honest, and which state the user sees while data catches up. This prevents a cache,
provider delay, or asynchronous projection from silently changing the product promise.

#### 2a. Classify public-contract evolution

When an interface has consumers beyond the owning module, classify its change before
calling it compatible. The classification belongs in the evolution record when a window,
consumer migration, or approval is needed.

| Change | Default classification | Required system response |
|---|---|---|
| new optional field or action | additive | Document semantics and preserve prior behavior. |
| required input or field | potentially breaking | Name affected callers and compatibility/default path. |
| rename or location change | breaking unless old alias remains | Define alias, migration notice, and removal condition. |
| enum/state expansion | consumer-sensitive | Verify callers can tolerate unknown or new state. |
| error shape or code change | consumer-sensitive | Preserve recoverable meaning and update error-to-fix guidance. |
| authentication or authorization change | trust-affecting | Re-evaluate access, failure behavior, and approval. |
| timing or async behavior change | behavior-affecting | Define pending, completion, callback, and timeout semantics. |
| idempotency or duplicate behavior change | data-affecting | Define replay safety and durable duplicate identity. |
| removal or deprecation | breaking | Inventory consumers and route to evolution/recovery design. |

Private interfaces still need an owner and failure semantics, but do not simulate public
versioning where no separate consumer or deployment boundary exists.

#### 3. Define interface and event contracts

Apply this to HTTP/API routes, form actions, CLI commands, admin operations, emitted events, webhooks, cron
triggers, and job messages that cross an ownership or trust boundary.

| Contract field | Required decision |
|---|---|
| identity | name, interface type, caller, owning module |
| input | source, fields, normalization, validation, size or rate boundary |
| authorization | credential/session/signature and enforcement point |
| success | result shape, redirect/event, durable side effects |
| errors | validation, authn/authz, absent, conflict, provider, internal behavior |
| evolution | additive/required/rename/enum/error/auth/timing/idempotency/removal/deprecation |
| proof | required evidence class and owner node |

Prefer additive behavior when consumers exist. A breaking public change requires consumer inventory,
compatibility decision, migration/deprecation path, approval, and an explicit evolution record. Do not hide a
public behavior change behind a refactor label.

#### 4. Define access and trust boundaries

For each protected read, list, mutation, admin path, job, provider callback, upload, and AI-derived action,
use this shape:

```text
subject -> resource -> action -> scope -> enforcement -> failure -> evidence
```

| Concern | Questions to answer |
|---|---|
| identity | who or what acts: user, tenant, admin, service, provider, job? |
| scope | which account, organization, object, plan, region, or environment applies? |
| enforcement | where is the decision enforced, and can callers bypass it? |
| untrusted input | which client, callback, upload, model output, or identifier must be checked? |
| failure | what is denied, what is visible, what is logged safely, who can recover? |
| evidence | which contract/security/runtime proof must later establish the boundary? |

Treat client role/owner/price/entitlement values, external callbacks, model output, and private identifiers as
untrusted until an enforcement point establishes otherwise. A UI guard is never the only authorization rule.
Treat prompts, retrieved content, and model output as proposals, never as authority. Before any AI-derived
side effect, deterministic server-side policy must re-establish identity, scope, permission, and parameter
constraints; prompt instructions or model confidence cannot replace that enforcement.
#### 5a. Reconcile contract interactions

Read the capability spine across data, interface, and trust rules once before handoff.
The following inconsistencies are common architecture defects, even when each individual
table looks complete.

| Cross-check | Resolve before Build |
|---|---|
| Data scope versus interface scope | A caller cannot request or infer records outside the enforced tenant/object scope. |
| State transition versus visible result | The result, pending state, and recovery action match what was durably accepted. |
| Provider callback versus local authority | A verified callback updates only the record and state it is entitled to affect. |
| Duplicate handling versus side effect | Replay cannot create a second charge, invite, export, or irreversible provider action. |
| Retention versus recovery | Deleted/redacted data cannot be required by an unnamed future repair path. |
| Error response versus operator process | A recoverable system condition has an owner and safe evidence without leaking secrets. |

When a resolution changes the user promise or acceptance criteria, return to Node01.
When it changes runtime shape, queueing, storage, module ownership, or a new provider,
continue to the architecture-decisions workflow rather than deciding it inside a table.

#### 5. Define states, failures, and recovery behavior

Name the states a user or operator can observe when they matter to the promise:

`success`, `pending`, `empty`, `validation failure`, `permission failure`, `not found`, `conflict`, `provider
failure`, `partial completion`, `stale state`, and `recovery required`.

For each plausible system failure, define behavior at the architecture level.

| Flow | Trigger | User sees | Durable state | System response | Recovery owner | Proof class |
|---|---|---|---|---|---|---|

Distinguish a retryable temporary failure from a conflict, a duplicate request, a permanently invalid request,
or a completed action whose response was lost. Silent failure is a contract gap. Do not define browser-level
copy, retry widgets, test cases, alert thresholds, or release commands here; send those choices downstream.

#### 6. Define provider and asynchronous work

Every provider adapter, webhook, cron task, queue job, backfill, or realtime process needs a compact contract.

| Area | Required decision |
|---|---|
| trigger | caller, schedule, event, eligibility, and dedupe identity |
| boundary | normalized input/output and local owner of external state |
| trust | secret/signature verification, redaction, callback authorization |
| lifecycle | timeout, retry owner, idempotency, ordering, partial completion |
| cost | quota, budget, rate boundary, customer-visible limit |
| recovery | replay/reconcile/manual repair and operator evidence |
| evolution | provider replacement, fallback, retained records, exit path |

Use an adapter when an external provider has distinct semantics, credentials, failure mapping, or likely future
replacement. Do not create a provider abstraction solely because a second provider might someday exist.

#### 7. Run the developer-facing contract gate only when applicable

For APIs, CLIs, SDKs, packages, webhooks, or integration products, first name the target
developer role, the job they are trying to complete, and the terms or workflow they
already expect. Verify that this developer can reach first success without founder
interpretation. Define install/access prerequisite, smallest valid request, meaningful
result, version behavior, upgrade/compatibility expectation, and owner of copy-paste
documentation/examples. Give the common path safe, useful defaults; add an advanced
override or escape hatch only for an evidenced consumer need. A developer-visible error
must explain what happened, why it happened, and how to fix or safely recover without
leaking internals.

This is a system contract gate, not a full developer-experience review. Route detailed docs, onboarding,
examples, and UI implementation to the owning downstream node. A private helper or
same-owner internal call does not trigger this gate.
