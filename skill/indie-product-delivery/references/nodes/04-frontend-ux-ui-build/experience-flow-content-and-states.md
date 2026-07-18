# Experience Flow, Content, and States

Use this guide to recover the actual frontend surface, define its user job and experience spine, then design information architecture, content, and complete visible states around user decisions rather than generic layout patterns.

## Sections

- [Frontend Discovery and Experience Frame](#frontend-discovery-and-experience-frame)
- [Flow, Information Architecture, Content, and State](#flow-information-architecture-content-and-state)

## Frontend Discovery and Experience Frame

#### 1. Recover approved experience truth

Read the Node01/02/03 handoff and identify target user, context, job, primary action,
success outcome, non-goals, acceptance, route/page, API/auth/error behavior, and
backend readiness or approved mock contract.

| Fact state | Meaning | Build treatment |
| --- | --- | --- |
| confirmed | explicit product/system/backend truth | implement it |
| defaulted | reversible local detail within an existing convention | record briefly |
| inferred | likely from nearby UI or code but not contract truth | verify or constrain |
| unknown | missing, conflicting, or unsupported fact | stop or route upstream |

Never default product promise, primary user, permission behavior, private-data exposure,
billing/entitlement meaning, destructive action consequence, API error semantics, or
visual repositioning. Naming, local component placement, minor layout details, and
fixture data may be defaulted only when they are reversible and non-observable.

#### 2. Audit the relevant frontend path

Inspect the affected route/page, shell/navigation, nearest components, style/token
source, data loading/cache pattern, form handling, auth rendering, error mapper,
existing tests/stories, dev-server/browser path, docs, and active changes.

| Area | Recover | Evidence to retain |
| --- | --- | --- |
| route | entry, navigation context, deep-link behavior, current page owner | source path and working neighbor |
| UI system | tokens, primitives, icons, fonts, layout rules, responsive convention | local system to preserve |
| data | loader/query/client cache, contract mock, loading/error policy | API/backend or approved mock |
| access | auth/session rendering, role/tenant visibility, privacy-safe absence | server-backed behavior expected |
| interaction | form, dialog, destructive action, optimistic/retry convention | nearest working flow |
| verification | browser, screenshot, test, lint/type/build commands | strongest available path |
| docs | module/frontend page or HTML current-state surface | durable truth affected |

Do not load unrelated pages or redesign the existing system because a nearby style
looks dated. The goal is enough evidence to make one surface correct and coherent.

#### 3. Build the experience spine

Trace the slice from a user's situation to the next useful outcome:

    user and context -> entry -> comprehension -> primary action -> visible state/result
    -> recovery or trust signal -> next action

| Spine point | Required statement |
| --- | --- |
| user/context | role, urgency, knowledge, permission, device, entry condition |
| comprehension | what they must recognize first and what may remain secondary |
| primary action | one action that advances the current job |
| state/result | loading, success, pending, error, empty, denied, stale, or partial behavior |
| recovery | retry, edit, filter, sign in, upgrade, request access, contact, or safe exit |
| trust/next action | proof, consequence, status, or next task visible after completion |
| proof | smallest browser/component evidence that demonstrates the path |

If two user jobs compete for first attention, return to Node01 rather than making both
equally prominent. If the UI cannot state a recovery because backend behavior is
unknown, return to Node02/03.

#### 4. Classify the surface before choosing style

| Surface | Primary design responsibility | Default visual stance |
| --- | --- | --- |
| public/brand | promise, trust, comprehension, conversion | distinctive but product-grounded direction |
| onboarding | first success and confidence | guided, low-friction, progressively disclosed |
| dashboard/operations | decision, scan, repeated action | quiet utility, truthful density, explicit hierarchy |
| form/transaction | intentional input and consequence | unambiguous action, preserved input, safe recovery |
| docs/current-state | finding current truth | structured navigation, evidence, restrained presentation |
| existing redesign | preserve working value while improving clarity | audit first, style second |

Public and brand surfaces may earn a strong signature move, real visual assets, or
conditional visual variants. Operational surfaces earn clarity, affordance, density,
and error recovery before spectacle. Do not apply landing-page art direction to a
high-frequency admin workflow.

#### 5. Map existing leverage and scope

For each sub-problem, mark reuse, extend, replace, or new. Prefer existing route,
primitive, token, pattern, data hook, state component, accessibility helper, or test
over parallel structure.

| Field | Required statement |
| --- | --- |
| outcome | observable user behavior being changed |
| existing leverage | component/system/path to reuse or extend |
| keep | brand, route, analytics, form, accessibility, or interaction facts protected |
| non-goals | related work deliberately excluded |
| proof | browser/component/command evidence needed |
| side-effect limit | auth, data, provider, analytics, external link, or deploy boundary |
| escalation | fact that requires Node01, Node02, Node03, or Node05 |

A screenshot, Figma frame, export, or prototype is a candidate input, never an
authority above product scope, system contracts, existing accessibility, or repo truth.

## Flow, Information Architecture, Content, and State

#### 1. Define the user flow and hierarchy

Map entry, orientation, action, progress, result, recovery, and next action. Design for
scanning: the first reasonable action should be visible, related information grouped,
and secondary material quiet until it matters.

| Question | Required answer |
| --- | --- |
| orientation | what page/surface is this, where is the user, and what changed? |
| first understanding | what must be recognized in the first scan? |
| primary action | which action advances the active job now? |
| secondary action | which actions support, defer, or safely reverse the main path? |
| consequence | what result, cost, status, or next step follows? |
| recovery | what can the user do after invalid input, denial, delay, or failure? |
| wayfinding | how do they know current location, available options, and a safe exit? |

Use conventions unless a justified improvement is demonstrably clearer. A link, button,
row, tab, or card must look actionable without hover. Do not bury essential information
behind tours, forced instructions, or decorative composition.

#### 2. Compose information architecture by mental model

Organize content around what users recognize and control, not database tables, API
fields, component boundaries, or prototype rectangles. Landing/public pages prioritize
segment, painful situation, promise, proof, CTA, objections, and trust. Operational
surfaces prioritize current state, decision context, action, exception, and follow-up.

| Surface | Hierarchy rule |
| --- | --- |
| landing/public | one thesis, one dominant CTA, real proof before decorative feature inventory |
| onboarding | next useful step, progress/context, limited cognitive load, visible escape/retry |
| dashboard | decision/action first; metrics only when they change a decision |
| list/table | meaningful columns, filters, status, empty state, actionable rows, bounded density |
| form | intent, relevant fields, validation near input, submitted/pending/success state |
| transaction | consequence, amount/scope, confirmation, irreversible boundary, recovery |
| settings/admin | clear ownership, current configuration, safe defaults, explicit save/apply feedback |

Do not use equal cards as a substitute for hierarchy. Do not use fake metrics, invented
precision, dummy product screenshots, or decorative labels that do not encode true
information.

#### 3. Write content as navigation

Visible text helps people act. Use user-recognized nouns and concrete verbs; retain one
term for the same action throughout the flow. A label labels, an example demonstrates,
and a button states the result of pressing it.

| Content moment | Required quality |
| --- | --- |
| primary action | verb and consequence are explicit |
| loading/pending | explains what is happening only when waiting is meaningful |
| empty state | names the absence and gives a relevant next action |
| validation error | identifies what to correct without blame or vague apology |
| permission/auth | explains available recovery without exposing policy internals |
| success | confirms the completed action using the same vocabulary |
| destructive action | states scope and consequence before confirmation |
| long/generated text | remains readable, bounded, and recoverable when missing or malformed |

Before completion, read all visible strings for vague claims, AI-style filler, fake
confidence, inconsistent action names, unclear referents, forced metaphors, and
unverified numbers. Rewrite toward plain, functional language.

#### 4. Assign state ownership and visible coverage

Name state ownership before implementing components.

| State kind | Owner/default |
| --- | --- |
| local visual state | component or existing primitive |
| form draft and validation | form owner; preserve user input on recoverable failure |
| remote data | existing query/loader/cache owner |
| URL/filter/page state | route/search parameter owner |
| auth/session | server-backed session/identity rendering |
| permission/entitlement | contract-backed result, never inferred from hidden UI |
| optimistic state | explicit mutation owner with rollback/refresh behavior |
| derived state | computed from canonical local/remote state, not duplicated |
| cross-screen state | existing store/URL/server source only when needed |

Map every relevant contract to a visible state.

| Default | Loading | Empty | Validation | Permission | Auth | Conflict | Provider | Success | Partial/stale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal task state | progress/skeleton/disabled behavior | absence plus next step | preserved input and correction | privacy-safe recovery | sign-in/return path | refresh/retry/explain | pending/retry/reference | confirmed next action | honest freshness and repair path |

The UI may present a state but must not reproduce backend authorization, pricing,
entitlement, provider, or conflict policy. Route missing semantics to Node02/03.

#### 5. Prepare implementation boundaries

Translate the flow into page, feature, primitive, hook, route, data, and content
responsibilities that match the repository. A component should own one visible job and
its states; a page coordinates the surface; data/auth code follows existing boundaries.

For a complex flow, identify what can be built with a contract mock and what waits for
Node03. Make mock status visible in the checkpoint, never silently turn it into a
production assumption.
