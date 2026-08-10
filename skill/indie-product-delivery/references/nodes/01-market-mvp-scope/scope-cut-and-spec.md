# Scope Cut and Spec

Take the completed discovery and cut it to the smallest product that tests the
riskiest hypothesis. Then write the spec Node02 will consume.

## MVP inclusion rule

A feature enters the MVP only when at least one is true:

1. Without it, the core job cannot be completed.
2. Without it, the riskiest assumption cannot be tested.
3. Without it, the product is unsafe, illegal, or untrustworthy.
4. Without it, measured user behavior would be misleading.

If a feature satisfies none, it goes to out-of-scope or non-goals.

## Scope-cut grilling

For each candidate feature, ask:

> If this is removed, can the user still complete the core job?

- Yes: out of scope, possibly later.
- No, but a manual workaround exists: out of scope, use the workaround.
- No and no workaround: in scope.

Then ask:

> Does this feature introduce a new user type, platform, data type, integration, or
> business model?

If yes, reconsider. It may be scope leakage that expands the product boundary.

Prefer temporary manual operations, one platform, one language, one workflow, and
controlled onboarding when these choices preserve the tested value proposition. Do
not fake trust, safety, privacy, legal, payment, or irreversible data behavior.

## Write the spec

Synthesize the grilling into the following document. Keep sections concise when
evidence is thin. Do not fill space with generic language.

```markdown
# Product Spec: [Name]

## Problem statement
Who, what pain, how they cope today, why solve this now.

## Target audience
### Primary audience
Behavior: situation, frequency, severity, current alternative, reachable channel.
### Excluded audience
Explicitly not supported.

## Core user journey
Trigger -> entry -> required input -> core action -> result -> user next step ->
return loop.

A core flow is incomplete if it produces output but does not help the user act,
decide, save, share, recover, or return.

## Alternatives and differentiation
| Alternative | What it covers | Why users have not switched | Our difference |
|---|---|---|---|

Write the differentiation as a specific trade-off, not "AI-powered" or "simpler."

## Scope
### In scope
Each feature with the inclusion rule it satisfies (1, 2, 3, or 4).
### Out of scope (this version)
Features deferred. Each with a revisit trigger: what event or evidence would bring
it back.
### Non-goals
What the product is intentionally not becoming. Use non-goals to prevent scope drift.

## Acceptance criteria
1. [Testable, pass/fail condition]
2. [...]

No "works correctly" or "handles edge cases." State the observable behavior.

## Risk assumptions
| Assumption | What happens if false | Cheapest test |
|---|---|---|

## Decision
- [ ] GO: proceed to Node02 for architecture design
- [ ] VALIDATE: run the cheapest test first (name it)
- [ ] NO_GO: current evidence does not support continuing
```

## Requirement changes

When the user changes a requirement during Node01, do not classify the change. Ask
which already-decided items it affects: audience, core journey, or scope. Re-grill
only the affected parts. Update the spec. Keep it simple.

## What not to do

- Do not include a feature without naming which inclusion rule it satisfies.
- Do not list "fast," "easy," "secure," or "intuitive" as requirements. Replace with
  measurable or observable conditions.
- Do not prescribe architecture in the spec. State the job and the constraints.
- Do not leave acceptance criteria subjective.
- Do not skip non-goals. Without them, scope drifts silently.
