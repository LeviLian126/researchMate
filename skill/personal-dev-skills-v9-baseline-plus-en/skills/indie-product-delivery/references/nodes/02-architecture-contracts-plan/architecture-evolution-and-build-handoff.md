# Architecture Evolution and Build Handoff

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

## Turn uncertainty into the right kind of work

Do not force every unknown into an implementation ticket. Classify the work before sequencing it.

| Work type | Completion evidence |
|---|---|
| research | a bounded finding with sources, confidence, and the decision it unblocks |
| decision | a selected option, trade-off, owner, and reversal condition |
| prefactor | a behavior-preserving seam that makes the next slice safer to change |
| tracer bullet | one thin end-to-end path that proves the risky integration boundary |
| capability | user-visible or operator-visible behavior with acceptance and proof |
| migration | explicit old/new compatibility, data movement, switch, verification, and recovery |
| hardening | a named reliability, security, performance, or observability risk with a measurable gate |

Draw dependency edges only when one work item genuinely cannot be decided or verified before another. The resulting frontier is the work that can proceed now, not an excuse to create a large issue hierarchy. Keep research findings attached to the decision they serve, and keep implementation tickets free of unresolved product or architecture choices.
