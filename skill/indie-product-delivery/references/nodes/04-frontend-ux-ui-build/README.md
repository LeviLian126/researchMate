# Frontend Build

Build a truthful, resilient user surface whose states, interactions, accessibility, layout, and
integration behavior remain coherent with real data and failure conditions. Treat visual quality
and implementation quality as the same product boundary: a polished screen with invented data,
broken state ownership, hidden overflow, or dishonest fallback is not complete.

Use the changed journey to select the relevant concerns rather than applying every pattern to every
component.

| Implementation surface | Desired property |
|---|---|
| state and data flow | one source of truth, explicit loading/empty/error/success states, no fabricated success |
| component ownership | cohesive components and hooks, stable contracts, no duplicated cross-layer policy |
| interaction | keyboard, pointer, focus, repeated action, cancellation, and cleanup behave predictably |
| responsive layout | content and controls remain reachable without overlap, clipping, or accidental scroll traps |
| performance and lifecycle | bounded rendering and requests, cleaned listeners/observers, no avoidable rerender loop |
| AI-generated code risk | confirm component/library APIs, remove placeholder UI and sample data, avoid cargo-cult abstractions and test-only behavior |

## Read the relevant workflow

| Need | Read |
|---|---|
| decide visual direction, design system, or dials | `visual-direction-and-design-system.md` |
| check named anti-patterns before shipping | `anti-default-directives.md` |
| recover the surface and design its journey, hierarchy, content, and complete states | `experience-flow-content-and-states.md` |
| implement components, interactions, accessibility, responsiveness, anti-overlap, or performance | `component-responsive-accessible-build.md` |
| look up concrete code patterns (stack / animation / fonts / icons / z-index) | `implementation-patterns.md` |
| handle external material, audit existing work, or modernize safely | `prototype-and-redesign.md` |
| verify in a browser, debug rendering/integration failures, or hand off | `browser-proof-and-debug.md` |
| write long-form help, explanation, or documentation inside a frontend surface | run the `humanizer` skill by default |
| build or refresh durable HTML project documentation | `../08-agent-context-html/README.md` |

## Output contract

Return the changed user journey and surface, relevant content and states, responsive and
accessibility behavior, visual/browser proof actually run, durable documentation impact,
and remaining risks or gaps. State whether the slice is `BUILT`, `BUILT_WITH_NAMED_GAPS`,
`BLOCKED`, or needs Node02/03 re-entry.
