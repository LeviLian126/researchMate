# Backend Slice, Domain, and Interface Build

Use this guide to frame an approved backend slice, place business behavior in the correct owner, and implement HTTP, action, CLI, admin, event, or webhook boundaries without changing their contracts by accident.

## Sections

- [Backend Discovery and Slice Framing](#backend-discovery-and-slice-framing)
- [Domain Workflow and State Change Build](#domain-workflow-and-state-change-build)
- [Interface, Access, and Contract Build](#interface-access-and-contract-build)

## Backend Discovery and Slice Framing

#### 1. Recover implementation truth

Read the Node01/02 handoff and restate the slice as one observable backend outcome.
Capture the actor, entry, approved action, expected result, non-goals, acceptance,
trust constraints, failure/recovery behavior, and proof obligation.

Classify facts so a convenient assumption cannot become an implementation contract.

| Fact state | Meaning | Build treatment |
| --- | --- | --- |
| confirmed | supported by current contract, repo evidence, or explicit user decision | implement it |
| defaulted | reversible local detail selected under an existing convention | record briefly |
| inferred | likely from code but not approved as contract truth | verify or constrain |
| unknown | missing, conflicting, or externally unverifiable | stop or name a bounded gap |

Never default public fields, schema semantics, tenancy, authorization, entitlement,
provider behavior, lifecycle, compatibility, cost policy, or recovery. Local naming,
fixture values, helper placement, and log wording may be defaulted only when they do
not change an observable contract.

#### 2. Audit the relevant implementation path

Inspect the nearest working path before creating a new one. Limit the audit to the
entry point, direct callers, domain/service owner, repository/data access, access
enforcement, error mapper, provider/job boundary, test harness, relevant config, and
current-state docs.

| Area | Recover | Evidence to retain |
| --- | --- | --- |
| entry | route/action/CLI/event, caller, transport convention | source path and existing request flow |
| domain | use-case owner, state rules, transaction style | nearby successful capability |
| data | repository, schema, query filters, constraint pattern | source of truth and ownership boundary |
| access | session/signature/role/tenant enforcement | server-side enforcement point |
| external | adapter, job, callback, timeout/retry convention | local provider lifecycle |
| tests | framework, helpers, fixtures, assertion style, commands | nearest behavior test |
| docs/config | module/API page, env names, feature flags, current diff | durable fact or active constraint |

Read TODOs, deferred work, recent changes, and docs only when they touch the slice.
Do not broaden a focused backend build into a whole-repository archaeology project.

#### 3. Build the implementation spine

Trace the approved behavior before choosing files or classes.

    capability -> entry -> interface/access -> domain policy -> data/provider
    -> observable result or recoverable failure -> local proof

For each arrow, name the existing owner or explicitly mark it new. A missing owner is
a design signal, not permission to put all behavior in a controller or handler.

| Spine point | Required statement |
| --- | --- |
| capability | approved outcome and actor |
| entry | request, command, event, schedule, or callback that starts work |
| interface/access | validation, identity, scope, and public result boundary |
| domain | invariant, state transition, policy, or orchestration owner |
| data/provider | durable source of truth or normalized external edge |
| outcome | result, pending state, error, or recovery visible to the caller |
| proof | smallest executable behavior that demonstrates the contract |

#### 4. Select a build mode

Use the narrowest mode that covers the implementation risk. Modes may combine only if
the same vertical slice truly crosses both boundaries.

| Mode | Use when | Required follow-up |
| --- | --- | --- |
| local extension | existing module implements an approved adjacent behavior | preserve convention and focused proof |
| interface/access | entry, input, output, auth, tenant, or public behavior changes | load interface/access workflow |
| domain state | use-case, invariant, conflict, or state transition changes | load domain workflow |
| persistence evolution | query, schema, transaction, backfill, constraint, or durable dedupe changes | load persistence workflow |
| provider/async | provider, job, callback, remote state, or delayed work changes | load provider workflow |
| regression fix | observed behavior is wrong or a test fails | reproduce before changing code |
| hardened slice | payment, admin, PII, tenant, auth, or destructive behavior changes | attach Node05-ready proof obligations |

#### 5. Challenge scope and choose existing leverage

For each sub-problem, mark reuse, extend, replace, or new. Reuse preserves a suitable
path; extend changes its established owner; replace needs a named defect and evolution
path; new requires evidence that no suitable path exists.

Ask before Build:

1. What is the smallest vertical change that achieves the approved outcome?
2. Does an existing route, service, repository, adapter, job, or test already solve
   part of it?
3. Is a proposed abstraction protecting a real boundary or hiding uncertainty?
4. Which work is explicitly not in scope and should remain deferred?
5. What realistic failure can this new path create in production, and which later
   proof will distinguish it from a guess?

If a change expands into multiple independent outcomes, trust models, data lifecycles,
or release risks, return to Node02 for a slice decision rather than silently widening
the implementation.

#### 6. Frame the build and proof

Produce a compact implementation frame before editing.

| Field | Required content |
| --- | --- |
| outcome | the observable behavior being implemented |
| owners | existing/new entry, domain, data/provider, and docs owners |
| invariant | condition that must remain true |
| allowed change | files/modules likely to change and why |
| non-goals | related work deliberately left untouched |
| local proof | targeted test, reproduction, command, or safe manual observation |
| side-effect limit | credentials, data, provider, migration, or environment boundary |
| escalation | evidence that requires Node01, Node02, Node05, or Node06 |

This is not a file-by-file code plan. It keeps the implementer from discovering the
contract only after changes have already spread across the repository.

## Domain Workflow and State Change Build

#### 1. Locate the use-case owner

Start from the implementation spine and identify the module that already owns the
business outcome. Prefer extending a service/domain module that owns the related
invariant over creating a route-local workflow or a second service with overlapping
authority.

| Question | Required answer |
| --- | --- |
| intent | what validated action is the actor asking the system to perform? |
| owner | which module owns the decision and resulting state? |
| preconditions | what identity, scope, state, or entitlement must already hold? |
| invariant | what must remain true before, during, and after the change? |
| result | what domain outcome does the entry boundary need to present? |
| side effect | what durable write, event, provider request, or job trigger follows? |
| failure | what conflict, denial, invalid state, or temporary failure can occur? |

A controller, CLI command, or webhook handler may translate transport into intent, but
it must not become the only home for a reusable business rule. Conversely, do not add a
domain service merely to hide a one-line policy already owned by a nearby module.

#### 2. Define the executable use-case path

Write the intended path in outcome language before changing implementation:

    validated intent -> policy and invariant -> state decision -> durable change or
    external request -> domain result -> boundary-specific response

Name every branch whose behavior is meaningful. This is not a replacement for Node02
state design; it is the implementation map for the state and failure behavior Node02
has already chosen.

| Path concern | Implementer responsibility |
| --- | --- |
| policy | consume trusted identity/scope and evaluate the approved rule |
| state transition | allow only contracted source-to-target transitions |
| conflict | detect stale, duplicate, or incompatible current state honestly |
| side effect | schedule it only after the required durable decision succeeds |
| result | return a stable domain outcome, not HTTP/provider formatting |
| recovery | surface retryable, manual-repair, or terminal outcome selected by Node02 |

When a result could be represented as success, accepted/pending, no-op duplicate,
conflict, validation failure, denied, temporary failure, or recovery-required, preserve
the distinction. Collapsing all exceptions into a generic failure erases the contract.

#### 3. Keep policy, state, and side effects coherent

Implement policy in the owner that can see the relevant trusted facts. Use existing
repositories/adapters through their contracts; do not reach around them to duplicate
data checks or invoke a provider directly from an entry boundary.

| Concern | Domain rule |
| --- | --- |
| authorization | consume the server-side access decision; do not trust UI or caller hints |
| state | verify current state and transition owner before write/request |
| idempotency | coordinate a duplicate identity with persistence/provider mechanisms |
| transaction | group domain changes that must succeed or fail together; delegate mechanics to persistence |
| external request | create the approved durable intent/status before or with the request as designed |
| compensation | trigger only the designed follow-up; do not invent rollback semantics |
| audit/event | emit only after the authoritative transition is known |

For a multi-write invariant, keep the domain method explicit about what is atomic and
what is eventually reconciled. If the system cannot explain that distinction, route
back to Node02 rather than approximating consistency.

#### 4. Add helpers and services only when ownership improves

A new helper/service must remove real complexity: it encapsulates a repeated invariant,
protects a trust/provider boundary, separates a stable use case, or makes a behavior
independently verifiable. Record its owner, input, output, dependency direction, and
invariant in a compact implementation note or current-state module update when durable.

| Signal | Preferred action |
| --- | --- |
| existing owner fits | extend it |
| repeated policy in two real callers | extract a focused domain helper |
| entry has growing business branches | move use-case logic inward |
| provider protocol leaks into policy | use the provider workflow/adapter boundary |
| one-off simple conversion | keep it local and named for the outcome |
| abstraction anticipates a hypothetical second use | defer it |

Do not use generic managers, orchestration layers, or event buses to make a small
feature look architecturally complete. The smallest honest owner is usually better.

#### 5. Implement refactors with a locked baseline

Before a backend refactor, list the behaviors that must remain unchanged: public entry,
field/response shape, authentication/authorization, state result, schema semantics,
provider request/error behavior, job trigger, and observability/recovery signal.

| Refactor evidence | Required action |
| --- | --- |
| existing behavior test | run it before and after the focused change |
| no suitable test | create a minimal characterization/proof for the affected behavior |
| contract change approved | state exactly which baseline changes and why |
| unrelated debt discovered | leave it named but untouched unless it blocks the slice |
| module boundary becomes impossible | return to Node02 with evidence |

A clean-looking internal rewrite is not sufficient proof when its old callers, error
paths, or callbacks have behavior the user relies on.

#### 6. Connect to data and provider mechanics deliberately

The domain owner specifies what must be true; persistence implements durable constraints,
transactions, concurrency, and migration mechanics; provider/async code implements
remote protocols, retries, callback verification, and reconciliation. Keep these
interfaces explicit rather than leaking database rows or SDK objects across layers.

When an implementation needs a new state, fee/entitlement rule, public error, recovery
action, or compatibility behavior that Node02 did not define, stop. That is a system
decision, not an opportunity for a domain default.

## Interface, Access, and Contract Build

#### 1. Recover the interface contract

For every changed entry, capture caller, intent, input, validation, identity, scope,
success output, side effect, errors, compatibility behavior, and local proof. Use the
existing route/action pattern unless Node02 explicitly approved a new surface.

| Contract field | Implement at Node03 |
| --- | --- |
| caller | user, admin, service, CLI user, provider, job, or internal module |
| input | source, allowed fields, normalization, size/rate restrictions |
| identity | session, token, signature, service identity, or command context |
| scope | tenant, account, owner, object, role, entitlement, environment |
| success | response/result/event shape and durable side effect |
| errors | validation, unauthenticated, denied, absent, conflict, provider, internal |
| compatibility | additive/default/alias/error/timing semantics already selected by Node02 |
| proof | targeted behavior that verifies the entry cannot bypass its contract |

Do not alter status codes, public field names, error shape, pagination behavior,
authentication requirement, timing, or idempotency semantics because an implementation
shortcut is convenient. These are interface changes and require Node02 when undecided.

#### 2. Normalize and validate at the untrusted boundary

Treat request bodies, query/path values, cookies, headers, form actions, CLI args,
admin input, webhook payloads, uploads, model output, imported files, and event
arguments as untrusted until a boundary validates them.

| Input concern | Required implementation |
| --- | --- |
| shape | validate type, required/optional fields, nested shape, and size |
| normalization | trim/canonicalize only when contract allows and preserve meaningful distinctions |
| allowlist | accept only client-settable fields; reject or ignore unknowns as contracted |
| server-owned values | derive owner, tenant, role, price, quota, entitlement, provider ID, timestamp, and controlled state from trusted state |
| dynamic query | whitelist sort, filter, include, and page options; bind values safely |
| files/URLs | validate type, size, content/path/target rules before downstream use |
| external data | verify signature/schema/origin before it reaches domain behavior |

Validation prevents malformed intent; it does not decide whether the actor is allowed.
Keep validation reusable where the repo already has a boundary schema/validator, but do
not create a general framework for one simple request.

#### 3. Enforce identity and access at the server

Implement the Node02 trust chain at the actual enforcement point:

    subject -> resource -> action -> scope -> enforcement -> safe failure -> evidence

Authenticate before protected access. Resolve resource scope from trusted identity and
server-side lookup, then authorize before read, mutation, export, provider action, or
private-field disclosure. A UI guard, caller-provided owner ID, or hidden route is not
an enforcement point.

| Access case | Required behavior |
| --- | --- |
| owned record | query and mutate through owner/tenant-scoped repository access |
| list/search | apply permission filter in the data query, not after fetching all rows |
| admin action | verify explicit privileged authority and audit requirement when designed |
| entitlement/plan | read canonical server-side state, never client price/plan/quota |
| webhook/callback | verify source before locating or updating a local resource |
| absent versus denied | follow privacy-preserving contract; do not leak resource existence |
| public response | map through response allowlist and omit internal/sensitive fields |

If access depends on a rule not represented by the contract, do not encode a guessed
policy in a middleware or service. Return to Node02 with the specific subject/resource
question.

#### 4. Map stable results and failures

Convert domain results into the current public representation in one established place.
Keep transport formatting out of domain services and provider adapters.

| Outcome | Boundary behavior |
| --- | --- |
| success | stable response/result shape, redirect, event, or accepted async state |
| validation failure | field-safe, actionable error without internal details |
| unauthenticated | current auth challenge/redirect/response convention |
| denied or privacy-safe absence | contracted status and no sensitive existence leak |
| conflict/duplicate | stable conflict semantics and safe retry guidance |
| provider/temporary failure | recoverable error class, correlation reference, no secret leakage |
| internal failure | safe generic response, redacted diagnostic evidence, no stack/SQL disclosure |

Use the repository's error mapper when present. Do not return inconsistent ad hoc
objects from new entries just because the happy path is simple.

#### 5. Implement query-facing interface behavior

When a public entry reads collections, implement the agreed filter, sort, pagination,
permission filter, empty state, stale-state behavior, and rate/cost boundary. Do not
promise a total count, cursor, page size, or filtering capability the persistence layer
cannot support safely.

Check for unbounded responses, user-controlled sort expressions, query-per-item
serialization, nested private fields, and timing changes caused by moving work async.
Route a storage/index/consistency decision back to Node02; implement the chosen query
shape in the persistence workflow.

#### 6. Cover developer-facing interfaces conditionally

Only for API, CLI, SDK, package, webhook, or integration consumers, verify the
first-success path for the target developer role and its expected vocabulary/workflow:
prerequisite identity, smallest valid input, meaningful result, recoverable error,
version/upgrade expectation, example ownership, and current API documentation.
Implement the approved safe defaults for the common path and expose advanced overrides
or an escape hatch only where the Node02 contract names a real consumer need. Make each
developer-visible error communicate what happened, why, and how to fix or safely
recover without exposing internal details. For a private internal helper, do not
simulate a public developer platform.

Update the affected API or module current-state page when the durable entry contract
actually changed. Keep architecture decisions in Node02 and detailed QA ownership in
Node05.
