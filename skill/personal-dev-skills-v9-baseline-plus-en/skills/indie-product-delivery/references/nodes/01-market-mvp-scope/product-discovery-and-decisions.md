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

Restate intent using the user's product vocabulary. Require confirmation before final scope or Node02 handoff. If the user
chooses speed, list defaults, unresolved risks, and revisit triggers. Do not fast-track payments, PII, auth,
deletion, regulated data, irreversible actions, or production-risk requirements.

## Traverse decisions by dependency, not by questionnaire order

Treat discovery as a changing decision graph. A useful question is not merely unanswered; its answer changes a later choice, the product boundary, or the evidence required to proceed. Keep four kinds of unknown separate so the user is not asked to do research the agent can do safely.

| Unknown | Owner | Action |
|---|---|---|
| repository, provider, competitor, price, standard, or current behavior that can be inspected | agent | research it and record the evidence before asking a dependent question |
| user goal, risk tolerance, taste, commercial intent, or acceptable trade-off | user | ask once the prerequisites are settled; include a recommendation and its main cost |
| knowledge held by a named stakeholder who is not present | stakeholder | prepare a short decision-oriented questionnaire; ask about the gap, not facts the sender already said they do not know |
| low-impact detail that does not change the current slice | later owner | default or defer it explicitly; do not let it block the frontier |

Ask the current frontier together only when the questions are independent. When one answer changes the meaning or available options of the next question, ask it first and recompute the frontier. A research lane may run in parallel without blocking unrelated user decisions, but downstream choices that depend on its result remain unsettled.

A good discovery question makes the decision easier. State the recommended default, the evidence behind it, the principal trade-off, and what new fact would reverse the recommendation. Avoid open-ended prompts such as “What do you want?” when the current evidence supports a bounded choice. Do not manufacture a false choice merely to move faster.

Stop interviewing when the remaining unknowns no longer change the smallest useful slice, acceptance, or an irreversible decision. Preserve them as named open decisions with an owner and re-entry condition instead of continuing until the document looks exhaustive.
