# Browser Proof and Debug

> **Goal:** Establish browser evidence for a user-visible frontend slice, diagnose rendering and
> integration failures, and hand quality reviewers direct observations rather than screenshot-only claims.
>
> **Owns:** proof matrix (including multi-resolution), hermetic browser proof, rendered-state reconnaissance, debug workflow, escalation routing, status contract
>
> **Does NOT own:** anti-pattern checklist (`anti-default-directives.md`, but references it for pre-flight)

## Browser Proof Matrix

Start with the experience spine and changed contracts. Browser evidence complements lint/type/build
and component tests; it does not replace backend, security, or final QA evidence.

### Proof areas

| Proof area | Verify when relevant |
|---|---|
| primary flow | entry, comprehension, action, result, next action |
| visible states | loading, empty, validation, auth, denied, conflict, provider, success, stale/partial |
| interaction | form submit, dialog/menu, retry, filter, pagination, destructive confirmation |
| responsive | desktop + at least 3 mobile resolutions (360px / 390px / 768px); each checks: primary action visible, no component stacking, no horizontal overflow, touch targets >= 44x44 CSS px, fixed/sticky not covering content, navigation reachable |
| accessibility | keyboard path, focus-visible, labels, dialog focus, contrast/motion basics, touch target spacing (adjacent interactive elements >= 8px apart) |
| integration | real backend or disclosed contract mock, safe error mapping, no private leakage |
| visual system | hierarchy, affordance, density, type/color/spacing consistency, real asset behavior |
| runtime | console errors, failed network requests, layout instability, relevant performance signal |

### Multi-resolution responsive proof

Narrow viewport is not a single value. The responsive proof area must cover at minimum:

| Breakpoint | Device | Checks |
|---|---|---|
| 360px | small Android | primary action visible, no stacking, no overflow, touch targets, fixed/sticky coverage, nav reachable |
| 390px | standard iPhone | same checks + form fields usable with keyboard, dialog/sheet viewport safety |
| 768px | tablet portrait | same checks + layout transitions correct (sidebar/drawer), grid reflow, table horizontal scroll |

Record which breakpoints were tested and how (Playwright/Cypress automated, DevTools manual, real
device). A single "tested on mobile" claim without specifying viewport width is insufficient.

### Strongest available path

Use the strongest available path: browser manual, Playwright/Cypress, Storybook/sandbox, component
tests, lint/type/build, or static review. Record limitations rather than claiming a screenshot proves
an interactive flow.

## Hermetic Browser Proof

Make an automated browser run own its server process, port, build-output directory, and fixture state.
Use deterministic local/demo data for product journeys unless the selected proof explicitly requires an
authorized deployed boundary. Keep its build output separate from an already running development
server, and clean up only processes the run started.

### Fail conditions

Fail the run on:

- uncaught page errors
- relevant console errors
- failed required requests
- unexpected external network requests

Maintain a narrow allowlist when an external asset or endpoint is part of the declared test boundary.
Do not let a test pass by silently falling back to a real cloud service, remembered browser session, or
developer machine state.

### Coverage

Cover the result and the state transition around a critical journey: navigation or route, visible
outcome, persistence or refresh behavior when relevant, and a recovery/error path. Prefer traces,
screenshots, and video on failure; retain always-on artifacts only when they serve a defined audit need.

## Reconnoiter Rendered State

For a dynamic application, wait until the page has rendered and the relevant data/state settles before
inspecting DOM or choosing selectors.

> navigate -> wait for usable rendered state -> inspect DOM/screenshot -> identify
> role/text/test selector -> interact -> inspect result, console, and network

Do not guess selectors from source when rendered content differs because of hydration, auth, data,
viewport, or pending state. Do not use arbitrary sleeps when a meaningful render/network/element
condition is available.

## Verify Visible Quality Proportionally

Check the changed surface against its surface stance.

### Public / brand check

- thesis/promise/proof/CTA are clear in first scan
- real subject/product visual supports the claim
- signature move serves subject rather than decoration
- copy is specific and no fake metrics/claims appear
- type/layout/motion support trust and mobile reading

### Operational / product check

- current state, decision context, and primary action are clear
- density and hierarchy support repeated scan/action
- controls and rows are visibly actionable without hover
- data, status, empty/error/recovery are honest
- focus, keyboard, filter/form/table/mobile behavior remains usable

For every surface, examine navigation/wayfinding, action affordance, contrast, focus, content noise,
mobile priority, long text/overflow, actual image/media rendering, and relevant status states. Take
before/after screenshots when fixing a visual issue where the difference is meaningful.

## Debug Visual or Interaction Defects

When a frontend behavior or visual result is wrong:

1. **Reproduce** the exact state and record viewport, route, data/auth condition, and evidence.
2. **Compare** against the nearest working component, token, state, or interaction pattern.
3. **Trace** the issue through page, feature, primitive, state owner, data/mock, and CSS/token boundary.
4. **State** one hypothesis and make the smallest change that tests it.
5. **Prefer** CSS/token/layout fixes for visual issues when they preserve behavior; do not refactor
   unrelated code.
6. **Re-run** the same interaction/state and inspect screenshot, console, network, focus, and viewport
   result.

### Escalation routing

| Evidence says | Route |
|---|---|
| user job, primary action, acceptance, or positioning is wrong | Node01 |
| API/auth/error/permission/async contract is missing or contradictory | Node02 |
| backend or mock behavior is absent/incorrect | Node03 |
| local frontend cause is known | focused Node04 repair |
| cross-system QA, security, review, or ship judgment is needed | Node05 |
| rollout or deployed environment behavior is implicated | Node06 |

When a repair path stops producing new information or exposes a contradictory contract, shared state,
or system-wide design problem, try another hypothesis, route, or evidence source, then return to the
owning upstream node when the issue is no longer local. Do not hide a dead loop inside CSS overrides or
component rewrites.

## Verify Fresh Evidence and Hand Off

A completion claim needs fresh evidence from the current slice. Run the pre-flight checklist from
`anti-default-directives.md` before claiming completion.

### Fresh evidence requirements

| Claim | Fresh evidence |
|---|---|
| primary interaction works | browser/component test or safe manual flow with observed result |
| visual change is coherent | affected viewport/state screenshot or rendered inspection |
| responsive behavior works | narrow viewport check at 360px, 390px, AND 768px of primary action, overflow, stacking, and navigation |
| accessible interaction works | keyboard/focus/label observation for changed control |
| integration is honest | real endpoint or disclosed mock plus error/auth state evidence |
| no local runtime regression | relevant console/network and targeted lint/type/build/test result |
| docs are current | update the project board or another durable document when the changed behavior is durable; otherwise record why no document changed |
| no anti-patterns | pre-flight checklist from `anti-default-directives.md` passes all applicable boxes |

### Status contract

Set one implementation status:

| Status | Meaning |
|---|---|
| BUILT | requested frontend slice and required local proof are complete |
| BUILT_WITH_NAMED_GAPS | implementation works locally; bounded browser/backend/QA facts remain |
| BLOCKED | a required contract, rendered state, environment, or proof is unavailable |
| NEEDS_NODE02_OR_03 | contract, backend, mock, or system boundary must be corrected |
| NEEDS_CREDENTIALS_OR_ENVIRONMENT | required browser/provider/environment proof cannot run because a credential or environment is unavailable |

### Handoff package

Hand Node05 the changed surface, upstream contracts, proof matrix, commands/results,
screenshots/observations, mock limitations, risks, and unverified security/release facts.

## Prove the Rendered Contract, Not Only the Screenshot

A screenshot can show hierarchy and layout at one moment, but it cannot prove keyboard behavior,
network failure, stale state, refresh recovery, deep links, repeated actions, or console cleanliness.
Pair visual evidence with the relevant interaction, console, network, URL, and persistence checks.
Capture the smallest evidence that explains a defect without turning the browser session into an
unstructured tour.

## Preserve a Reproducible Path

Record the route, state, viewport, account or fixture boundary, and relevant build identity for any
visual defect or proof that another engineer must reproduce. Avoid screenshots with no context.

Re-run comparisons against the same route, data state, account boundary, and viewport whenever the proof
is meant to show a before/after change. If any of those inputs changed, say so and treat the observation
as a different case. This avoids crediting a CSS or component fix for a result actually caused by
different data, permissions, feature flags, caching, or deployment identity. Use the same locale and
time assumptions when they affect rendering.

---

**Acceptance criteria:** After reading this file, you can construct a proof matrix (including
multi-resolution testing at 360/390/768), run a hermetic browser proof, use the 6-step debug workflow,
route to the correct upstream node when blocked, and produce a status-claimed handoff with fresh
evidence including pre-flight checklist results.
