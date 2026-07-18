# Visual Direction, Prototype, and Redesign

Use this guide for meaningful visual direction, reference-led reconstruction, prototype translation, or redesign. Preserve product and system truth while making the surface deliberate and comparable.

## Sections

- [Visual Direction, System, and Art Direction](#visual-direction-system-and-art-direction)
- [Prototype, Redesign, and Visual Exploration](#prototype-redesign-and-visual-exploration)

## Visual Direction, System, and Art Direction

#### 1. Ground visual direction in the subject

Before choosing colors, fonts, cards, or motion, name the concrete subject, audience,
page job, and visual language. Write one design read:

    Reading this as a surface for an audience, with a page job and visual language,
    leaning toward a compatible system or aesthetic family.

The design read must come from product facts, real assets, user references, and the
surface context. Do not select an aesthetic because it is an LLM default or because
another product page recently used it.

| Direction field | Required decision |
| --- | --- |
| subject | product world, material, artifact, workflow, or evidence that grounds the surface |
| audience | knowledge, trust need, urgency, and aesthetic expectation |
| page job | one thing the page must make easier to understand, decide, or do |
| visual language | restrained system, editorial, industrial, playful, luxury, utilitarian, or other justified family |
| signature move | one product-serving typography, imagery, layout, rhythm, or interaction decision |
| system stance | preserve existing, use official system, extend repo primitives, or define lightweight tokens |

A signature move is not a collection of decorations. Spend boldness in one memorable
place and keep surrounding UI quiet enough for the job to remain obvious.

#### 2. Set surface-aware visual dials

Set visual variance, motion intensity, and information density proportionally. Record
the direction only when visual work is meaningful; local changes inherit the nearby
system and do not require a new art-direction exercise.

Treat these dials as shared constraints for the page or active surface, not independent
per-component choices. Local variation needs a content, state, or interaction reason.

| Surface | Variance | Motion | Density | Priority |
| --- | --- | --- | --- | --- |
| public/brand | deliberate and potentially distinctive | one meaningful orchestrated moment if useful | breathable around proof/CTA | promise, trust, differentiation |
| onboarding | restrained and guiding | feedback/progress only | progressive disclosure | first success |
| dashboard/operations | low to moderate | state feedback only | efficient and scannable | decision, repeated action |
| form/transaction | restrained | feedback/reduced motion | focused | clarity, consequence, recovery |
| docs/current-state | low | optional and nonessential | structured | evidence, navigation |

Do not treat high variance as superior. A refined operational tool can be distinctive
through clarity, rhythm, type hierarchy, and disciplined density rather than spectacle.

#### 3. Build or preserve a usable visual system

Inspect existing tokens, primitives, assets, fonts, icons, responsive conventions, and
design docs first. Preserve a coherent system unless a change is approved and justified.
When no system exists, define only the token decisions needed by the active surface.

Distinguish a design system from a visual language. When the repository already adopts
a mature system, use its actual supported primitives, tokens, and interaction conventions.
Keep one primary system per surface; do not mix component grammars or claim official
system adoption when only approximating its appearance. A new system or dependency still
requires Node02 approval.

| System element | Decision |
| --- | --- |
| color | semantic roles, contrast, one hierarchy; no decorative palette without product purpose |
| type | readable body, purposeful display/utility roles, hierarchy, measure, weights |
| spacing/layout | rhythm, container rules, grid/stack choice, section meaning, stable dimensions |
| radius/elevation | interaction hierarchy and surface meaning, not uniform decoration |
| iconography | familiar symbols for actions, consistent style, accessible labels/tooltips |
| assets | real product/subject imagery, brand material, generated asset only when useful and inspectable |
| motion | state change, orientation, or one signature moment; reduced-motion fallback |
| responsive intent | what stays primary, stacks, scrolls, collapses, or changes mode on narrow screens |

Typography and layout should encode importance. Numbering, eyebrows, dividers, labels,
and decorative structures must express a real sequence, category, or relationship.
Do not introduce them merely to make a screen look designed.

#### 4. Apply anti-default and content checks

For public/brand work, actively reject defaults unless the brief makes them right:
generic centered hero, purple/blue gradient atmosphere, three equal feature cards,
decorative icon circles, uniform bubbly radii, card-on-card sections, fake dashboards,
stock-like visual crops, filler badges, invented metrics, and motion without meaning.

For operational UI, reject fake density: equal metric cards, decorative panels around
every group, hidden action affordance, small unreadable text, hover-only discovery,
inconsistent spacing, or data-shaped hierarchy.

For a long public page, choose each section's macro composition from its information
relationship and inspect adjacent sections for mechanical repetition. Vary composition
only when the content structure warrants it while keeping type, color, spacing, controls,
and motion language coherent; do not satisfy an arbitrary layout or section quota.

| Preflight question | Required answer |
| --- | --- |
| hierarchy | can the user identify page purpose, current state, and primary action in a scan? |
| affordance | are buttons, links, fields, rows, and navigation visibly actionable without hover? |
| trust | are proof, real data labels, consequences, and privacy effects honest? |
| content | are all visible strings specific, grammatical, consistent, and free of fake precision? |
| visual system | do type, color, spacing, radius, asset, and motion choices share one rationale? |
| access | do contrast, focus, touch, reduced motion, and readable measure survive the direction? |
| mobile | does the primary action remain obvious without relying on hover or excess space? |

A strong visual direction never excuses hidden information, weak contrast, misleading
metrics, inaccessible interactions, or a weaker product flow.

#### 5. Choose assets and motion deliberately

Use visuals that show the actual product, place, object, subject, or user-relevant
state. For a public hero, a real/generated inspectable visual or an immersive product
moment may be warranted; for an operational screen, decorative imagery is usually noise.

Do not use a hand-built fake dashboard or arbitrary gradient blob as product proof.
Use a real screenshot, actual mini-component, generated asset, relevant photography, or
no visual when the page job is clearer without one.

Motion should signal a state change, guide attention, orient a transition, or carry the
signature move. Prefer one coordinated moment over scattered animation. Respect reduced
motion and avoid moving elements that impair reading or repeated work.

## Prototype, Redesign, and Visual Exploration

#### 1. Classify supplied material

Treat external material as evidence with limits.

| Material | Useful for | Never authoritative for |
| --- | --- | --- |
| screenshot | hierarchy, density, composition, visual mood | behavior, hidden states, accessibility, data/auth truth |
| Figma/Stitch/v0 | IA experiment, content inventory, component intent | production code, dependencies, backend or permission behavior |
| exported HTML | structure/copy/assets inventory | repo architecture, security, responsive/accessibility completeness |
| brand asset | existing identity, color/type/photo direction | automatic page layout or interaction policy |
| generated image/reference | subject/art direction and asset exploration | factual product proof or live UI state |
| existing site | working routes, conversion, content, behavior to preserve | permission to replace brand/product meaning |

When material conflicts with Node01 scope, Node02 contract, Node03 behavior, current repo system, or
accessibility requirements, preserve the useful intention and rebuild the unsafe detail.

#### 2. Audit existing redesign work before changing it

Classify the work as targeted evolution, broad redesign, or approved repositioning.
For targeted evolution, audit only the affected page and its direct paths; for broader
redesign, build a preserve/retire/improve record before implementation.

| Area | Preserve/check before style change |
| --- | --- |
| routes/navigation | URL, anchors, deep links, nav labels, active state, search/wayfinding |
| conversion/forms | fields, names, order, validation, consent, primary CTA, confirmation |
| content/proof | approved claims, pricing, legal copy, testimonials, evidence, brand voice |
| analytics/SEO | event names, metadata, canonical/OG, structured data where relevant |
| behavior/states | auth, permission, loading, empty, error, mobile, accessibility wins |
| brand | logo, wordmark, approved colors/type/assets, trust markers |
| implementation | framework, tokens, primitives, asset path, performance constraints |

Modernize in order: clarity and hierarchy, typography/rhythm, states/feedback, color
calibration, layout composition, then replacement of a section or block. Do not silently
change route slugs, analytics events, form meaning, legal copy, or brand identity.

#### 3. Extract production-ready intent

Translate retained material into explicit decisions:

| Reference signal | Production decision |
| --- | --- |
| layout rhythm | container/grid/spacing hierarchy compatible with repo |
| type/color | token role and readable hierarchy, not copied arbitrary values |
| imagery | source/asset strategy, crop, alt intent, responsive behavior |
| component region | page/feature/primitive responsibility and state coverage |
| copy | approved or rewritten functional content with consistent action vocabulary |
| interaction | supported behavior, affordance, focus, loading/recovery expectation |
| anti-pattern | detail to avoid because it is generic, unsafe, fake, or inaccessible |

Do not paste exported CSS, CDN assets, inline scripts, remote runtime dependencies,
static fake data, or oversized page markup into production. Rebuild through local
components, tokens, contracts, and state ownership.

#### 4. Explore visual variants only when justified

Variant exploration is optional and limited to public visual-critical pages, an
important redesign with real direction uncertainty, or explicit user request. It is not
for dashboard polish, a routine UI bug, or a surface governed by a mature design system.

Before creating variants, write 2-3 concise concepts. Each must differ in typography,
palette, layout rhythm, and signature move; minor color swaps do not count. Compare
them against the same product job, trust needs, accessibility constraints, real assets,
and mobile behavior.

| Variant decision | Rule |
| --- | --- |
| number | 2-3 directions, not an unbounded gallery |
| distinction | different type family/role, color temperature, composition, and rhythm |
| reference | use real product/subject visual, existing screenshot, or inspectable generated asset |
| feedback | summarize what differs and capture the user's chosen direction in the checkpoint |
| implementation | extract tokens/motifs/constraints; do not chase pixel similarity |
| rejection | record why a direction conflicts with product, system, accessibility, or trust |

Do not create comparison servers, persistent taste profiles, telemetry, autonomous
generation loops, or project-local design artifact systems. The output is an approved
direction and implementation constraints, not a separate product.

#### 5. Hand off protected facts

State preserve, retire, improve, and deferred items. Update current-state frontend docs
only when durable direction, behavior, state coverage, or asset/system choices changed.
Use `references/agent-context-html/instructions.md` when updating a long-lived HTML project board.
