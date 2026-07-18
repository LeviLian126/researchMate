# Visual and Interaction System

Use HTML as a working surface for information that is hard to understand as a linear Markdown document. Use [HTML Effectiveness](https://thariqs.github.io/html-effectiveness/) as the default frontend reference: render comparisons, flows, timelines, dependency maps, annotated evidence, and status lanes in the form that lets a reader see their shape at a glance. Keep the current snapshot directly openable and link focused topic pages with ordinary local navigation.

## Purpose

Make dense, serious project documentation scannable, calm, and directly usable without inventing a separate product visual identity. Default navigation, headings, labels, captions, and explanatory prose to English unless the user explicitly requests another language.

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

Use `<details>` and `<summary>` for field-level database and API detail. Keep the contract summary, status, and evidence visible outside the collapsed body so readers can decide what to open.

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
- Apply `min-width: 0` to grid/flex children, allow long code and paths to wrap safely, and adapt or remove connector arrows when a sequence wraps.
- Reserve horizontal scrolling for genuinely two-dimensional tables, matrices, or diagrams. Normal cards, comparisons, status lanes, and step flows must reflow without clipped text, overlapping arrows, or nested scrollbars.
