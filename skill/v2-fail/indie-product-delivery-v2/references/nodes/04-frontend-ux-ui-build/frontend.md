# Frontend

Use this when the present need is a frontend surface: the experience, its visual direction, the production build, or browser proof.

## Sections
- [Recover approved experience truth](#recover-approved-experience-truth)
- [Experience spine](#experience-spine)
- [Flow, content, and states](#flow-content-and-states)
- [Visual direction](#visual-direction)
- [Reference-driven archetype alignment](#reference-driven-archetype-alignment)
- [Production build](#production-build)
- [Browser proof and visual debug](#browser-proof-and-visual-debug)

## Recover approved experience truth

Take the approved product and architecture truth rather than redesigning scope: which surface, who's using it, what they're trying to do, what's approved, and what's out of bounds. Classify facts by state (see `references/methods.md`). Don't broaden a focused frontend change into a redesign — name the preserved constraints and work inside them.

## Experience spine

Trace the journey before choosing components; name the existing screen or mark it new:

```
screen -> entry state -> action -> feedback -> success or recoverable failure -> next or rollback
```

A missing owner on an arrow is a design signal — the journey has a gap, not a styling problem.

## Flow, content, and states

Define the user flow and hierarchy: which screen opens which, which action leads where, and what the primary path is versus the recovery path. Compose information architecture by the user's mental model, not by your component library's defaults.

Write content as navigation: labels and states should answer "where am I, what can I do, what just happened." Keep one term for one action and one status.

Assign every state an owner and make it visible. The states that ship invisibly are the ones users hit and blame the product for:

| State | Owned by | Visible as |
|---|---|---|
| empty | entry/call site | a reason to start and a first action |
| loading | the async owner | progress scoped to what's changing, not a full-screen modal |
| error / failure | the boundary that failed | what failed, what's safe to do (retry / cancel / go back) |
| partial | the data owner | what arrived and what's still pending |
| disabled / forbidden | the permission/feature owner | why, and what would enable it |
| optimistic | the action owner | the temporary state and how it reconciles with the real result |

## Visual direction

Ground visual direction in the subject, not in a generic template. The look should be readable as belonging to this product, not as any product. Set the surface-aware dials deliberately; defaults that look "fine" everywhere usually look like nothing in particular:

| Dial | Decide |
|---|---|
| content width & line length | legibility at real density, not a centered hero |
| type scale & line height | hierarchy that survives long content |
| section rhythm | spacing that groups related things |
| density | packed vs airy, per surface type |
| borders, radii, fills | the edge language of the product |
| motion | what moves, how far, why — motion explains change |
| contrast & color | status beyond color; brand without gradient theater |

Build or preserve a usable visual system: a real type scale, spacing scale, and color tokens. Reuse the existing one if present; extend it before adding parallel concepts.

### Anti-default checks

Review the surface for combinations of these signals — each is harmless alone, several together read as a generic AI mockup:

- a centered hero with a vague headline and two buttons that mean the same thing;
- a three-card feature row with one-line titles and no real content behind them;
- gradients, glassmorphism, or blur with no information reason;
- stock imagery or generic illustrations standing in for missing content;
- AI-favored vocabulary ("seamless", "powerful", "leverage") where a plain product term fits;
- placeholder-shaped content — `${value}`, "Lorem", or three repeated demo rows — left in production;
- every section the same height, every card the same radius, every list three items.

Rewrite when the signals cluster or when one clearly obstructs the reader. A mono font, a serif, an em dash, a gradient that means data — none of these are defects by themselves.

## Reference-driven archetype alignment

When the user supplies a reference site, inspect its real DOM, computed styles, dimensions, breakpoints, component states, and interactions — don't approximate its mood from memory. Reconstruct the selected page archetype faithfully while replacing its subject matter with this product's documentation. Match its information geometry, not just its palette:

content width, type scale and line height, section rhythm, navigation shape, borders/radii/spacing, component composition, disclosure patterns, responsive transitions, and focus or interaction states. A palette-only resemblance doesn't pass. Changing only colors, fonts, or card styling doesn't complete a reference-driven task.

## Production build

Use existing implementation boundaries — reuse the component system, the styling convention, and the data-fetching pattern already in the repo before introducing a parallel one.

- Implement contract-backed state and interactions: state comes from the real backend contract, not from invented local mock shapes; a field that the API doesn't return is a missing contract, not a frontend detail to hardcode.
- Build semantic and accessible interaction: landmarks, headings, focus order, reduced-motion support, and status text beyond color. Don't rely on a visual alone to communicate a state.
- Define responsive behavior deliberately: which breakpoints, how grids collapse, where long content wraps or truncates, and what happens to a sticky element on a small screen. Don't let a single hard-coded width cause overflow.
- Check content, performance, and style health: real longest-heading and densest-table behavior, no obvious render-blocking, no style that breaks a shared component elsewhere.

## Browser proof and visual debug

Prove in a browser, proportional to risk:

| Axes | Cover |
|---|---|
| pages | each screen in scope |
| widths | desktop, constrained desktop, tablet, mobile |
| states | empty, loading, error, partial, disabled — not only the happy path |

Reconnoiter the rendered state before acting — what's actually on the page, not what the diff suggests. Verify visible quality proportionally: horizontal overflow, clipping, contrast, visible focus, keyboard reach, and the *repeated* component instances, not only the first example. Include nested grids inside half-width cards, the longest heading or path, the densest table, every diagram family, and filtered/expanded states — defects hide in the copies, not the showcase.

When a reference governs the frontend, compare the implementation against the reference archetype at matching viewport sizes; palette-only resemblance doesn't pass. Debug visual or interaction defects from evidence (the rendered DOM and computed styles), not from a guess about the cause. Claim only what you verified in a browser, and state clearly what you didn't.
