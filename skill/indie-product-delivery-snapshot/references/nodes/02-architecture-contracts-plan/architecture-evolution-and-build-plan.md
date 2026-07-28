# Architecture, Evolution, and Build Plan

Use this guide for runtime shape, module and dependency direction, providers, asynchronous behavior, compatibility, migration, recovery, and an implementation-ready handoff.

## Sections

- [Architecture Decisions and Runtime Shape](#architecture-decisions-and-runtime-shape)
- [Evolution, Readiness, and Build Handoff](#evolution-readiness-and-build-handoff)

## Architecture Decisions and Runtime Shape

#### 1. Start from the decision ladder

Inspect the current repo and contract before proposing a new layer. Prefer the first path that fulfills the
real boundary safely:

```text
standard library -> platform native -> existing repo capability -> small local helper
-> new dependency -> framework, service, or provider
```

For a proposed addition, state the failed lower-cost paths, the exact trigger, operating/maintenance cost,
security impact, deployment fit, ownership, exit path, and upgrade ceiling. A possible future need is not a
trigger.

| Addition | Minimum trigger |
|---|---|
| dependency | standard/native/existing capability cannot meet a named contract |
| abstraction | two actual implementations exist or a protected boundary needs one |
| provider | honest delivery requires its distinct capability |
| configuration | behavior truly varies by environment, user, plan, or operator policy |
| durable model | current storage cannot preserve/query/report the required lifecycle safely |
| async mechanism | request path cannot safely own duration, retry, concurrency, or recovery |

#### 2. Compare real architecture forks

Compare two or three approaches only when reasonable engineers could select different system shapes. Always include the current/native/minimal path. Include a more durable path only when its ceiling or exit value is
credible, not aspirational.
Keep the selected shape proportionate to the current slice. The absence of a trigger is
positive evidence for preserving the existing shape; future options belong in a revisit
trigger, not in the first implementation.

| Option | Repo fit | Contract coverage | Complexity | Operating cost | Reversibility | Proof burden | Ceiling and trigger |
|---|---|---|---|---|---|---|---|

Recommend one option in terms of approved product constraints and current evidence. State why rejected options
are not selected now, how they can be revisited, and whether user approval is needed. Do not force a comparison when one safe repo-conformant path is clearly required.

#### 2a. Calibrate decision confidence and approval

Use an architecture comparison to make a decision, not to create the appearance of
certainty. State whether the decisive evidence is confirmed, a bounded assumption, or
an unknown that has a named latest-safe decision point.

| Decision condition | Appropriate action |
|---|---|
| Current/native path satisfies the contract | Select it and record the trigger that would justify leaving it. |
| Two paths are viable but costs differ | Compare them against the active constraints and choose deliberately. |
| A material fact is unverified but reversible | Use a bounded default and define the observation that revisits it. |
| A material fact controls privacy, public behavior, cost, or irreversibility | Stop for evidence or required product/technical approval. |

Approval is not a generic ceremony. Request it when the decision commits meaningful
ongoing spend, user-visible compatibility, trust exposure, or a hard-to-reverse
topology. Record who can revise it and what evidence should trigger that review.

#### 3. Apply the low-cost indie baseline carefully

Existing repo conventions win unless unsafe, stale, or explicitly overridden. For an unconstrained greenfield
product, begin from the documented low-cost baseline:

| Layer | Baseline | Reconsider when |
|---|---|---|
| hosting/web | small Hetzner Ubuntu VPS, Nginx, PHP-FPM | hosting/control/compliance or traffic needs differ |
| backend/workers | vanilla PHP services/repositories, cron, Python tooling | repeated middleware/validation/auth or long work needs stronger support |
| realtime | vanilla Node.js only where request/response is the wrong fit | realtime or long-lived protocol is not actually needed |
| data | SQLite with PRAGMAs, backups, migrations | write contention, multi-instance, tenant/search/analytics pressure appears |
| frontend | vanilla CSS/JS | real shared state/components/routing or repo convention demands a build stack |
| edge/private admin | Cloudflare DNS/SSL/Tunnel and Tailscale | exposure, identity, or network policy demands a different boundary |
| paid/external | adapters for xAI, Stripe hosted flows, Cloudflare R2, OpenFreeMap when fit | product, compliance, capability, or exit requirements differ |

Consider Postgres for proven contention/multi-instance/analytics/search needs; a queue for retries, long jobs,
parallelism, or durable status; a framework for repeated routing/middleware/validation/auth; and split services
for proven isolation, reliability, scaling, or deployment-cadence needs. Record the condition that makes the
change necessary rather than using scale as a vague justification.

#### 4. Define module responsibilities and dependency direction

Use the smallest model already supported by the repository. Name only layers that exist or protect a real
boundary.

| Layer | Owns | May depend on | Must not own |
|---|---|---|---|
| UI/view | visible state and user intent | client contract | business truth or authorization enforcement |
| entry/controller | transport conversion and request boundary | service/domain | provider-specific policy |
| service/domain | use-case orchestration and invariants | repository/provider contract | transport/UI details |
| repository/data | persistence/query mapping | database/store | caller policy or external workflow |
| provider adapter | external normalization and credentials | provider SDK/protocol | product/business ownership |
| job/script/realtime process | scheduled/event lifecycle | service and adapter contract | duplicate domain rules |

State shared-module ownership, allowed dependency direction, duplicate-state risk, and the boundary that
prevents reverse dependencies. Do not introduce a framework merely to make this table look complete.
When repository conventions allow it, keep interface, types, behavior, and tests that
share one reason to change near the owning capability or module. Do not reorganize a
stable tree merely to impose feature folders; existing ownership and dependency
direction remain the stronger constraints.

#### 5. Describe runtime shape and observability points

For each non-trivial flow, choose the smallest useful view: context, sequence, data lifecycle, dependency
graph, or deployment boundary. A diagram earns its place when it explains a cross-module, async, provider, or
stateful flow faster than prose.

Trace only applicable paths:

```text
request or event -> validation -> authorization -> domain action -> data/provider -> result or async state
```

For each path, identify state ownership, sync/async boundary, consistency expectation, idempotency point,
safe correlation identifier, user-visible latency expectation, and recovery handoff. Add caches, queues,
realtime channels, or background processes only after their contract trigger is established.
For an asynchronous or provider path, make the handoff sequence explicit:
intent -> durable acceptance or rejection -> job/provider request -> status update or
callback -> visible completion, recoverable failure, or reconciliation.

Name which step owns the durable record, how duplicate delivery is recognized, which
boundary can time out, and what evidence links a user-visible result to the relevant
system action. If the workflow is synchronous, state why the request path can safely
own its duration and failure recovery.

| Runtime concern | Decide at system-design level |
|---|---|
| read path | source of truth, cache role, permission filter, and acceptable staleness |
| write path | validation, authorization, durable commit, conflict/duplicate boundary |
| async path | acceptance state, executor, retry owner, status visibility, reconciliation |
| callback path | verification, correlation identity, replay behavior, local state update |
| recovery path | safe retry, compensation/repair authority, and observable evidence |
| observability | correlation, meaningful event/log, failure signal, and owner who uses it |

#### 6. Check non-functional architecture proportionally

Evaluate latency, concurrency, rate/cost, availability, backup, privacy, operational burden, and distribution
only when the active contract makes them meaningful.
For a cross-boundary or high-risk decision, also check failure radius; a local,
reversible change does not need this analysis merely because the table contains it.

| Risk | Architecture question | Design response |
|---|---|---|
| latency | what waiting is visible or unsafe? | synchronous limit, async state, or honest progress contract |
| concurrency | which writes can collide or duplicate? | ownership, uniqueness, transaction, idempotency, or queue trigger |
| rate/cost | who can trigger expensive work and how often? | quota, entitlement, budget, or operator limit |
| availability | what fails when storage/provider/process is absent? | degraded behavior, retry owner, fallback, recovery |
| failure radius | what is the worst plausible failure, which users/data/systems are affected, can it cascade or expose a single point, and will it be detected? | isolation/containment boundary, degraded path, meaningful signal, and recovery owner |
| privacy | what data crosses a boundary or persists? | minimization, redaction, retention, access enforcement |
| distribution | how does a CLI/package/container/app reach users? | delivery owner or explicit deferral |

Do not turn this into Node05 test design or Node06 operating procedure. Define architectural obligations and
send proof and execution to their owners.

#### 7. Record ADR-lite decisions

Create an ADR-lite only for stack/framework, database/storage, auth/session/tenant model, paid provider,
public API, job/queue/cron, deploy boundary, module split, migration/deprecation, or a decision that is costly
to reverse. Skip local naming, helper placement, CSS, and other reversible details.

```text
Context -> decision -> options rejected -> evidence -> consequences -> cost and exit
-> compatibility -> revisit trigger -> approval state
```

Keep the current decision discoverable from the Architecture or Control Room region of the HTML project command
board; add a separate ADR artifact only when the user requests it or the rationale needs durable independent retrieval.
For each recorded decision, state the consequence for the next node: which contract or
module boundary becomes fixed, which cost or operational responsibility is accepted,
what compatibility constraint survives, and which evidence can reopen the choice. This
keeps an ADR-lite actionable instead of a technology diary.

## Evolution, Readiness, and Build Handoff

Turn the system design into a buildable architecture handoff when contracts, durable
data, providers, public behavior, or runtime topology must evolve. Keep this at the
system level: define compatibility, recovery, proof ownership, and slice boundaries;
do not turn it into a file-by-file implementation plan, test plan, QA ritual, or
deployment runbook.

#### 1. Classify the evolution

Classify every non-trivial change before assigning implementation order. A change can
belong to more than one class; use the highest-risk class to set its proof burden.

| Change class | Typical signal | System-design obligation |
| --- | --- | --- |
| Additive | A new optional capability or field | Preserve old behavior and name the new owner. |
| Transforming | Existing records or semantics change | Define old/new state, conversion, and repair. |
| Destructive | Data, behavior, or access is removed | Establish backup, compatibility window, and removal criterion. |
| Provider-state | A remote provider keeps related state | Define reconciliation, callback identity, and manual recovery. |
| Public contract | API, webhook, CLI, SDK, or export changes | Inventory consumers, compatibility, versioning, and communication. |
| Deprecation | A supported route is being retired | Define notice, fallback, adoption evidence, and end date or condition. |
| Topology/config | Runtime, secret, queue, domain, or deployment boundary changes | Define configuration ownership, rollback boundary, and operational evidence. |

Do not call a semantic replacement "additive" merely because its database migration
adds a column. Equally, do not invent a migration ceremony for a private, unpersisted
screen state that can safely reset.

#### 2. Define compatibility and recovery

For every transforming, destructive, provider-state, public-contract, deprecation, or
topology/config change, record the evolution statement before Build starts.

| Concern | Decide at Node02 | Hand off to later nodes |
| --- | --- | --- |
| Old and new state | What exists now, what success looks like after change, and what remains readable | Node03/04 implements the transition. |
| Consumer inventory | Users, jobs, integrations, admin tooling, docs, and providers affected | Node03/04 updates owned consumers; Node06 communicates or rolls out. |
| Compatibility window | Whether old and new inputs/outputs coexist, and for how long | Node03/04 preserves the defined path; Node06 enforces rollout timing. |
| Migration support | Backfill, lazy conversion, dual-read/write, or forward-only rationale | Node03 implements it; Node05/06 verifies the evidence appropriate to risk. |
| Recovery | Backup, dry run, idempotency, repair command/process, and manual owner | Node03/04 supplies mechanisms; Node06 performs operational controls. |
| Removal | Adoption or safety evidence required before deletion | Node06 authorizes execution after the stated criterion. |
| Fallback | User-visible fallback and safe behavior if conversion or provider state is incomplete | Node03/04 implements the designed behavior; Node05 evaluates it. |

For data transformations, specify whether a dry run, backup or export, idempotent
rerun, audit log, sample verification, or repair path is required. For provider state,
specify reconciliation source, retry owner, manual recovery authority, and evidence
that remote and local state agree. A forward-only change is acceptable only when its
irreversibility and recovery alternative are explicit.

This node designs the compatibility and recovery model. Node06 executes a rollout,
backup, switch, or rollback operation; it must not invent the model during release.

#### 3. Build design slices, not code plans

Split the design only where contracts, data dependencies, compatibility risk, or a
separate owner requires it. Each slice describes a coherent system change, not a list
of functions, components, commits, or test scripts.

| Slice field | Required statement |
| --- | --- |
| Capability and outcome | The capability it enables and the observable system outcome. |
| Owning module(s) | Which existing or planned boundary owns the behavior and state. |
| Upstream contract | The data, interface, permission, event, or provider contract it consumes. |
| Dependencies | Preconditions and whether the dependency is contractual or merely convenient. |
| Invariants | Conditions that must remain true during and after the slice. |
| Expected system state | The meaningful end state, including compatibility state where relevant. |
| Architecture proof obligation | The evidence category that must later establish the contract. |
| Stop or escalation condition | What observation invalidates this slice or requires Node02 re-entry. |

Order slices only when a real data, contract, or compatibility dependency exists.
Mark slices parallel only after checking that they do not mutate shared state, compete
for the same public contract, or make each other's evidence ambiguous. A slice without
an owner, input contract, expected state, and proof obligation is a placeholder, not a
handoff.

Map proof obligations to the later node that designs or produces the evidence. The
mapping is not a test plan and does not preselect a testing framework.

| Proof category | Typical evidence | Primary later owner |
| --- | --- | --- |
| Contract behavior | Observable API/action/event behavior and compatibility | Node03/04 implements; Node05 sets risk-based verification. |
| Browser flow | User can complete the designed path and see recoverable failures | Node04 implements; Node05 owns QA judgment. |
| Migration evidence | Dry-run, record counts, repair/retry behavior, and recovery evidence | Node03 implements; Node05/06 evaluates or executes by risk. |
| Security/privacy | Access denial, isolation, secret handling, and data exposure evidence | Node05 owns verification design and ship evidence. |
| Provider evidence | Sandbox or live confirmation, callback verification, reconciliation | Node03/04 implements; Node05 verifies the relevant path. |
| Load/observability | Meaningful limits, logs, metrics, alerts, or runtime signals | Node05 defines validation; Node06/07 operates and observes. |

#### 4. Run `implementation-readiness check` as readiness review

Keep the compatibility workflow id `implementation-readiness check`, but use it here as a
System Design readiness review. It checks whether Build can implement a known system,
not whether a file-level coding plan has been written.

Run it for M/L work, any public or durable-state change, provider integration,
permission model, migration, runtime boundary, or change that produced an ADR-lite.
For S work, use its questions proportionately; do not add ceremony when the change has
no meaningful system boundary.

1. Is the Node01 product handoff stable enough: user, first success path, scope,
   constraints, and acceptance are known?
2. Does repo evidence distinguish existing capability to reuse or extend from the
   genuinely new system responsibility?
3. Are the capability, data, interface, trust, state, failure, and recovery contracts
   sufficient that Node03/04 will not guess behavior?
4. Are material architecture choices justified by evidence, cost, exit path, and a
   concrete revisit trigger rather than "future scale"?
5. Does every required evolution have consumer inventory, compatibility window,
   recovery path, and removal criterion?
6. Are the affected architecture, module, API, and ADR-lite documents current without
   rewriting unrelated stable facts?
7. Does every design slice name owner, dependency, invariant, expected state, proof,
   and stop/escalation condition?
8. Does each unresolved decision name an owner, temporary assumption, latest safe
   decision point, and impact if it stays unresolved?

Set one readiness state:

| State | Meaning |
| --- | --- |
| `READY` | The system design is sufficiently decided for the requested Build scope. |
| `READY_WITH_NAMED_RISKS` | Build may proceed with explicit owners, bounds, and revisit points for remaining risk. |
| `BLOCKED` | A missing product, boundary, contract, trust, compatibility, or recovery decision makes Build guess. |
| `FAST_TRACK_ACCEPTED` | A deliberately small, reversible slice may skip non-applicable depth; record why and its limit. |

Fast track never waives a real payment, authentication, tenant isolation, private-data,
public-contract, destructive migration, or provider-trust concern. It only prevents a
local reversible change from impersonating a system design project.

#### 5. Persist and route the handoff

Update the affected Architecture, Technology/Contracts, or Control Room region of the HTML project command
board. Add or update an ADR-lite for a major, low-reversibility decision. Keep stable facts intact;
current-state documentation is evidence, not an invitation to rewrite the architecture.

Route from the readiness record according to the next unanswered question.

| Next need | Route | Node02 contribution |
| --- | --- | --- |
| Server/domain/data/provider implementation | Node03 | Contracts, module boundary, slices, and proof obligations. |
| User-facing flow or UI implementation | Node04 | User-visible state/failure semantics and browser-flow proof. |
| Test strategy, QA, or ship evidence | Node05 | Architecture proof map and named risks. |
| Deploy, rollout, migration execution, or rollback operation | Node06 | Compatibility/recovery design and removal criterion. |
| Operate and learn after release | Node07 | Observable outcomes, limits, and revisit triggers. |
| Product meaning or acceptance changed | Node01 | The evidence showing which product decision became invalid. |

#### 6. Re-enter architecture on evidence

Node03/04 returns here when implementation exposes contradictory contracts, an
unworkable module boundary, an unreachable runtime shape, or a dependency the design
did not account for. Node05 returns here when root-cause evidence says the system mode
or shared architecture is wrong, a critical failure cannot be repaired locally, or
three focused local fixes reveal the same shared-state or boundary problem. Node06
returns here when rollout, compatibility, or recovery design does not hold in reality;
it does not improvise a migration strategy while releasing.

Return with the observed evidence, current assumption, affected contracts, and the
smallest decision that must change. Do not reopen a settled architecture merely because
another option exists.
