# Browser Proof and Visual Debug

Use this guide to establish browser evidence for a user-visible frontend slice, diagnose rendering and integration failures, and hand quality reviewers direct observations rather than screenshot-only claims.

## Sections

- [Browser Proof, Visual Debug, and Handoff](#browser-proof-visual-debug-and-handoff)

## Browser Proof, Visual Debug, and Handoff

#### 1. Build a browser proof matrix

Start with the experience spine and changed contracts. Browser evidence complements
lint/type/build and component tests; it does not replace backend, security, or final QA
evidence.

| Proof area | Verify when relevant |
| --- | --- |
| primary flow | entry, comprehension, action, result, next action |
| visible states | loading, empty, validation, auth, denied, conflict, provider, success, stale/partial |
| interaction | form submit, dialog/menu, retry, filter, pagination, destructive confirmation |
| responsive | desktop plus narrow viewport, primary action, overflow, navigation, touch behavior |
| accessibility | keyboard path, focus-visible, labels, dialog focus, contrast/motion basics |
| integration | real backend or disclosed contract mock, safe error mapping, no private leakage |
| visual system | hierarchy, affordance, density, type/color/spacing consistency, real asset behavior |
| runtime | console errors, failed network requests, layout instability, relevant performance signal |

Use the strongest available path: browser manual, Playwright/Cypress, Storybook/sandbox,
component tests, lint/type/build, or static review. Record limitations rather than
claiming a screenshot proves an interactive flow.

#### 2. Reconnoiter rendered state before action

For a dynamic application, wait until the page has rendered and the relevant data/state
settles before inspecting DOM or choosing selectors. Then inspect the visible state,
screenshot or rendered structure, identify semantic selectors, and perform the target
action.

    navigate -> wait for usable rendered state -> inspect DOM/screenshot -> identify
    role/text/test selector -> interact -> inspect result, console, and network

Do not guess selectors from source when rendered content differs because of hydration,
auth, data, viewport, or pending state. Do not use arbitrary sleeps when a meaningful
render/network/element condition is available.

#### 3. Verify visible quality proportionally

Check the changed surface against its surface stance.

| Public/brand check | Operational/product check |
| --- | --- |
| thesis/promise/proof/CTA are clear in first scan | current state, decision context, and primary action are clear |
| real subject/product visual supports the claim | density and hierarchy support repeated scan/action |
| signature move serves subject rather than decoration | controls and rows are visibly actionable without hover |
| copy is specific and no fake metrics/claims appear | data, status, empty/error/recovery are honest |
| type/layout/motion support trust and mobile reading | focus, keyboard, filter/form/table/mobile behavior remains usable |

For every surface, examine navigation/wayfinding, action affordance, contrast, focus,
content noise, mobile priority, long text/overflow, actual image/media rendering, and
relevant status states. Take before/after screenshots when fixing a visual issue where
the difference is meaningful.

#### 4. Debug visual or interaction defects from evidence

When a frontend behavior or visual result is wrong:

1. Reproduce the exact state and record viewport, route, data/auth condition, and evidence.
2. Compare against the nearest working component, token, state, or interaction pattern.
3. Trace the issue through page, feature, primitive, state owner, data/mock, and CSS/token boundary.
4. State one hypothesis and make the smallest change that tests it.
5. Prefer CSS/token/layout fixes for visual issues when they preserve behavior; do not refactor unrelated code.
6. Re-run the same interaction/state and inspect screenshot, console, network, focus, and viewport result.

| Evidence says | Route |
| --- | --- |
| user job, primary action, acceptance, or positioning is wrong | Node01 |
| API/auth/error/permission/async contract is missing or contradictory | Node02 |
| backend or mock behavior is absent/incorrect | Node03 |
| local frontend cause is known | focused Node04 repair |
| cross-system QA, security, review, or ship judgment is needed | Node05 |
| rollout or deployed environment behavior is implicated | Node06 |

After three focused repair attempts that expose contradictory contracts, shared state,
or a system-wide design problem, stop and return to the owning upstream node. Do not
hide the fourth attempt inside a CSS override or component rewrite.

#### 5. Verify fresh evidence and hand off

A completion claim needs fresh evidence from the current slice.

| Claim | Fresh evidence |
| --- | --- |
| primary interaction works | browser/component test or safe manual flow with observed result |
| visual change is coherent | affected viewport/state screenshot or rendered inspection |
| responsive behavior works | narrow viewport check of primary action, overflow, and navigation |
| accessible interaction works | keyboard/focus/label observation for changed control |
| integration is honest | real endpoint or disclosed mock plus error/auth state evidence |
| no local runtime regression | relevant console/network and targeted lint/type/build/test result |
| docs are current | affected module/frontend/API HTML snapshot updated or consciously not needed |

Update docs only for durable frontend truth, following
`references/agent-context-html/instructions.md`. Hand Node05 the changed surface, upstream contracts, proof
matrix, commands/results, screenshots/observations, mock limitations, risks, and
unverified security/release facts.

Set one implementation status:

| Status | Meaning |
| --- | --- |
| BUILT | requested frontend slice and required local proof are complete |
| BUILT_WITH_NAMED_GAPS | implementation works locally; bounded browser/backend/QA facts remain |
| BLOCKED | a required contract, rendered state, environment, or proof is unavailable |
| NEEDS_NODE02_OR_03 | contract, backend, mock, or system boundary must be corrected |
| NEEDS_AUTHORIZATION | required browser/provider/environment action is not authorized |
