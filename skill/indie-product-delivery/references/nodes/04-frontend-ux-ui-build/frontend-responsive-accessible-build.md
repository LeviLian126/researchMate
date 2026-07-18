# Frontend Responsive and Accessible Build

Use this guide while implementing or refactoring production frontend code, including component boundaries, complete interaction states, responsive behavior, accessibility, motion performance, and reusable visual blocks.

## Sections

- [Frontend Component, Responsive, and Accessible Build](#frontend-component-responsive-and-accessible-build)

## Frontend Component, Responsive, and Accessible Build

#### 1. Use existing implementation boundaries

Recover repository naming, folders, primitives, data client, form convention, tokens,
icons, styling approach, lint/type/build commands, and nearest working feature. Extend
the smallest suitable owner.

| Layer | Owns | Must not own |
| --- | --- | --- |
| page/route | surface coordination, route state, composition, high-level loading boundary | duplicated backend policy or reusable primitive details |
| feature | one user-visible job, local interaction/state composition | unrelated page layout or global authority |
| primitive | accessible repeated interaction/visual behavior | domain/API policy |
| hook/data client | existing request/cache/subscription convention | presentation-specific copy/layout |
| form owner | draft, validation display, submit lifecycle, preserved input | server authorization or canonical entitlement |
| token/style | semantic visual role and system consistency | page-specific product policy |
| utility | pure formatting/derivation | remote side effects or hidden state |

Split a component when it owns unrelated user jobs, repeated state branches, scattered
API calls, access logic that becomes obscure, or layout and domain behavior that cannot
be independently verified. Do not extract components merely to satisfy a file-size rule.

Only when creating or extending a genuinely cross-page visual block, define its supported
and excluded contexts, public props, state coverage, responsive fallback, token/theme
assumptions, motion and reduced-motion behavior, accessibility contract, and known failure
patterns. A one-page composition does not justify a block library.

#### 2. Implement contract-backed state and interactions

Use the flow/state map from the preceding workflow. Render only approved API, auth,
permission, pending, conflict, provider, and recovery behavior. A local mock must be
identified in the checkpoint and follow the contracted result/error shape.

| Interaction | Required behavior |
| --- | --- |
| submit | prevent accidental duplicate action, preserve input on recoverable failure, show pending/success |
| destructive action | reveal scope/consequence, confirm only when designed, display final or recoverable result |
| list/filter | synchronize approved URL/local state, bound results, preserve meaningful selection |
| optimistic update | explicit rollback/refresh path and visible temporary state |
| dialog/menu | focus management, escape/close behavior, return focus, no hidden required action |
| async/provider | pending status, retry/recovery action, no raw internal/provider error |
| access/auth | render contract-backed recovery; never infer authority from hidden controls |
| generated/long content | loading/missing/error/overflow behavior and safe readable bounds |

Do not call providers directly from the browser, expose secrets/tokens, log private
payloads, or use client-side state as the enforcement authority. UI hiding is not
security.

#### 3. Build semantic and accessible interaction

Use semantic HTML before ARIA. Add ARIA only where native elements cannot express the
interaction. Check the active surface, not an abstract compliance checklist.

| Concern | Implementation check |
| --- | --- |
| structure | meaningful headings, landmarks, list/table relationships, logical DOM order |
| controls | real button/link semantics, label/name, visible affordance, disabled meaning |
| keyboard | reachable primary action, sensible tab order, escape/enter behavior where relevant |
| focus | focus-visible indicator, dialog focus management, focus return after close/submit |
| contrast | text/icon/status distinctions readable without color alone |
| motion | reduced-motion fallback and no essential meaning only in animation |
| media | useful alt text, decorative media excluded from reading order, bounded layout |
| updates | status/error/progress announced when meaningful without disruptive noise |
| touch | adequate target size and no hover-only critical discovery |

An interaction that cannot be operated or understood without a pointer is incomplete,
especially on mobile.

#### 4. Define responsive behavior deliberately

Treat narrow viewport as an interaction mode, not a smaller desktop screenshot. For
each relevant surface, state what remains primary, stacks, scrolls, collapses, becomes a
dialog/sheet, or moves behind an explicit affordance.

| Surface | Responsive decision |
| --- | --- |
| shell/sidebar | persistent, collapsible, drawer, or simplified nav with current location visible |
| table/list | priority columns, horizontal scroll, detail view, filter placement, row action access |
| form | field grouping, keyboard/touch spacing, submit visibility, error wrapping |
| dialog/sheet | viewport-safe sizing, scroll, close affordance, focus and escape behavior |
| dashboard | information priority, summary/detail transition, chart/table fallback |
| grid/cards | stable minimum sizes, no squeezed unreadable cards, meaningful reflow |
| composer/chat | input stays usable with keyboard, long message overflow, state feedback |
| CTA | primary action stays visible and unambiguous without hover |

Never hide a primary action, reduce body text until unreadable, or let a fixed-width
component create horizontal overflow merely to preserve a desktop composition.

#### 5. Check content, performance, and style health

Test long names, zero results, maximum errors, missing images, generated output, mixed
permissions, large arrays, slow data, and narrow viewports. Check only performance risks
the slice actually introduces.

| Risk | Check |
| --- | --- |
| image/font/asset | local/repo-safe loading, correct dimensions, no unnecessary weight |
| motion | bounded work, no distracting loops, reduced-motion path |
| layout shift | reserved/stable dimensions for media, controls, grids, loading states |
| rendering | avoid repeated expensive derivation, unstable list keys, unnecessary rerenders |
| collection | pagination/virtualization trigger, bounded rendering, no hidden provider fanout |
| state | no duplicate source of truth or scattering of request/access behavior |
| CSS | tokens/local conventions, manageable specificity, no blanket overrides or style bloat |
| dependency | existing stack first; new library/framework/system returns to Node02 |

For non-trivial animation, keep continuous pointer, scroll, and timeline values in the
browser or animation layer instead of ordinary application state that causes continuous
component rerenders. When behavior is equivalent, prefer compositor-friendly `transform`
and `opacity`; clean up event listeners, observers, animation instances, and scheduled
work. Use complex scroll orchestration only when the page job requires it and the approved
stack supports it, with a meaningful reduced-motion fallback.

Update module/frontend current-state docs only for durable behavior, state coverage,
visual direction, or API/auth flow changes. Do not create documentation churn for
private layout cleanup.
