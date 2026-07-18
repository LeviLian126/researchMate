# Product Discovery, Scope, and Acceptance

Use this guide to recover product truth, distinguish reversible defaults from founder decisions, set an appropriate ambition level, cut a credible MVP or MAP, and keep accepted scope synchronized for architecture and delivery.

## Sections

- [Discovery, Decisions, and Founder Ambition](#discovery-decisions-and-founder-ambition)
- [MVP Scope and Acceptance](#mvp-scope-and-acceptance)
- [Change Control, Output, and Handoff](#change-control-output-and-handoff)

## Discovery, Decisions, and Founder Ambition

#### 1. Recover product truth

1. Classify mode and inspect existing product docs, repo constraints, user goals, current evidence, and previous decisions.
2. Restate the current hypothesis: target user, pain/job, current workaround, promised outcome, first successful session, constraints, non-goals, and confidence.
3. If money, real users, pricing, demand, or competitors matter, apply Startup rigor even when the user calls it a side project. Offer a fast track only with named unresolved risks.

| Mode | Optimize for |
|---|---|
| Startup | demand, wedge, first revenue |
| Intrapreneurship | adoption, stakeholder value, durability |
| Builder | usefulness, delight, momentum |
| Hackathon/demo | clarity, wow path, demo script |
| Open-source/research | usefulness, maintainability, contribution path |
| Learning | teachable slice and learning outcome |

For a bootstrapped product, also recover runway/time budget, reachable first users, buyer versus user, support
capacity, recurring manual work, ongoing provider/content obligations, and the next evidence or revenue deadline.
Treat these as product constraints, not later implementation details.

Classify the current stage because it changes which unknowns deserve attention:

| Stage | Diagnostic focus | Do not overvalue |
|---|---|---|
| idea, no users | specific actor, painful status quo, narrowest test | market size and feature breadth |
| users, no revenue | observed behavior, repeated use, surprise, activation | signups and compliments |
| paying users | retention, expansion, willingness to lose the product, support economics | one-time purchases alone |
| internal product | sponsor outcome, adoption path, organizational durability | demo enthusiasm without ownership |
| builder/demo | delight, learning, shareable first success, time box | forced pricing or startup theater |

Ask only the stage-relevant questions not already answered. A later-stage product does not need to replay
idea-stage discovery unless its target user or promise has materially changed.

#### 2. Challenge the premise before collecting features

Run this stage for a new product, material feature, changed promise, pricing/business-model choice, or unclear problem. Skip it for approved local work.

1. Name the actual user or business outcome and test whether the request solves it or a proxy.
2. State what happens if nothing is built: observed loss, repeated workaround, missed revenue, trust harm, or no meaningful consequence.
3. Distinguish observed pain from inferred or hypothetical pain; attach evidence or a validation path.
4. Compare this work with the next-best use of founder attention and the cost of delay.
5. Check whether a manual service, changed process, configuration, existing capability, or narrower flow could deliver the same learning or outcome sooner.
6. Continue only with a one-sentence verdict: `Right problem`, `Right outcome, wrong framing`, `Evidence first`, `Not now`, or `Blocked`.

Do not turn this into automatic skepticism. Challenge once, recommend plainly, and let the founder decide unless the premise is unsafe, internally contradictory, or impossible to verify.

Use these forcing lenses selectively when the first answer remains vague:

| Lens | Force specificity toward | Warning signal |
|---|---|---|
| demand reality | payment, repeated use, workflow dependency, urgent request | interest, waitlist, likes, broad excitement |
| status quo | named workflow, workaround, time/money/trust cost | "nothing solves it" with no compensating behavior |
| desperate user | one role/person, situation, consequence, switching trigger | demographic or industry category only |
| narrowest wedge | one outcome deliverable in days, possibly without login or automation | platform required before any value exists |
| observation | unassisted use, confusion, workaround, unexpected behavior | demos, surveys, no surprises |
| future fit | specific change that makes the product more or less essential | category growth or generic AI tailwind |

Do not require all lenses. For an idea, prioritize demand/status quo/user; for active users, prioritize
status quo/observation/wedge; for paying users, prioritize observation/economics/future fit. For an internal
product, translate payment into sponsor commitment and durable ownership.

#### Diagnostic posture

1. Treat specificity as evidence of understanding, not as a performance test. Reframe a vague answer into
   the strongest concrete interpretation and ask whether it is accurate.
2. Separate the founder's pitch from users' own description and behavior. When they disagree, record the gap rather than averaging them together.
3. Name one recognizable failure pattern when present: solution seeking a problem, hypothetical user,
   interest mistaken for demand, platform-before-wedge, proxy metric, or perfection delaying observation.
4. Take a provisional position and state what evidence would change it. Avoid empty encouragement, but do not manufacture certainty or repeatedly push after the founder makes an informed decision.
5. Challenge the strongest version of the claim. If evidence supports the direction, move forward instead of continuing interrogation for its own sake.

#### 3. Ask only material questions

1. State confidence from 0-100%; below 70%, name the missing facts that change direction, scope, risk, or
   handoff.
2. Attach a current guess, option, or uncertainty to every question.
3. Ask one question when its answer changes the next question; batch up to eight only for broad scoping.
4. Use the shortest fitting mode:

| Mode | Use | Output |
|---|---|---|
| Hypothesis | start or new information | current read, confidence, gaps |
| Question-plus-guess | several material unknowns | question, guess, why, effect |
| Tradeoff | viable paths change product meaning | options, recommendation, decision |
| One-question | sensitive or single blocker | one focused question plus guess |
| Restate | confidence is high | user, problem, promise, first success, constraints, non-goals |

Ask roughly in this order unless context demands otherwise: mode, first user, problem, outcome, evidence, alternatives, switching trigger, first success, constraints, acceptance, non-goals, and handoff facts.

For a real tradeoff, ask with a compact decision brief:

```text
Decision: <what must be chosen>
Why it matters: <user/founder consequence>
Recommendation: <choice and reason>
Options: <2-3 choices with the decisive tradeoff>
After the answer: <what scope or next step changes>
```

Do not use this format for fact lookup or reversible local preferences. Ask consequential dependent decisions one at a time; batch only independent scoping facts.

If the user asks to move faster, identify the one or two unanswered questions most likely to change the build, ask them once, then proceed with explicit assumptions. If the user declines again, respect the decision unless a safety, payment, privacy, auth, deletion, or irreversible risk remains blocked.

#### 4. Decide ask, search, default, defer, reject, or block

Classify each choice by subject and judgment: product promise, user/buyer, pricing, validation, data/privacy, handoff, or local detail; then mechanical, taste, founder challenge, or one-way/high-magnitude.

| Action | Use when |
|---|---|
| Ask | choice changes promise, market, risk, handoff, or acceptance |
| Search | demand, competitors, pricing, category, or public pain matters |
| Default | detail is local, reversible, and not product-defining |
| Defer | valuable but unnecessary for first scope; add revisit trigger |
| Reject | no pain/outcome/test, contradiction, or misalignment |
| Block | ambiguity makes scope unsafe or fictitious |

Preserve the user's stated direction for a founder challenge unless evidence makes it unsafe, infeasible, or product-invalid. One-way/high-magnitude decisions require explicit approval. A requirement is ready only when this sentence can be completed:

```text
For <specific actor> in <specific situation>, this capability produces <observable outcome> because
<pain/business need>, and it can be verified by <acceptance criteria>.
```

Rank assumptions as `Must` (false means stop/pivot), `Should` (changes approach), or `Might` (useful later).
Every kept MVP item must support first success, test a Must assumption, or protect trust/safety/payment/privacy.

#### 5. Calibrate founder ambition for material plans

Skip this stage for copy/style changes, isolated bugs, approved S implementation, and reversible local detail.
For core workflow, target user, promise, pricing, business model, or meaningful M/L features:

1. Recover the real user/business outcome, current state, existing capabilities, founder runway/time, and cost of doing nothing.
2. Challenge whether this is the real problem, the shortest path, and a stronger use of founder attention than the next-best option.
3. Select one posture before candidate scope is generated:

| Posture | Use | Effect |
|---|---|---|
| Expand | explicit ambitious greenfield direction | describe a bold end-state; every addition remains opt-in |
| Selective expand | a feature may improve trust, differentiation, activation, revenue, or reusable leverage | keep baseline and offer a few high-leverage additions |
| Hold | approved scope, bug/refactor, or exploration is not useful | improve completeness without changing scope |
| Reduce | runway, validation speed, risk, or complexity makes the plan too large | keep the smallest credible first-success path |

4. Map `current state -> this slice -> 12-month ideal` only when long-term direction matters.
5. For a real product fork, compare two or three value-delivery paths rather than implementation architectures:
   reuse or process change, manual/concierge delivery, minimum product, or a more durable product path. Compare
   outcome coverage, learning speed, honesty of the promise, founder effort, reachability, recurring support,
   maintenance, and exit cost. Send technical design choices to Node02.
6. Frame additions by user outcome, founder leverage, effort, risk, maintenance, and validation value. Reject
   decoration, platform work without a near-term consumer, and generic feature accumulation.
7. Ask separately for scope-changing candidates. Send accepted items to MVP cutting, deferred items to a
   revisit trigger, and rejected items to non-goals.

Apply four founder decision lenses before recommending the posture:

- **Reversibility x magnitude:** move quickly on reversible choices; slow down for one-way, high-consequence
  promises, migrations, pricing, trust, or distribution commitments.
- **Inversion:** name what would make the product fail even if implementation succeeds.
- **Focus by subtraction:** identify the strongest thing not to build and the leverage gained by omitting it.
- **Narrative coherence:** ensure user, problem, promise, wedge, and this slice can be explained as one causal
  story without relying on an unrelated metric or future platform.

#### 6. Confirm or fast-track

Restate intent in the user's language. Require confirmation before final scope or Node02 handoff. If the user
chooses speed, list defaults, unresolved risks, and revisit triggers. Do not fast-track payments, PII, auth,
deletion, regulated data, irreversible actions, or production-risk requirements.

## MVP Scope and Acceptance

1. If the idea is broad or solution-first, generate three to five plausible product directions.
2. Compare only the lenses that resolve ambiguity: user value, evidence, feasibility, differentiation,
   validation speed, risk, and fit.
3. Select one direction; name alternatives, assumptions, and non-goals.
4. List candidate features, then keep only those required for first success, Must-assumption validation, or
   trust/safety/payment/privacy/permission.
5. Defer useful non-critical work with revisit triggers; reject work with no pain, outcome, test, alignment,
   or credible rationale.
6. Choose MVP versus Minimum Awesome Product based on trust, payment, privacy, public sharing, and credibility risk.
7. Map the end-to-end journey and expose gaps between kept features before writing isolated stories.
8. Write a specific user story and fail-able acceptance criteria for every kept item.
9. Include only relevant states: happy path, empty, validation, permission, persistence, entitlement,
   provider failure, trust/accessibility/visual requirement, activation, and verification.
10. Trace each kept item to first success, a Must assumption, a journey step, or a trust/risk obligation; cut
    orphan scope.
11. Ask the user to approve the cut before Node02.

### Slice boundary and decomposition

Before detailed criteria, decide whether the request is one coherent product slice:

1. Name the single observable outcome and the shortest continuous journey that produces it.
2. Split capabilities that serve a different actor, validate a different Must assumption, can ship or fail
   independently, or require a separate adoption motion.
3. Order slices by dependency and learning value. Complete the first independently valuable slice through
   scope and acceptance; record later slices without designing them prematurely.
4. Keep trust, safety, payment, permission, migration, or deletion work with the slice when it is required to make that slice honest and usable; do not mislabel it as optional polish.

Use this output when decomposition is needed:

| Slice | User outcome | Assumption tested | Depends on | Decision |
|---|---|---|---|---|
| first | independently usable value | riskiest relevant Must | minimum prerequisite | define now |
| follow-up | expands the first outcome | next uncertainty | first slice or evidence | defer with trigger |
| separate workstream | different actor/outcome | independent premise | none or external | route separately |

#### Narrowest-wedge pressure test

- Can one named user receive meaningful value this week without the eventual platform?
- Can setup, login, integration, automation, or self-service be replaced temporarily without making the
  promise dishonest?
- What is the one workflow or artifact the user would pay for, repeatedly use, or actively miss?
- If the narrow version has no value, is breadth truly necessary or is the outcome still unclear?
- Does the wedge lead naturally toward the intended product, or create disposable work and a misleading customer promise?

Minimum does not mean incomplete. The wedge must complete one real outcome and include the states needed for
trust. Reduce breadth before reducing integrity.

### Scope rules

| Decision | Rule |
|---|---|
| Keep | required for first success, Must validation, trust/safety/payment/privacy/permission, or validation method |
| Defer | useful later, second persona, heavy architecture, incumbent parity, manual-first possible, or Might assumption |
| Reject | no pain/outcome/test, contradictory promise, risk without learning, competitor-copy only, or unverifiable breadth |

### Ambition posture and candidate control

Carry the posture selected in discovery through the cut without silently drifting:

| Posture | Baseline behavior | Candidate treatment |
|---|---|---|
| Expand | describe the strongest coherent end-state and this slice's role in it | propose additions individually; none enter scope without approval |
| Selective expand | make approved baseline complete, then scan for a few high-leverage additions | state outcome, effort, risk, maintenance, and defer/skip option |
| Hold | preserve approved product meaning | add only missing completeness, trust, states, or acceptance |
| Reduce | preserve the core outcome while cutting breadth and commitments | separate must-ship-together from follow-up work |

For Expand or Selective expand, use three lenses before proposing candidates:

1. **10x experience:** what would make the user's outcome dramatically faster, clearer, safer, or more
   delightful without relying on implausible claims?
2. **Ideal product:** what should the user feel and understand if time were abundant and taste excellent?
   Describe experience before architecture.
3. **Small delight:** what low-cost detail removes anxiety, prevents a dead end, rewards progress, or makes the
   result worth sharing?

Distill the vision into concrete candidates. For each, record `Add now`, `Defer with trigger`, or `Skip`; do
not treat vivid language as approval. Limit the first pass to the few candidates with the highest leverage.
Platform potential is a benefit only when a near-term consumer exists.

For Hold, completeness means the approved journey has honest states and criteria, not that every imagined
edge case becomes scope. For Reduce, explicitly identify what can ship later and what must remain atomic for
the first outcome to work.

Manual or semi-manual delivery is valid only when the promise remains honest, privacy/consent is clear, and
the manual work tests the same value automation would provide.

### Journey and acceptance gate

Use only applicable stages, but mark intentional omissions rather than silently ignoring them:

| Stage | Confirm |
|---|---|
| trigger and entry | situation, expectation, acquisition/entry surface |
| setup or onboarding | minimum input, trust, permissions, time to value |
| first success | user action, system response, observable outcome |
| repeat use | saved state, return path, changed or stale data |
| interruption and recovery | resume, retry, provider/network failure, support path |
| entitlement or payment | limits, upgrade/downgrade, cancellation, honest access state |
| exit and deletion | export, deletion, revocation, retained obligations |

For each applicable stage, name the actor, entry state, action, visible result, failure behavior, and proof.
Then check the full journey for missing transitions, duplicate concepts, dead ends, and moments where the
public promise exceeds the delivered experience. Do not invent payment, accounts, retention, or deletion when
the product does not need them.

Interrogate the journey over time where relevant:

| Moment | Product question |
|---|---|
| first minute | Is the promise legible and can the user start without founder explanation? |
| first success | Does the user see, trust, and know what to do with the result? |
| interrupted use | Can the user safely leave, retry, resume, or recover? |
| second session | Is state understandable and is the return path obvious? |
| repeated use | What becomes faster, personalized, stale, noisy, or expensive? |
| weeks or months | What accumulates, expires, requires support, or increases switching cost? |

Resolve product decisions that implementation would otherwise guess later: ownership of saved state,
meaning of partial success, user-visible latency expectation, notification responsibility, retention promise,
and what happens when a dependency disappears. Leave storage, protocol, queue, and service choices to Node02.

```text
As a <specific user in a specific situation>, I want <capability>, so that <observable outcome>.

Given <state>, when <action>, then <observable result>.
```

## Change Control, Output, and Handoff

#### 1. Control scope changes

1. Quote the requested change and classify it: add, remove, modify, split, replace, defer, reject, or research.
2. Record the reason: user pain, business goal, stakeholder request, competitor evidence, technical
   constraint, or preference.
3. Assess product, UX, API/backend, data, auth/security, validation, release, docs, and ops impact.
4. Decide `Accept now`, `Defer`, `Reject`, `Split`, `Research first`, or `Block`.
5. If accepted, update scope, non-goals, stories, criteria, validation, handoff, and durable docs. If deferred
   or rejected, record rationale and revisit trigger.

| Decision | Use |
|---|---|
| Accept now | required for first success, trust/safety, or risk validation |
| Defer | useful but not MVP-critical; name revisit trigger |
| Reject | outside promise, unsupported by evidence, or contradictory |
| Split | narrow version now, broad version later |
| Research first | material decision lacks evidence |
| Block | safety/payment/privacy/auth/data ambiguity |

For material choices, maintain a lightweight decision ledger in the durable scope output:

| Decision | Status | Basis | Decided by | Product impact | Revisit trigger |
|---|---|---|---|---|---|
| concise choice | confirmed / defaulted / deferred / rejected / superseded | evidence or rationale | user / inferred default | affected promise, journey, or scope | event, date, or `never` |

Record only decisions another agent might otherwise reopen or misremember. Never label a model default as a
user decision; link superseded choices to the replacement rather than silently deleting history.

#### 2. Confirm progressively at the right depth

Do not wait until a long document is complete to discover that the product premise was misunderstood. Scale approval checkpoints to complexity:

| Complexity | Confirmation sequence |
|---|---|
| narrow, one decision | restate outcome, scope, and criterion once |
| material feature | confirm problem/premise, then scope/journey |
| new product or changed promise | confirm premise, value path, MVP cut, then final durable brief |
| sensitive or one-way decision | confirm the individual choice immediately before it becomes product truth |

At each checkpoint, summarize only what changed, the recommendation, rejected alternatives, and the next
decision. If the user corrects an early section, revise dependent assumptions before presenting later scope.
Approval of a premise is not approval of every feature candidate, and approval in chat is not proof that the
durable document is synchronized.

#### 3. Choose the lightest durable output

Use the existing HTML project command board, or create one at the user-requested/project-conventional location,
when product truth needs durable retrieval. Follow `references/agent-context-html/instructions.md`; keep chat as summary.

| Variant | Required content |
|---|---|
| Intent restate | mode, user, problem, first success, promise, constraints, non-goals, unresolved items |
| Scope brief | objective, user, MVP/MAP, out of scope, criteria, handoff notes |
| Full scope/PRD | decisions, evidence, assumptions, scope cut, stories, validation, handoff, risks |
| Requirement change | old/new scope, impact, decision, changed criteria, revisit trigger |
| Architecture handoff | surfaces, data, permissions, integrations, failures, analytics, open questions |
| Blocked scope | blocker, attempts, evidence, safe options |

For a full scope document, order sections as: decision summary, confirmed decisions, low-risk defaults,
evidence/uncertainty, MVP/MAP table, stories/criteria, validation, architecture handoff, blocked items, and
optional activity-journal link.

For a new product or material feature, include the applicable parts of this product brief:

| Section | Required product truth |
|---|---|
| problem and status quo | actor, situation, current workaround, observed cost, do-nothing consequence |
| demand and evidence | strongest supporting/opposing evidence, confidence, riskiest Must assumption |
| wedge and promise | first reachable user, narrow outcome, switching trigger, why this approach now |
| founder constraints | runway/time, acquisition path, support/manual load, provider or margin pressure |
| premises | concise statements explicitly confirmed, defaulted, or still disputed |
| approaches considered | materially different value-delivery paths and why the recommendation won |
| scope and journey | keep/defer/reject, non-goals, states, temporal behavior, criteria |
| distribution | how the first user receives value and who owns adoption |
| validation assignment | one real-world action, threshold, time box, and resulting decision |
| architecture handoff | surfaces, data concepts, roles, failures, analytics, constraints, open questions |

Do not create empty sections to appear complete. Omit inapplicable fields and state material omissions. For a
revised brief, identify what it supersedes and preserve changed decisions in the ledger.

#### 4. Review product consistency

Before handoff, make one adversarial pass over the product truth:

1. Check that target user, buyer, beneficiary, situation, pain, promise, and first success describe the same
   product rather than adjacent ideas.
2. Trace every kept item and criterion to the approved journey, Must assumption, or trust/risk obligation;
   reject orphan scope.
3. Check that scope, non-goals, pricing/entitlement, permissions, manual delivery, public claims, and validation
   method do not contradict one another.
4. Look for hidden expansion, undefined terms, missing transitions, unverifiable adjectives, and defaults
   presented as confirmed facts.
5. Resolve each finding, record it as an open decision, or block. Do not improve wording while leaving the
   underlying contradiction intact.

Run this once locally. A separate reviewer is optional for unusually consequential scope; do not create a
mandatory review loop or enlarge context for routine requirements.

Calibrate findings by implementation consequence:

| Severity | Meaning | Action |
|---|---|---|
| Blocker | two reasonable builders could create materially different products, or a contradiction makes the promise false | resolve or keep handoff blocked |
| Concern | a named uncertainty could alter scope, adoption, trust, or validation | record owner, assumption, and decision trigger |
| Advisory | wording, example, or future enhancement does not change the first implementation plan | improve if cheap; do not block |

Scan for `TODO`, `TBD`, placeholders, undefined adjectives, missing owners, and incomplete tables, but report
only gaps that matter. Never turn document symmetry or stylistic preference into a product blocker.

#### 5. Resolve open decisions and assignment

1. List unresolved product decisions separately from architecture questions. Give each an owner, latest safe
   decision time, temporary assumption, and impact if wrong.
2. Do not hide an unresolved choice inside prose or acceptance criteria. If implementation can safely proceed
   under a reversible default, mark `Ready with named risks`; otherwise mark `Blocked`.
3. End an evidence-limited Node01 cycle with one concrete founder action: observe, ask for commitment, deliver
   manually, test a CTA, recruit a named user, or measure an existing behavior.
4. Make the assignment small enough to complete in the stated time box and strong enough to change a
   decision. "Research more", "talk to users", and "think about pricing" are not assignments.
5. When the user explicitly accepts assumption-led building, define the earliest in-product event that will
   confirm or reject the assumption after release.

#### 6. Run the Node01 exit and Node02 handoff gate

Node01 is ready only when all applicable checks pass:

- actor, situation, pain/outcome, promise, and first success are explicit;
- founder constraints and non-goals bound the work;
- the riskiest Must assumption has evidence or a concrete decision rule;
- kept scope forms a coherent journey and every kept item has fail-able criteria;
- material product choices are explicitly approved, defaulted, or left open by name;
- pricing, trust, privacy, payment, permission, and manual-service assumptions are honest where applicable;
- consistency review has no hidden contradiction or silent expansion;
- Node02 can identify surfaces and open architecture questions without inventing product behavior.

Node02 must not guess target user, buyer, first success, promise, MVP/MAP boundary, capabilities, surfaces,
data objects/lifecycle, roles/permissions, payment/privacy assumptions, failure states, analytics/validation,
trust/safety requirements, criteria, or open architecture questions.

Use handoff state `Ready`, `Ready with named risks`, `Blocked`, or `Fast-track accepted`.

Before marking `Ready`, present the final product brief at the scale needed for review. Ask for explicit user
approval when the work creates a new product, changes the public promise, adds pricing/payment, changes a core
workflow, or resolves a disputed premise. For an approved narrow feature, a concise restatement and correction
window is enough. Never interpret silence as approval for a material scope change.
