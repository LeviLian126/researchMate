# Visual, Interaction, and Accessibility System

Use HTML as a working surface for information that is hard to understand as a linear Markdown document. Use [HTML Effectiveness](https://thariqs.github.io/html-effectiveness/) as the default frontend reference: render comparisons, flows, timelines, dependency maps, annotated evidence, and status lanes in the form that lets a reader see their shape at a glance. Keep the current snapshot directly openable and link focused topic pages with ordinary local navigation.

## Workflow

Choose the spatial form that matches each information relationship, reconstruct the selected HTML Effectiveness page archetype, then add only interactions that improve navigation or density while preserving a no-JavaScript reading path.

## Reference-driven fidelity

When the user provides a reference website and requests close or one-to-one reproduction, treat the site as an implementation specification, not a mood board.

1. Inspect the actual page with browser developer tools when available. Record the DOM hierarchy, computed colors, fonts, type sizes and line heights, maximum content width, horizontal padding, section gaps, borders, radii, shadows, grid tracks, responsive breakpoints, overflow behavior, focus states, and interactive state changes.
2. Identify the matching page archetype before building: documentation index, implementation plan, feature explainer, report, flowchart, comparison, editor, or another demonstrated form. Reproduce that archetype's composition rather than blending unrelated examples into a generic dashboard.
3. Create a compact reconstruction specification and shared design tokens. Match geometry and behavior as well as palette: masthead, navigation, reading measure, heading rhythm, diagram surfaces, tables, disclosures, captions, and mobile transitions.
4. Replace the reference subject matter with project facts while preserving its frontend grammar. Do not stop at “similar colors and cards.”
5. Compare rendered screenshots at desktop, constrained desktop, tablet, and mobile sizes with the reference. Correct meaningful differences in alignment, scale, density, wrapping, and interaction before handoff.

Use source code, fonts, icons, or other assets only when their license or the user's authorization permits reuse. Otherwise reconstruct the observed frontend independently while matching the visible result and behavior as closely as practical.

## Default HTML Effectiveness system

Use `../assets/document-system.css` as the implementation base. It is an independently implemented, validated stylesheet derived from inspection of the HTML Effectiveness documentation examples and already includes safe responsive behavior for the project-board components.

When the live reference is available, inspect its index page for navigation and document-index composition, `16-implementation-plan.html` for plans, milestones, diagrams, comparisons, risks, and questions, and `14-research-feature-explainer.html` for disclosures, tabs, callouts, file maps, and FAQ behavior. Use the closest archetype; do not combine all patterns on every page.

Keep these inspected defaults unless the selected reference page demonstrates another value:

| Layer | Default |
| --- | --- |
| canvas | ivory `#FAF9F5`; paper-white content surfaces; near-black `#141413` text |
| accents | clay `#D97757` / dark clay `#B85C3E`; oat `#E3DACC`; olive `#788C5D`; low-saturation gray metadata |
| typography | system sans body, Georgia-compatible serif headings, system monospace contracts and paths |
| geometry | centered `1120px` maximum page, `32px` desktop side padding, generous section rhythm, `12–14px` panel radius, fine `#D1CFC5` borders |
| index archetype | serif display title around `62px`, pill-like text navigation, three-column example/index grid when width allows |
| detail archetype | serif page title around `38px`, section headings around `26–27px`, prompt/summary blocks, white diagrams, dense ledgers, disclosures, and local navigation |
| responsive behavior | collapse summary and mock grids near `880–900px`; collapse dense row layouts near `780px`; use one-column reading order near `640px` |

Add a page-level class when the index and detail archetypes need different title scales. Preserve the restrained document character: no gradients, glass effects, colored blobs, decorative illustrations, remote font imports, generic marketing hero, or wall of identical floating cards. Let typography, alignment, rules, and whitespace explain hierarchy. Color reinforces a text label and marker; it never supplies status meaning by itself.

## Board composition

Keep a compact summary on the landing page: project name, current release/delivery state, key decision or risk, evidence freshness, and the most important next action. Follow it with a documentation index that exposes every topic page and its evidence/status responsibility. Repeat a compact, consistent global navigation on child pages and always provide a direct path back to the current snapshot.

Treat the pages as professional engineering documentation, not a teaser. Use the selected archetype's title scale and spacing, then fill it with dense ledgers, anchored sections, diagrams, definitions, source paths, and complete contract tables. Do not turn a complete documentation task into sparse summary cards that make readers reconstruct missing detail from source code.

| Information | Preferred form |
| --- | --- |
| project, audience, promise, price | concise fact ledger or comparison table |
| capability state and MVP boundary | labeled status lanes plus acceptance/evidence ledger |
| sequence or roadmap | timeline with shipped, in-progress, candidate, and blocked markers |
| frontend/backend/data flow | labeled boxes and arrows; annotate handoffs, ownership, and failure paths |
| stack and decisions | compact decision table with consequence and revisit trigger |
| database entities | relation map plus expandable field-contract tables |
| API/actions | endpoint index plus expandable request/response/error contract |
| risks and next actions | severity/impact ledger and a short prioritized action queue |

Use `<details>` and `<summary>` to keep long pages navigable. When a section would force excessive scrolling before the reader reaches the next decision, wrap the subordinate detail in a collapsible disclosure: lengthy technical explanations, full ledgers, field-level database and API contracts, route/endpoint bodies, and recovery procedures. Keep the summary, status, evidence, and one-line decision visible outside the collapsed body so readers can decide what to open. A page that opens to mostly closed toggles hides the current state; a page that collapses nothing when it is already too long to scan defeats the board. The first viewport should show the current truth, with each toggle revealing a deeper layer on demand.

## Progressive interaction

Core facts must work with JavaScript disabled. Add small vanilla-JavaScript interactions only when they make a board faster to use:

- status/category filters that do not hide the current selection or evidence;
- anchored table of contents and scroll-position indication;
- focus/hover-linked architecture nodes and details panels, with click and keyboard equivalents;
- copy controls for a command, route, or action list;
- sortable/expandable dense ledgers when the default order remains meaningful.

Do not add interactions merely because they are possible. Never hide project state behind tabs without an accessible default, use hover as the only way to reveal content, or depend on a remote API for the first render.

## Layout safety and accessibility

- Use semantic landmarks, one clear page title, logical headings, visible focus, descriptive link text, labels, and inline SVG labels/alternatives.
- Respect `prefers-reduced-motion`; avoid motion unless it clarifies a state change.
- On narrow screens, preserve reading order. Let tables, code, paths, and contracts scroll inside a bounded container or wrap safely; do not shrink them into unreadable text.
- Test desktop, constrained desktop, tablet, and mobile widths for sticky overlap, long labels, map readability, table overflow, and keyboard reachability.
- Treat nested layout as a separate responsive state. A three- or four-column flow that works at page width must become two columns or a vertical rail inside a half-width card; never preserve it with fixed child minimum widths.
- Apply `min-width: 0` to grid/flex children and adapt or remove connector arrows when a sequence wraps.
- Long file paths, source paths, and backslash-style Windows paths are a layout hazard inside narrow table cells, cards, and nav pills. Ensure path-bearing text has `overflow-wrap: anywhere` and path-heavy tables sit in a `.scroll` container with `overflow-x: auto`; confirm the longest real path wraps cleanly instead of stacking into a narrow text tower or pushing siblings aside.
- Reserve horizontal scrolling for genuinely two-dimensional tables, matrices, or diagrams. Normal cards, comparisons, status lanes, and step flows must reflow without clipped text, overlapping arrows, or nested scrollbars.

## Keep the artifact inspectable and portable

Prefer a self-contained page or a small static site with ordinary HTML, CSS, inline SVG, and minimal JavaScript. The core content, navigation, and evidence must remain usable when scripts fail. Use interaction to reveal detail, filter a dense ledger, highlight a path, or compare states; do not hide essential facts behind hover, animation, or an opaque client application.

Reuse repository design tokens and assets when they exist. When no system exists, choose a restrained document system with a readable text measure, strong hierarchy, clear state encoding, and enough contrast for long sessions. Decorative novelty must not compete with project evidence. Preserve keyboard access, focus visibility, semantic landmarks, table relationships, reduced-motion preferences, mobile reflow, and print or screenshot readability.

## Page table of contents and navigation consistency

Every HTML page — including landing pages, child pages, and archive pages — must contain exactly one `<aside class="toc">` table of contents block, immediately after the page lede/summary and before the first main content section. The TOC is the first navigation anchor for new readers and agents: it lets a reader judge which topics a page covers and where the current evidence sits without scrolling the whole page, and it lets an agent verify every page with a single grep before each commit.

### Required TOC contract

1. **Existence**: every standalone HTML page must have one `<aside class="toc">` element. Landing pages and archive pages are not exempt. If a page is too short to need a TOC, it should live as a section of its parent page, not as a standalone page.
2. **Unified heading text**:
   - English (`.html`): `<b>On this page</b>`
   - Chinese (`.zh.html`): `<b>本页目录</b>`
   - Variants such as `Contents`, `Table of Contents`, `本页导航`, `本页内容`, `目录` are forbidden. Unified wording lets readers build a stable visual expectation across pages and lets an agent verify deterministically with a regex rather than checking pages by hand.
3. **Anchor integrity**: every `<a href="#anchor">` in the TOC must correspond to a real `id` in the body. A broken fragment link is a board trust failure.
4. **Stable position**: the TOC sits right after the lede/summary, before the first main content section; do not place it in the footer or hide it inside a disclosure.

### Why this rule is a hard constraint

TOC wording drift and missing TOCs are the two most common consistency problems on the current board: the English variant mixed `On this page` with `Contents`, the Chinese variant had four writings — `本页导航`, `本页内容`, `本页目录`, `目录` — and some archive and landing pages had no TOC at all. Readers had to re-identify the TOC's location and name on every page, and an agent could not audit the whole site with one command. Unified wording and mandatory existence close both problems at once: every page has a TOC, every page uses the same name, and Chinese/English correspond one-to-one.

### Cross-page navigation sync

When adding a new HTML page, update the navigation bars of all sibling pages at the same time so the new page is reachable from every relevant page:

1. **Nav bar sync**: if the new page belongs to a child-page navigation group (such as sub-pages under learn/), the link to the new page must be added to the sub-page navigation bar of every sibling page. Missing any one page makes the new page undiscoverable.
2. **Label consistency**: the navigation label for the same child page must be consistent across all pages (Chinese pages use the Chinese label uniformly, English pages use the English label uniformly). For example, if the index uses "切面分析", every sub-page navigation must use "切面分析", not a mix of "Flow analysis".
3. **Link suffix consistency**: navigation links on Chinese pages use the `.zh.html` suffix uniformly; English pages use `.html` uniformly. Language-switch links are the exception (they point to the other-language version).
4. **Verification checklist**: after adding a page, check each sibling page's navigation bar one by one for the new page's link, label consistency, and correct link suffix, and confirm every page (including the new page itself) has an `<aside class="toc">` block and unified heading text that satisfy the TOC contract above. This step is not optional.

## Process page visual presentation

When a page needs to present a business process, request flow, or data pipeline, prefer a spatialized flow diagram over a plain-text proof-chain. Reference the `14-research-feature-explainer.html` archetype and pipeline pattern from HTML Effectiveness:

1. **Pipeline timeline**: use a vertical timeline (left-side connector + numbered circular nodes); each step is a color-coded card labeled with its step type (intercept/approve/execute/inspect).
2. **Color encoding**: red = intercept/failure path, yellow = approve/pause, green = pass/inspect, orange = execute/external call, gray = neutral/no-op.
3. **Step card**: each step contains a title, a type label, a description, the file/function names it passes through, database read/write markers, and external-call markers.
4. **Sub-steps**: expand complex steps with a nested sub-step list; each sub-step carries its own type label.
5. **Panorama preview**: before the detailed flow, use a horizontal chips bar to show the whole pipeline at a glance so readers see the full picture first.
6. **Comparison view**: for "with/without a mechanism" comparisons, use a side-by-side comparison card layout.
7. **Effectiveness note**: after each flow, use an orange callout box to explain why the key design decision is effective.
