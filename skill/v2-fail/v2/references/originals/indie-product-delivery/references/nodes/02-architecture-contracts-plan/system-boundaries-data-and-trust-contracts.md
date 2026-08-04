# System Boundaries, Data, and Trust Contracts

Use this guide to turn approved product scope and repository evidence into explicit system, data, interface, permission, provider, and failure contracts that implementation must not guess.

## Sections

- [System Discovery and Boundary Map](#system-discovery-and-boundary-map)
- [Contracts, Data, and Trust Model](#contracts-data-and-trust-model)

## System Discovery and Boundary Map

#### 1. Intake product truth without reopening product strategy

1. Read the Node01 handoff and identify the target actor, primary workflow, first successful outcome, accepted scope, non-goals, acceptance criteria, product constraints, and material assumptions.
2. Classify every input fact as `confirmed`, `defaulted`, `inferred`, or `unknown`. A default is not a user decision, and an inference is not runtime truth.
3. Name the architecture question in one sentence: what system capability must now exist, for whom, under which constraints, and what outcome must remain observable.
4. Confirm the change does not silently alter product promise, pricing, user role, privacy stance, or first success. Return those questions to Node01 rather than choosing them through technical design.

| Input | Required before contracts | Route when missing |
|---|---|---|
| workflow | actor, entry, action, observable outcome | Node01 |
| scope | keep/defer/reject boundary and non-goals | Node01 |
| acceptance | behavior that can succeed or fail | Node01 |
| constraints | privacy, payment, time, cost, support, platform | Node01 or user |
| current truth | source, config, docs, tests, runtime evidence | repo audit |

#### 2. Choose the system-design mode

Select the narrowest mode that covers the architectural uncertainty. Modes can combine only when their boundaries genuinely interact.

| Mode | Use when | Primary output |
|---|---|---|
| Greenfield | no established repo or system shape exists | minimum viable system boundary |
| Existing extension | an approved feature changes an existing workflow | affected-boundary delta |
| Strict contract | API, data, permission, public action, or event changes | explicit contract model |
| Provider or async | external service, webhook, job, cron, or realtime flow exists | trust and lifecycle path |
| Evolution | migration, removal, compatibility, provider state, or topology changes | old/new and recovery design |
| Developer surface | API, CLI, SDK, package, or integration is the product surface | first-success and upgrade contract |

Do not choose a mode because an implementation technology sounds interesting. A UI-only change that keeps
the same data, contract, and behavior normally stays in Node04.

#### 3. Audit repository and system reality

Inspect only evidence relevant to the slice: current modules, entry points, routes/actions, data access,
auth/session, provider adapters, jobs, configuration, deployment boundary, package commands, tests, docs,
open work, and recently changed files. Record the source path or command that supports each material claim.

For each relevant area, answer:

- What responsibility does it own now?
- What is known to call it, read it, or depend on it?
- What data or external state can it change?
- Which pattern is already working and should be preserved?
- Which fact remains unknown because evidence is absent or conflicting?

Read deferred work, TODOs, current diffs, or current-state HTML only when they touch, block, or are enabled by
this design. Do not turn routine repo exploration into a complete audit of unrelated modules.
#### 3a. Calibrate evidence and architecture unknowns

Keep a compact evidence inventory so a design claim can be separated from a convenient
assumption. Confidence is about the supporting evidence, not the importance of a
decision.

| Claim or unknown | Evidence source | Confidence | Consequence if wrong | Owner and next check |
|---|---|---|---|---|
| current behavior | source, running route, config, test, or current-state doc | confirmed / partial / absent | boundary, contract, or cost impact | named owner and decision point |

Prefer current code, configuration, live-safe observation, and maintained contracts over
stale docs or a nearby-looking module. When sources conflict, record the conflict, use
the safer temporary assumption, and identify the smallest check that can resolve it.
Do not turn a low-confidence detail into an architecture-wide rewrite.

An architecture unknown deserves escalation when it can change the data owner, trust
boundary, public compatibility, provider behavior, runtime topology, or recovery path.
A local unknown that does not affect those boundaries may remain named in the handoff
for Node03/04 to resolve during implementation.

#### 4. Build the existing leverage map

Map each sub-problem to the strongest existing path before proposing new layers.

| Sub-problem | Existing path | Decision | Reason | Constraint or gap |
|---|---|---|---|---|
| capability or flow | module, route, job, provider, or `none` | reuse / extend / replace / new | repo/product fit | evidence or trigger |

`Reuse` preserves a complete suitable path. `Extend` changes a proven owner without creating a parallel
concept. `Replace` requires a named deficiency, consumer impact, and evolution route. `New` means no suitable
path exists after inspection. Do not create a second source of truth, second authorization path, or second
provider adapter merely because it is locally convenient.

#### 5. Draw the system context and boundary map

Describe the main path before deciding internal implementation. Use a diagram when a flow crosses more than
two boundaries or includes asynchronous/provider state.

```text
actor -> entry point -> system boundary -> owning module -> data/provider -> observable outcome
```

For every boundary, record the owner, inputs/outputs, state ownership, dependency direction, trust level, and
failure handoff.

| Boundary | Owner | Inputs and outputs | State owner | Trust or async concern | Stable rule |
|---|---|---|---|---|---|
| entry | page, route, CLI, event | request or command / visible result | caller or system | identity and validation | no business truth in client-only state |
| domain | service or module | validated intent / domain result | domain model | invariant and authorization | one owner per rule |
| data | repository or store | query or mutation / durable record | database or provider | tenancy, retention, concurrency | no bypass path |
| external | adapter or job | normalized request / mapped result | provider plus local record | timeout, callback, cost | provider detail stays at edge |

Name stable boundaries that this change must not violate: current public contracts, module ownership,
authorization enforcement, provider adapter ownership, data source of truth, or deployment topology.

#### 6. Challenge system scope before designing deeper

Test whether this remains one coherent system slice:

1. Does one primary outcome connect the entry, data, modules, and observable result?
2. Does it add a distinct actor, data lifecycle, external consumer, or release risk that can be independently
   designed and delivered?
3. Can a smaller extension of an existing path create the same outcome without an honesty or safety gap?
4. Is a proposed platform, queue, service, or abstraction solving a real boundary, or hiding an unresolved
   product/system question?

Split when a part has an independent user outcome, trust model, lifecycle, compatibility window, or owner.
Record later slices as `deferred design slices`; do not fully architect them in anticipation.
#### 6a. Capture the architecture discovery record

Before moving to contracts, summarize the discovery in a decision record that downstream
nodes can read without repeating the audit.

| Record field | What to capture |
|---|---|
| system mode | selected mode and any coupled mode that actually interacts |
| active boundary | entry, owning module, state owner, external edge, and observable outcome |
| existing leverage | reuse/extend/replace/new choices with source evidence |
| stable boundary | public contract, data source, trust rule, adapter, or topology that must remain intact |
| design slices | smallest coherent slices and explicit deferrals |
| unknown | missing fact, consequence, temporary safe assumption, owner, and latest safe decision point |
| escalation | product decision, approval, or evidence that must happen before Build |

A good record makes the next contract or decision question smaller. It is not a prose
restatement of every file inspected, nor an implementation plan. Retain only evidence
that changes the boundary, contract, cost, risk, or ability to recover.

#### 7. Update durable architecture truth

Update the Architecture and Technology/Contracts regions of the existing HTML project command board when the
changed boundary has durable value. Preserve verified stable facts and replace superseded current-state facts
in place; add a separate artifact only when the user requests it or the board cannot remain usable.

Link each material diagram or claim to source paths, configs, contracts, tests, or an explicitly planned
decision. HTML pages communicate current truth; they do not become a second implementation plan or history
log.
#### 7a. Select the next design question

Do not load every Node02 workflow after discovery. Follow the uncertainty that remains.

| Observed need | Next workflow |
|---|---|
| data ownership, API/action, permission, failure, provider, or job behavior is undecided | contracts-data-and-trust-model |
| module boundary, dependency, storage, queue, provider, runtime, or operating cost is undecided | architecture-decisions-and-runtime-shape |
| public compatibility, migration, removal, provider-state reconciliation, or build readiness is undecided | evolution-readiness-and-build-handoff |
| no material system question remains and the local owner is clear | route directly to the relevant Build node |

Loading the next file is an explicit response to evidence, not a full-node reading
requirement. Preserve the discovery record as the shared input for the selected workflow.

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
