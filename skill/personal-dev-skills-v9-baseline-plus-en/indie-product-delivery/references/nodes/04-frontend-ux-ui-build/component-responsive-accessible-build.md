# Component, Responsive, and Accessible Build

> **Goal:** Implement correct component boundaries, complete interaction states, semantic accessibility,
> responsive behavior, anti-overlap/anti-stacking rules, and performance health.
>
> **Owns:** component layers, contract-backed interactions, semantic accessibility, responsive behavior, multi-resolution adaptation, anti-overlap rules, touch targets, performance/style health
>
> **Does NOT own:** code patterns like import paths (`implementation-patterns.md`), anti-patterns (`anti-default-directives.md`), visual direction (`visual-direction-and-design-system.md`)

Use this guide while implementing or refactoring production frontend code.

## Component Boundaries

Recover repository naming, folders, primitives, data client, form convention, tokens, icons, styling
approach, lint/type/build commands, and nearest working feature. Extend the smallest suitable owner.

### Layer responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| page / route | surface coordination, route state, composition, high-level loading boundary | duplicated backend policy or reusable primitive details |
| feature | one user-visible job, local interaction/state composition | unrelated page layout or global authority |
| primitive | accessible repeated interaction/visual behavior | domain/API policy |
| hook / data client | existing request/cache/subscription convention | presentation-specific copy/layout |
| form owner | draft, validation display, submit lifecycle, preserved input | server authorization or canonical entitlement |
| token / style | semantic visual role and system consistency | page-specific product policy |
| utility | pure formatting/derivation | remote side effects or hidden state |

### Split rules

Split a component when it owns unrelated user jobs, repeated state branches, scattered API calls,
access logic that becomes obscure, or layout and domain behavior that cannot be independently verified.
Do not extract components merely to satisfy a file-size rule.

Only when creating or extending a genuinely cross-page visual block, define its supported and excluded
contexts, public props, state coverage, responsive fallback, token/theme assumptions, motion and
reduced-motion behavior, accessibility contract, and known failure patterns. A one-page composition
does not justify a block library.

## Contract-Backed State and Interactions

Use the flow/state map from `experience-flow-content-and-states.md`. Render only approved API, auth,
permission, pending, conflict, provider, and recovery behavior. A local mock must be identified in the
checkpoint and follow the contracted result/error shape.

### Interaction behavior

| Interaction | Required behavior |
|---|---|
| submit | prevent accidental duplicate action, preserve input on recoverable failure, show pending/success |
| destructive action | reveal scope/consequence, confirm only when designed, display final or recoverable result |
| list / filter | synchronize approved URL/local state, bound results, preserve meaningful selection |
| optimistic update | explicit rollback/refresh path and visible temporary state |
| dialog / menu | focus management, escape/close behavior, return focus, no hidden required action |
| async / provider | pending status, retry/recovery action, no raw internal/provider error |
| access / auth | render contract-backed recovery; never infer authority from hidden controls |
| generated / long content | loading/missing/error/overflow behavior and safe readable bounds |

Do not call providers directly from the browser, expose secrets/tokens, log private payloads, or use
client-side state as the enforcement authority. UI hiding is not security.

## Semantic and Accessible Interaction

Use semantic HTML before ARIA. Add ARIA only where native elements cannot express the interaction.
Check the active surface, not an abstract compliance checklist.

| Concern | Implementation check |
|---|---|
| structure | meaningful headings, landmarks, list/table relationships, logical DOM order |
| controls | real button/link semantics, label/name, visible affordance, disabled meaning |
| keyboard | reachable primary action, sensible tab order, escape/enter behavior where relevant |
| focus | focus-visible indicator, dialog focus management, focus return after close/submit |
| contrast | text/icon/status distinctions readable without color alone |
| motion | reduced-motion fallback and no essential meaning only in animation |
| media | useful alt text, decorative media excluded from reading order, bounded layout |
| updates | status/error/progress announced when meaningful without disruptive noise |
| touch | adequate target size and no hover-only critical discovery |

An interaction that cannot be operated or understood without a pointer is incomplete, especially on
mobile.

## Responsive Behavior

Treat narrow viewport as an interaction mode, not a smaller desktop screenshot. For each relevant
surface, state what remains primary, stacks, scrolls, collapses, becomes a dialog/sheet, or moves
behind an explicit affordance.

### Surface responsive decisions

| Surface | Responsive decision |
|---|---|
| shell / sidebar | persistent, collapsible, drawer, or simplified nav with current location visible |
| table / list | priority columns, horizontal scroll, detail view, filter placement, row action access |
| form | field grouping, keyboard/touch spacing, submit visibility, error wrapping |
| dialog / sheet | viewport-safe sizing, scroll, close affordance, focus and escape behavior |
| dashboard | information priority, summary/detail transition, chart/table fallback |
| grid / cards | stable minimum sizes, no squeezed unreadable cards, meaningful reflow |
| composer / chat | input stays usable with keyboard, long message overflow, state feedback |
| CTA | primary action stays visible and unambiguous without hover |

### Dense table and ledger guidance

For dense tables and ledgers, choose one deliberate fallback: preserve readable columns with horizontal
scrolling, reduce to priority columns plus a detail view, or render each row as a labelled record. Use
records when every column contains prose; use a table when cross-row comparison is the reader job.

Preserve normal word and identifier boundaries: never split a word merely to make a column fit. Let
cells retain their intrinsic word width; reserve breaking for a genuinely unbroken overlong token, and
disable automatic hyphenation unless it is an intentional editorial choice. A `nowrap` chip may wrap,
truncate with an accessible full value, or grow the table; it must never overlap an adjacent cell. When
a table must scroll, make the horizontal scrollbar visible and usable.

Reduce or collapse secondary rails, such as a table of contents, before starving the main reading
column. Test the widest real cell content, including badges, code, and long generated text, at the
target desktop width and narrow viewports before claiming responsive proof.

### Multi-resolution adaptation

Narrow viewport is not a single value. Test at minimum three mobile breakpoints:

| Breakpoint | Representative device | What to check |
|---|---|---|
| 360px | small Android (Galaxy S10 SE, Pixel 5) | primary action visible, no component stacking, no horizontal overflow, touch targets >= 44x44 CSS px, fixed/sticky not covering content |
| 390px | standard iPhone (iPhone 14/15) | same checks + navigation reachable, form fields usable with keyboard |
| 768px | tablet portrait (iPad mini) | same checks + layout transitions (sidebar visible or drawer), grid reflow correct |

At least one of these must be a Playwright/Cypress automated check if the project has browser testing
infrastructure. The others may be manual DevTools device simulation. Record which breakpoints were
tested and how.

Never hide a primary action, reduce body text until unreadable, or let a fixed-width component create
horizontal overflow merely to preserve a desktop composition.

## Anti-Overlap and Anti-Stacking

These rules prevent the most common mobile and responsive failure: components visually colliding,
overlapping, or stacking into an unusable mess. Every rule applies at every tested viewport (360 / 390 /
768), not just desktop.

### Fixed / sticky element collision

Sticky headers, bottom navigation bars, floating action buttons (FAB), and fixed toolbars must not
cover primary actions or interactive content.

- Content regions must reserve `padding-top` / `padding-bottom` matching the sticky element height, or
  use `scroll-margin-top` on anchor targets.
- A FAB must not overlap the last list item's action buttons. Either add bottom padding to the
  scrollable container or position the FAB where it cannot collide.
- Test: scroll to the bottom of every scrollable region at every breakpoint. Verify no fixed element
  covers a visible interactive element.

### Absolute positioning reflow collision

After reflow (narrowing viewport), check all `position: absolute` or `position: fixed` elements for
visual overlap with adjacent content.

- Narrow screens: prefer document flow + flex/grid reordering. Use `absolute` positioning only when the
  element does not affect reflow (decorative overlay, badge on a card corner).
- If an absolute element must remain, test its position at all breakpoints. If it collides at any
  width, switch to document flow or add a responsive override.

### Grid and cards reflow

- Narrow-screen reflow must use explicit grid degradation: `grid-cols-1` at mobile, `md:grid-cols-2`,
  `lg:grid-cols-3`. Do not rely on `flex-wrap` to "figure it out" - wrapping can produce uneven, stacked
  card layouts that look broken.
- Every grid item must maintain a `min-width` that prevents the card from collapsing into an unreadable
  sliver. Use `min-w-0` (to allow flex/grid shrinking) combined with internal `overflow` handling.
- "Meaningful reflow" means each item remains readable and actionable at every breakpoint. It does not
  mean "visually compressed into a pile."
- Cards must have stable minimum sizes. No squeezed unreadable cards. If content cannot fit, truncate
  with accessible full value (`title` attribute or `aria-label`) rather than overlap.

### Touch targets

- Adjacent interactive elements must have a minimum touch target of 44 x 44 CSS pixels (WCAG 2.5.5).
- Spacing between adjacent touch targets must be at least 8px to prevent mis-taps.
- Use `min-w-[44px] min-h-[44px]` on interactive elements, or wrap small targets in a larger
  clickable area with proper `aria` labeling.
- Icon-only buttons must include `aria-label` for screen readers.

### Modal / dialog viewport safety

- Modals must not exceed viewport bounds on small screens. Use `max-h-[90vh]` with internal scrolling.
- Close controls (X button, backdrop click, escape key) must remain reachable at all viewports.
- Apply `overscroll-behavior: contain` to the modal body to prevent scroll chaining to the underlying
  page. See `implementation-patterns.md` for the overscroll containment pattern.
- On very narrow viewports, consider a bottom sheet (`slide-up` panel) instead of a centered modal -
  it uses the full width and is easier to reach on mobile.

### Long content overflow

Long text, long URLs, long identifiers, and long generated content must not break container layout or
overlap adjacent elements.

- Use `overflow-wrap: break-word` or `word-break: break-all` (for URLs/identifiers only) to prevent
  content from forcing horizontal overflow.
- Use `min-width: 0` on flex/grid children combined with `truncate` (`overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap`) for single-line truncation. Always provide the full
  value via `title` attribute or an accessible expand mechanism.
- Test with the longest realistic content: longest username, longest error message, longest URL, longest
  generated text. If any of these breaks layout, fix the overflow handling before shipping.

### z-index management

Do not use bare `z-9999` or arbitrary z-index values. Use a layered z-index scale defined as tokens or
CSS variables. See `implementation-patterns.md` for the full z-index scale definition.

- Each z-index layer must come from a token: `z-base`, `z-dropdown`, `z-sticky`, `z-drawer`, `z-modal`,
  `z-toast`.
- Never inline `z-index: 9999` or similar magic numbers.
- If a stacking conflict appears, add a token layer rather than escalating the number.

### Horizontal overflow prohibition

`overflow-x: hidden` on `body` or a container is a last resort, not a fix. It masks the real problem:
a fixed-width component or uncontained content forcing horizontal scroll.

- First fix the root cause: constrain the fixed-width component, add `max-w-full` / `overflow-hidden`
  to the specific element, or use responsive width units (`%`, `rem`, `vw` instead of `px`).
- Only use `overflow-x: hidden` when the overflow is from a genuinely unavoidable decorative element
  (e.g., a background pattern extending beyond viewport).
- Test: scroll horizontally at every breakpoint. If horizontal scroll is possible, find and fix the
  source element.

## Performance and Style Health

Test long names, zero results, maximum errors, missing images, generated output, mixed permissions,
large arrays, slow data, and narrow viewports. Check only performance risks the slice actually
introduces.

| Risk | Check |
|---|---|
| image / font / asset | local/repo-safe loading, correct dimensions, no unnecessary weight |
| motion | bounded work, no distracting loops, reduced-motion path |
| layout shift | reserved/stable dimensions for media, controls, grids, loading states |
| rendering | avoid repeated expensive derivation, unstable list keys, unnecessary rerenders |
| collection | pagination/virtualization trigger, bounded rendering, no hidden provider fanout |
| state | no duplicate source of truth or scattering of request/access behavior |
| CSS | tokens/local conventions, manageable specificity, no blanket overrides or style bloat |
| dependency | existing stack first; new library/framework/system returns to Node02 |

For non-trivial animation, keep continuous pointer, scroll, and timeline values in the browser or
animation layer instead of ordinary application state that causes continuous component rerenders.
For specific animation implementation patterns (Motion API, `useMotionValue`, `useScroll`,
IntersectionObserver, reduced-motion fallback), see `implementation-patterns.md`.

Update module/frontend current-state docs only for durable behavior, state coverage, visual direction,
or API/auth flow changes. Do not create documentation churn for private layout cleanup.

---

**Acceptance criteria:** After reading this file, you can assign each component to the correct layer,
implement all required interaction states, pass the accessibility check table, define per-surface
responsive behavior (including multi-resolution testing at 360/390/768), identify and fix every
overlap/stacking risk (fixed/sticky collision, grid reflow, touch targets, modal viewport safety, long
content overflow, z-index management, horizontal overflow), and identify performance risks.
