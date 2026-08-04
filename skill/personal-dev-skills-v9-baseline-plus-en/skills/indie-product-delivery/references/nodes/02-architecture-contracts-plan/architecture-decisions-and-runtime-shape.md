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

## Design twice at low-reversibility boundaries

For a public contract, durable data model, security boundary, module boundary, or provider commitment that will be costly to reverse, compare at least two feasible shapes before selecting one. This is not a ceremony for routine implementation details. It is a way to expose hidden assumptions while change is still cheap.

Use the same comparison frame for each candidate: ownership, dependency direction, state location, failure isolation, compatibility, migration cost, operational burden, test seams, and the simplest evidence that would invalidate the design. Reject decorative alternatives that differ only in naming or library choice.

Prefer the design that makes the important policy explicit and keeps volatile mechanisms behind a narrow interface. A deep module is useful when a small surface hides a coherent amount of complexity; it is harmful when the small surface merely conceals unrelated responsibilities. Keep the selected design close to the current need and record the condition that would justify the more elaborate alternative later.
