# Frontend Build

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
