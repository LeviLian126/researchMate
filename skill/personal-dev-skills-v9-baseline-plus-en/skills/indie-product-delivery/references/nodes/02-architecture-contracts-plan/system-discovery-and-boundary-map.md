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
