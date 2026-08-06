# Visual Direction and Design System

> **Goal:** Given a frontend surface brief, decide what it should look like and which design system to use.
>
> **Owns:** brief inference, design read, three visual dials, design-system map, signature move
>
> **Does NOT own:** anti-default checks (`anti-default-directives.md`), code patterns (`implementation-patterns.md`), flow/state design (`experience-flow-content-and-states.md`)

Use this guide before choosing colors, fonts, cards, or motion. Name the concrete subject, audience,
page job, and visual language first. Do not select an aesthetic because it is an LLM default or because
another product page recently used it.

## Design Read

Before touching code or tweaking dials, infer what the user actually wants. Most LLM design output is
bad because the model jumps to a default aesthetic instead of reading the room.

### Read these signals first

1. **Page kind** - landing (SaaS / consumer / agency / event), portfolio (dev / designer / studio),
   redesign (preserve vs overhaul), dashboard, form, docs, editorial.
2. **Vibe words** - "minimalist", "calm", "Linear-style", "Awwwards", "brutalist", "premium consumer",
   "Apple-y", "playful", "serious B2B", "editorial", "agency-y", "glassy", "dark tech".
3. **Reference signals** - URLs, screenshots, product names, brands they compete with.
4. **Audience** - B2B procurement vs design-conscious consumer vs recruiter vs operations team.
   The audience picks the aesthetic, not your taste.
5. **Brand assets that already exist** - logo, color, type, photography. For redesigns these are
   starting material, not optional input.
6. **Quiet constraints** - accessibility-first audiences, public-sector, regulated industries,
   trust-first commerce, kids products. These constraints override aesthetic preference.

### Vibe-word to direction inference

| Signal in the brief | VARIANCE | MOTION | DENSITY | Direction |
|---|---|---|---|---|
| "minimalist / clean / calm / editorial / Linear-style" | 5-6 | 3-4 | 2-3 | restrained, sans-serif display, generous whitespace |
| "premium consumer / Apple-y / luxury / brand" | 7-8 | 5-7 | 3-4 | refined spacing, deliberate materiality, one signature moment |
| "playful / wild / Dribbble / Awwwards / experimental / agency" | 9-10 | 8-10 | 3-4 | expressive, kinetic motion, asymmetric layout |
| "landing page / portfolio / marketing site (default)" | 7-9 | 6-8 | 3-5 | distinctive but product-grounded |
| "trust-first / public-sector / regulated / accessibility-critical" | 3-4 | 2-3 | 4-5 | official system (GOV.UK / USWDS), restrained, high-contrast |
| "dashboard / operations / admin / data-dense" | 3-4 | 2-3 | 6-7 | quiet utility, truthful density, explicit hierarchy |
| "redesign - preserve" | match existing | +1 | match existing | audit first, style second |
| "redesign - overhaul" | +2 | +2 | match existing | reposition with preserved content |

### Output a one-line design read before generating

Before any code, state in one line:

> "Reading this as: <page kind> for <audience>, with a <vibe> language, leaning toward
> <design system or aesthetic family>."

Example reads:

- *"Reading this as: B2B SaaS landing for technical buyers, with a Linear-style minimalist language,
  leaning toward Tailwind utilities + Geist + restrained motion."*
- *"Reading this as: solo designer portfolio for hiring managers, with an editorial / kinetic-type
  language, leaning toward native CSS + scroll-driven animation + custom typography."*
- *"Reading this as: operational dashboard for on-call engineers, with a utilitarian language, leaning
  toward existing repo primitives + high-density table layout + state-feedback-only motion."*
- *"Reading this as: redesign of a public-sector service site, with a trust-first language, leaning
  toward GOV.UK Frontend."*

### Brief inference rules

- If the brief is ambiguous, ask exactly one clarifying question - never a multi-question dump - and
  only when the design read genuinely diverges. Example: *"Should this feel closer to Linear-clean or
  Awwwards-experimental?"*
- If you can confidently infer from context, do not ask. Declare the design read and proceed.
- The design read must come from product facts, real assets, user references, and the surface context.
  Do not select an aesthetic because it is an LLM default or because another product page recently
  used it.

## Visual Dials

After the design read, set three dials. Every layout, motion, and density decision below is gated by
these. Treat them as shared constraints for the page or active surface, not independent per-component
choices. Local variation needs a content, state, or interaction reason.

### The three dials

- **VARIANCE (1-10):** 1 = perfect symmetry, 10 = artsy chaos. Controls layout experimentation.
- **MOTION (1-10):** 1 = static, 10 = cinematic / physics. Controls animation depth.
- **DENSITY (1-10):** 1 = art gallery / airy, 10 = cockpit / packed data. Controls information per viewport.

### Surface presets

These presets extend beyond marketing pages into operational surfaces that dedicated design skills
often skip. Use these unless the design read overrides them.

| Surface | VARIANCE | MOTION | DENSITY | Priority |
|---|---|---|---|---|
| public / brand | 7 | 6 | 4 | promise, trust, differentiation |
| onboarding | 5 | 4 | 3 | first success, progressive disclosure |
| dashboard / operations | 3 | 2 | 6 | decision, scan, repeated action |
| form / transaction | 3 | 2 | 4 | clarity, consequence, recovery |
| docs / current-state | 4 | 2 | 5 | evidence, navigation, structured truth |

### Dial principles

- High variance is not superior. A refined operational tool earns distinctiveness through clarity,
  rhythm, type hierarchy, and disciplined density - not spectacle. Do not apply landing-page art
  direction to a high-frequency admin workflow.
- If two user jobs compete for first attention, return to Node01 rather than making both equally
  prominent.
- Record the direction only when visual work is meaningful; local changes inherit the nearby system
  and do not require a new art-direction exercise.

## Design System Map

Once you have the design read and dials, pick the right foundation. Do not invent CSS for things that
have an official package. Do not pretend an aesthetic trend is an official system.

### When to reach for a real design system

| Brief reads as | Reach for | Install |
|---|---|---|
| Microsoft / enterprise SaaS / dashboards | Fluent UI React | `npm i @fluentui/react-components` |
| Google-ish UI, Material-flavored product | Material Web | `npm i @material/web` |
| IBM-style B2B / enterprise analytics | Carbon | `npm i @carbon/react @carbon/styles` |
| Shopify app surfaces | Polaris | `polaris.js` web components |
| Atlassian / Jira-style product | Atlaskit | `yarn add @atlaskit/css-reset @atlaskit/tokens` |
| GitHub-style devtool / community page | Primer | `npm i @primer/css` |
| UK public-sector service | GOV.UK Frontend | `npm i govuk-frontend` |
| US public-sector / trust-first | USWDS | `npm i uswds` |
| Modern accessible React foundation | Radix Themes | `npm i @radix-ui/themes` |
| Modern SaaS where you own the components | shadcn/ui | `npx shadcn@latest init` |
| Fast local-business / agency MVP | Bootstrap 5.3 | `npm i bootstrap` |
| Tailwind-based modern SaaS / AI marketing | Tailwind v4 utilities | `@tailwindcss/postcss` |

**Honesty rule:** if the brief reads as one of the systems above, install and use the official package.
Do not recreate its CSS by hand. Do not import a system tokens but then override 90% of them.

**One system per project.** Do not mix Fluent React with Carbon in the same tree. Do not import
shadcn/ui components into a Material 3 app. A new system or dependency still requires Node02 approval.

### When the brief is an aesthetic, not a system

For these directions there is no single official package. Build with native CSS + Tailwind + a
maintained component library. Be honest in code comments about what is borrowed inspiration vs
official material.

| Aesthetic | Honest implementation |
|---|---|
| Glassmorphism / frosted glass | `backdrop-filter`, layered borders, highlight overlays. Provide solid-fill fallback for `prefers-reduced-transparency`. |
| Bento (Apple-style tile grids) | CSS Grid with mixed cell sizes. No single library owns this. |
| Brutalism | Native CSS, monospace, raw borders. No library. |
| Editorial / magazine | Serif type, asymmetric grid, generous whitespace. No library. |
| Dark tech / hacker | Mono + accent neon, terminal motifs. No library. |
| Aurora / mesh gradients | SVG or layered radial gradients. No library. |
| Kinetic typography | Native CSS animations, scroll-driven animations, GSAP for hijacks. No library. |
| Apple Liquid Glass | Apple documents this for Apple platforms only. No official `liquid-glass.css` exists. Web implementations are approximations using `backdrop-filter` + layered borders + highlights. Label clearly as approximation. |

### System preservation rules

- Inspect existing tokens, primitives, assets, fonts, icons, responsive conventions, and design docs
  first. Preserve a coherent system unless a change is approved and justified.
- Distinguish a design system from a visual language. When the repository already adopts a mature
  system, use its actual supported primitives, tokens, and interaction conventions. Keep one primary
  system per surface; do not mix component grammars or claim official system adoption when only
  approximating its appearance.
- When no system exists, define only the token decisions needed by the active surface.

### Visual system elements

When building or extending a system, make deliberate decisions for each element. Each must serve the
page job, not decorate it.

| Element | Decision |
|---|---|
| color | semantic roles, contrast, one hierarchy; no decorative palette without product purpose |
| type | readable body, purposeful display/utility roles, hierarchy, measure, weights |
| spacing / layout | rhythm, container rules, grid/stack choice, section meaning, stable dimensions |
| radius / elevation | interaction hierarchy and surface meaning, not uniform decoration |
| iconography | familiar symbols for actions, consistent style, accessible labels/tooltips |
| assets | real product/subject imagery, brand material, generated asset only when useful and inspectable |
| motion | state change, orientation, or one signature moment; reduced-motion fallback |
| responsive intent | what stays primary, stacks, scrolls, collapses, or changes mode on narrow screens |

Typography and layout should encode importance. Numbering, eyebrows, dividers, labels, and decorative
structures must express a real sequence, category, or relationship. Do not introduce them merely to
make a screen look designed.

## Signature Move

A signature move is one product-serving typography, imagery, layout, rhythm, or interaction decision.
It is not a collection of decorations. Spend boldness in one memorable place and keep surrounding UI
quiet enough for the job to remain obvious.

- For public/brand surfaces, a real/generated inspectable visual or an immersive product moment may
  be warranted. For an operational screen, decorative imagery is usually noise.
- Motion should signal a state change, guide attention, orient a transition, or carry the signature
  move. Prefer one coordinated moment over scattered animation.
- Restraint does not mean boring. A restrained interface earns its quality through spacing, hierarchy,
  typography, state design, and precise alignment; it does not need ornamental code.
- An expressive direction may justify custom assets or motion, but must still meet performance,
  accessibility, responsive, and maintenance requirements. Distinctive does not mean unpredictable to use.

## Commit to one context-specific direction

Before coding a new visual surface, name the intended tone, the user and setting, the strongest
remembered element, and the implementation constraints. Explore alternatives only when the direction is
genuinely unresolved. Once selected, execute one coherent point of view instead of blending several
fashionable motifs.

For brownfield work, the existing design system and product identity are evidence, not obstacles.
Change them only when the request is a redesign or the current system cannot support the required
hierarchy and states.

---

**Acceptance criteria:** After reading this file, you can output a one-line design read, three
justified dial values (VARIANCE / MOTION / DENSITY), one design-system choice (or honestly labeled
aesthetic direction), and one signature move - all grounded in product facts rather than LLM defaults.
