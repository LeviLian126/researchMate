# Experience Flow, Content, and States

> **Goal:** Recover the frontend surface, define its user job and experience spine, then design
> information architecture, content, and complete visible states around user decisions.
>
> **Owns:** experience discovery, experience spine, flow hierarchy, content quality, state ownership, visible-state coverage
>
> **Does NOT own:** visual direction (`visual-direction-and-design-system.md`), component architecture (`component-responsive-accessible-build.md`), content anti-patterns (`anti-default-directives.md`)

## Recover Approved Experience Truth

Read only the upstream handoff that defines the changed surface or contract. Identify target user,
context, job, primary action, success outcome, non-goals, acceptance, route/page, API/auth/error
behavior, and backend readiness or approved mock contract.

Verify every material fact against explicit product, system, or backend truth before building on it.
These must come from an approved source, never from inference:

- product promise and primary user
- permission behavior and private-data exposure
- billing / entitlement meaning
- destructive action consequence
- API error semantics
- visual repositioning

Naming, local component placement, minor layout details, and fixture data may use a reversible default
only when they are non-observable.

## Audit the Relevant Frontend Path

Inspect the affected route/page and its surrounding system. Do not load unrelated pages or redesign the
existing system because a nearby style looks dated. The goal is enough evidence to make one surface
correct and coherent.

| Area | Recover | Evidence to retain |
|---|---|---|
| route | entry, navigation context, deep-link behavior, current page owner | source path and working neighbor |
| UI system | tokens, primitives, icons, fonts, layout rules, responsive convention | local system to preserve |
| data | loader/query/client cache, contract mock, loading/error policy | API/backend or approved mock |
| access | auth/session rendering, role/tenant visibility, privacy-safe absence | server-backed behavior expected |
| interaction | form, dialog, destructive action, optimistic/retry convention | nearest working flow |
| verification | browser, screenshot, test, lint/type/build commands | strongest available path |
| docs | module/frontend page or HTML current-state surface | durable truth affected |

## Build the Experience Spine

Trace the slice from a user's situation to the next useful outcome:

> user and context -> entry -> comprehension -> primary action -> visible state/result
> -> recovery or trust signal -> next action

For each point in the spine, state concretely:

- **user/context:** role, urgency, knowledge, permission, device, entry condition
- **comprehension:** what they must recognize first and what may remain secondary
- **primary action:** one action that advances the current job
- **state/result:** loading, success, pending, error, empty, denied, stale, or partial behavior
- **recovery:** retry, edit, filter, sign in, upgrade, request access, contact, or safe exit
- **trust/next action:** proof, consequence, status, or next task visible after completion
- **proof:** smallest browser/component evidence that demonstrates the path

If two user jobs compete for first attention, return to Node01 rather than making both equally
prominent. If the UI cannot state a recovery because backend behavior is unknown, return to Node02/03.

## Flow and Hierarchy

Map entry, orientation, action, progress, result, recovery, and next action. Design for scanning: the
first reasonable action should be visible, related information grouped, and secondary material quiet
until it matters.

### Orientation questions

- What page/surface is this, where is the user, and what changed?
- What must be recognized in the first scan?
- Which action advances the active job now?
- Which actions support, defer, or safely reverse the main path?
- What result, cost, status, or next step follows?
- What can the user do after invalid input, denial, delay, or failure?
- How do they know current location, available options, and a safe exit?

Use conventions unless a justified improvement is demonstrably clearer. A link, button, row, tab, or
card must look actionable without hover. Do not bury essential information behind tours, forced
instructions, or decorative composition.

### Hierarchy by surface type

| Surface | Hierarchy rule |
|---|---|
| landing / public | one thesis, one dominant CTA, real proof before decorative feature inventory |
| onboarding | next useful step, progress/context, limited cognitive load, visible escape/retry |
| dashboard | decision/action first; metrics only when they change a decision |
| list / table | meaningful columns, filters, status, empty state, actionable rows, bounded density |
| form | intent, relevant fields, validation near input, submitted/pending/success state |
| transaction | consequence, amount/scope, confirmation, irreversible boundary, recovery |
| settings / admin | clear ownership, current configuration, safe defaults, explicit save/apply feedback |

Do not use equal cards as a substitute for hierarchy. Do not use fake metrics, invented precision,
dummy product screenshots, or decorative labels that do not encode true information.

## Content as Navigation

Visible text helps people act. Use user-recognized nouns and concrete verbs; retain one term for the
same action throughout the flow. A label labels, an example demonstrates, and a button states the
result of pressing it.

### Content moment quality

| Moment | Required quality |
|---|---|
| primary action | verb and consequence are explicit |
| loading / pending | explains what is happening only when waiting is meaningful |
| empty state | names the absence and gives a relevant next action |
| validation error | identifies what to correct without blame or vague apology |
| permission / auth | explains available recovery without exposing policy internals |
| success | confirms the completed action using the same vocabulary |
| destructive action | states scope and consequence before confirmation |
| long / generated text | remains readable, bounded, and recoverable when missing or malformed |

When the surface contains long-form help, explanation, or documentation, also apply the default
`human` skill. Keep short interface copy focused on the action and state instead of forcing it
through a long-form prose style.

### Content self-audit

Before completion, read all visible strings for: vague claims, AI-style filler, fake confidence,
inconsistent action names, unclear referents, forced metaphors, and unverified numbers. Rewrite toward
plain, functional language.

For specific content anti-patterns (generic names, AI cliches, fake numbers, passive voice), see
`anti-default-directives.md` Content section. Do not duplicate those checks here.

## State Ownership and Visible Coverage

Name state ownership before implementing components. The UI may present a state but must not reproduce
backend authorization, pricing, entitlement, provider, or conflict policy.

### State ownership

| State kind | Owner / default |
|---|---|
| local visual state | component or existing primitive |
| form draft and validation | form owner; preserve user input on recoverable failure |
| remote data | existing query/loader/cache owner |
| URL / filter / page state | route/search parameter owner |
| auth / session | server-backed session/identity rendering |
| permission / entitlement | contract-backed result, never inferred from hidden UI |
| optimistic state | explicit mutation owner with rollback/refresh behavior |
| derived state | computed from canonical local/remote state, not duplicated |
| cross-screen state | existing store/URL/server source only when needed |

### Visible-state coverage

Map every relevant contract to a visible state. If a state cannot be rendered, route the missing
semantics to Node02/03.

| Default | Loading | Empty | Validation | Permission | Auth | Conflict | Provider | Success | Partial/stale |
|---|---|---|---|---|---|---|---|---|---|
| normal task state | progress/skeleton/disabled | absence plus next step | preserved input and correction | privacy-safe recovery | sign-in/return path | refresh/retry/explain | pending/retry/reference | confirmed next action | honest freshness and repair path |

## Implementation Boundaries

Translate the flow into page, feature, primitive, hook, route, data, and content responsibilities that
match the repository. A component should own one visible job and its states; a page coordinates the
surface; data/auth code follows existing boundaries.

For a complex flow, identify what can be built with a contract mock and what waits for Node03. Make
mock status visible in the checkpoint, never silently turn it into a production assumption.

For component layer responsibilities, split rules, and cross-page visual block definitions, see
`component-responsive-accessible-build.md`.

---

**Acceptance criteria:** After reading this file, you can trace the experience spine from user context
to next action, assign state ownership for each contract, map every state to a visible-state coverage
entry, distinguish mock dependencies from Node03 dependencies, and audit visible content for clarity
and consistency.
