# Market, Scope, and Acceptance

Use this when the present need is product-side: who the product serves, what it promises, whether it's worth building, how to price or position it, and what the smallest credible first slice is.

## Sections
- [Recover product truth](#recover-product-truth)
- [Challenge the premise](#challenge-the-premise)
- [Ask only material questions](#ask-only-material-questions)
- [Validate demand and wedge](#validate-demand-and-wedge)
- [Bootstrapped viability](#bootstrapped-viability)
- [Positioning and public trust](#positioning-and-public-trust)
- [Acceptance, scope control, and handoff](#acceptance-scope-control-and-handoff)

## Recover product truth

Inspect existing product docs, repo constraints, user goals, current evidence, and prior decisions; classify each fact by state (see `references/methods.md`). Then restate the current hypothesis in one pass: target user, pain or job-to-be-done, current workaround, promised outcome, first successful session, constraints, non-goals, and confidence. The point of restating is catching where you've been filling in blanks instead of finding evidence.

If money, real users, pricing, demand, or competitors are realistically in play, hold the bar of "startup rigor" even when the user calls it a side project — these change what's worth building. A "learning" or "builder-demo" stance is fine when it's the honest one; just name it and skip startup theater.

## Challenge the premise

Do this once for a new product, a material feature, a changed promise, a pricing/business-model choice, or an unclear problem. Skip it for approved local work — challenging approved work is friction, not rigor.

Name the actual user or business outcome and test whether the request solves it or a proxy. Ask what happens if nothing is built: a real loss, repeated workaround, missed revenue, trust harm — or no meaningful consequence. Distinguish observed pain from hypothesized pain, and attach evidence or a validation path. Compare against the next-best use of founder attention and the cost of delay. Check whether a manual service, changed process, configuration, existing capability, or narrower flow could deliver the same learning sooner. Then give a one-line verdict and let the founder decide unless the premise is unsafe, internally contradictory, or impossible to verify:

| Verdict | When |
|---|---|
| `Right problem` | the outcome and actor check out |
| `Right outcome, wrong framing` | the goal is real, the approach isn't |
| `Evidence first` | the gap is knowable and changes the decision |
| `Not now` | the cost of delay is low or attention is better spent elsewhere |
| `Blocked` | a needed decision, authority, or premise must resolve first |

When the first answer stays vague, forcing lenses turn a foggy claim specific. Don't require all of them.

| Lens | Force specificity toward | Warning signal |
|---|---|---|
| demand reality | payment, repeated use, workflow dependency, urgent request | interest, waitlist, likes, broad excitement |
| status quo | named workflow, workaround, time/money/trust cost | "nothing solves it" with no compensating behavior |
| desperate user | one role/person, situation, consequence, switching trigger | a demographic or industry category only |
| narrowest wedge | one outcome deliverable in days, possibly without login or automation | a platform required before any value exists |
| observation | unassisted use, confusion, workaround, unexpected behavior | demos, surveys, no surprises |
| future fit | a specific change that makes the product more or less essential | category growth, a generic AI tailwind |

For an idea, demand / status quo / desperate-user are usually enough; for active users, status quo / observation / wedge; for paying users, observation / economics / future fit. Don't manufacture certainty, and don't keep pushing after the founder makes an informed decision.

## Ask only material questions

State confidence 0–100%; below 70%, name the missing facts that would change direction, scope, risk, or handoff (the mechanism lives in `references/methods.md`). Attach a current guess to every question so the human is choosing between options, not filling a blank. Ask one question when its answer changes the next; batch only for broad scoping.

For a real tradeoff, use a compact decision brief rather than open-ended polling:

```text
Decision: <what must be chosen>
Why it matters: <user/founder consequence>
Recommendation: <choice and reason>
Options: <2-3 choices with the decisive tradeoff>
After the answer: <what scope or next step changes>
```

## Validate demand and wedge

Strength of evidence matters more than volume of evidence. Rank what you actually have:

| Strength | Evidence |
|---:|---|
| 1 | payment, renewal, pre-order, signed pilot, budget |
| 2 | repeated workaround, support issue, churn complaint, painful migration |
| 3 | observed workflow or past-behavior interview |
| 4 | competitor traction, pricing, hiring, logos, category growth |
| 5 | landing conversion, demo request, waitlist, signup |
| 6 | survey preference, compliments, likes |

Read it in three layers:

| Layer | Question |
|---|---|
| established pattern | What reliably works in this category, and why? |
| current evidence | What are products, users, pricing, reviews, and failures showing now? |
| first principles | Where might convention be solving an old constraint or serving a different segment? |

Choose a validation action with a decision rule — the strongest evidence you can gather for the cost, tied to a named decision it would change. Don't run a landing page or survey as theater; only when its result changes whether to build.

## Bootstrapped viability

For a bootstrapped product, recover these as product constraints, not later implementation details: runway or time budget, reachable first users, buyer versus user, support capacity, recurring manual work or ongoing provider/content obligations, and the next evidence or revenue deadline. Each one, if unknown, is a named risk — not a detail to sort out after launch.

## Positioning and public trust

Positioning tightens when it's about to become public. Before a surface ships, name what it must carry:

| Surface signal | Required handoff |
|---|---|
| new landing/public page | promise, audience, proof, trust objections, visual-world brief |
| generic or untrusted redesign | positioning gap and preservation constraints |
| pricing/conversion | buyer anxiety, value proof, packaging promise |
| brand/logo | category, audience, metaphor, visual world, misuse boundaries |
| "make it premium" | what premium means for this segment and decision |

## Acceptance, scope control, and handoff

Write acceptance as behavior that can succeed or fail — observable, not aspirational. Scope control distinguishes reversible defaults (record and move on) from founder decisions (explicit, because reversing them costs social or product capital). When a requirement changes, name what it relaxes, what it tightens, and what already-built work it affects.

Hand off the agreed slice, its acceptance, non-goals, named risks/unknowns, and the evidence behind each. Product truth heading into a contract or implementation decision should be `confirmed`, not `inferred` pretending to be settled.
