# Anti-Default Directives

> **Goal:** Verify a surface contains no named anti-patterns before shipping. This is a cross-stage
> reference usable during direction-setting, implementation, and verification.
>
> **Owns:** anti-AI-average-design philosophy, named anti-patterns with override conditions, pre-flight checklist
>
> **Does NOT own:** direction selection (`visual-direction-and-design-system.md`), browser verification (`browser-proof-and-debug.md`)

## Anti-AI-Average Design Philosophy

Two anti-pattern logics, unified by one principle: do not select an aesthetic because it is an LLM
default or because another product page recently used it.

### 1. Public / brand surfaces: reject templated decoration

Actively reject these defaults unless the brief makes them right: generic centered hero, purple/blue
gradient atmosphere, three equal feature cards, decorative icon circles, uniform bubbly radii,
card-on-card sections, fake dashboards, stock-like visual crops, filler badges, invented metrics, and
motion without meaning.

### 2. Operational surfaces: reject fake density and hidden visibility

Reject: equal metric cards, decorative panels around every group, hidden action affordance, small
unreadable text, hover-only discovery, inconsistent spacing, data-shaped hierarchy (metrics that do not
change a decision occupying primary position), and decorative imagery on operational screens (usually
noise).

A refined operational tool earns distinctiveness through clarity, rhythm, type hierarchy, and
disciplined density - not spectacle.

## Brownfield vs Greenfield Override

- **Brownfield:** the existing design system and product identity are evidence, not obstacles. Change
  them only when the request is a redesign or the current system cannot support the required hierarchy
  and states. "Avoid AI defaults" does not mean redesigning an existing system because a nearby style
  looks dated. Preserve working value; improve clarity.
- **Greenfield:** this is the main battlefield for "avoid interchangeable cards, generic system
  typography, purple-on-white gradients, decorative glass, and motion with no product meaning." Reach
  past LLM defaults deliberately based on the design read.

## Named Anti-Patterns

Each entry: what it looks like, why it is bad, when it is acceptable (override), and what to use instead.

### Color

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| AI-purple / blue glow | Purple button glows, random neon gradients, purple-on-white atmosphere | Brand or brief explicitly asks for purple; execute with intent and harmonized neutrals | Neutral bases (Zinc / Slate / Stone) with one high-contrast accent (Emerald, Electric Blue, Deep Rose, Burnt Orange) |
| Premium-consumer beige+brass+espresso | Backgrounds `#f5f1ea` `#f7f5f1` `#fbf8f1` `#efeae0`; accents `#b08947` `#b6553a` `#9a2436` `#9c6e2a`; text `#1a1714` `#1b1814` | Brand brief explicitly names those colors, or brand identity is genuinely vintage / artisan / warm-craft | Rotate: Cold Luxury (silver-grey + chrome), Forest (deep green + bone + amber), Black and Tan (off-black + warm tan), Cobalt + Cream, Terracotta + Slate, Olive + Brick, Pure monochrome + single saturated pop |
| Mixed warm and cool grays | Warm gray text with cool gray borders in the same project | Never acceptable within one project | Stick to one gray family. Tint all grays with a consistent hue. |
| Multiple accent colors | Rose CTA, teal badge, blue link, orange highlight on the same page | A genuinely multi-category data visualization requires distinct hues | One accent color, locked across the whole page. A warm-grey site does not get a blue CTA in section 7. |

### Typography

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Inter as default sans | Inter everywhere with no brand justification | User explicitly asks for neutral / standard / Linear-style feel, or public-sector / accessibility-first site | Geist, Outfit, Satoshi, Cabinet Grotesk first |
| Fraunces or Instrument_Serif as default serif | Creative brief triggers serif default automatically | Brand brief literally names that serif, or aesthetic family is genuinely editorial / luxury / publication AND you can articulate why this specific serif fits | Rotate from: PP Editorial New, GT Sectra Display, Cardinal Grotesque, Reckless Neue, Tiempos Headline, Recoleta, Cormorant Garamond, Playfair Display, EB Garamond, IvyPresto, Migra, Editorial Old, Saol Display, Domaine Display, Canela, Schnyder |
| Mixed-family emphasis | Random serif word injected into a sans headline for visual interest | Never acceptable | Italic or bold of the same font family |
| Italic descender clipping | Italic display text with descender letters (y g j p q) at `leading-none` or `leading-[1]` | Never acceptable | `leading-[1.1]` minimum + `pb-1` or `mb-1` reserve on wrapping element |
| All-caps subheaders everywhere | Every section label is `uppercase tracking-widest` | Genuine small-caps design system or regulatory/legal labeling convention | Lowercase italics, sentence case, or small-caps with positive tracking |

### Layout

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Centered hero when VARIANCE > 4 | Generic centered H1 + subtext + two CTAs stacked | Editorial / manifesto / launch-announcement where the message itself is the design | Split screen (50/50), left-aligned content / right-aligned asset, asymmetric whitespace, scroll-pinned structures |
| Three equal feature cards | Three identical-width cards in a row as the feature section | Brief has exactly three equal-weight features and no better composition exists | 2-column zig-zag, asymmetric grid, bento with mixed cell sizes, horizontal scroll, masonry |
| Card-on-card sections | Cards inside larger cards inside outer panels | Genuine nested data hierarchy where each layer communicates a different abstraction level | Open layouts with `border-t`, `divide-y`, or negative space. Use cards only when elevation communicates real hierarchy. |
| `h-screen` for full-height sections | `height: 100vh` causing layout jump on mobile (iOS Safari address bar) | Never acceptable | `min-h-[100dvh]` |
| Flexbox percentage math | `w-[calc(33%-1rem)]` for multi-column layouts | Never acceptable | CSS Grid: `grid grid-cols-1 md:grid-cols-3 gap-6` |
| No max-width container | Content stretches edge-to-edge on wide screens | Genuine full-bleed immersive hero or map | `max-w-[1400px] mx-auto` or `max-w-7xl` |
| Uniform border-radius on everything | Same `rounded-lg` on buttons, cards, inputs, containers | Documented rule with consistent application (e.g. "buttons are full-pill, cards are 16px, inputs are 8px") | Vary radius by element type: tighter on inner elements, softer on containers |
| Pure-black drop shadows | `box-shadow: 0 4px 12px rgba(0,0,0,0.15)` on light backgrounds | Never acceptable on light backgrounds | Tint shadows to the background hue. Use colored shadows (dark blue shadow on blue background). |
| Decorative glass everywhere | `backdrop-blur` on every surface with no hierarchy reason | Genuine glassmorphism aesthetic with fallback for `prefers-reduced-transparency` | Use glass only on one elevated layer (navbar, one modal). Use opaque surfaces elsewhere. |

### Content

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Generic names | "John Doe", "Jane Smith", "Acme Corp", "Nexus", "SmartFlow", "Flowbit" | Never acceptable | Diverse, realistic-sounding names. Contextual, believable brand names. |
| AI copywriting cliches | "Elevate", "Seamless", "Unleash", "Next-Gen", "Game-changer", "Delve", "Tapestry", "In the world of..." | Never acceptable | Plain, specific language. Active voice. Concrete verbs. |
| Fake round numbers | 99.99%, 50%, $100.00, 1M users | Never acceptable | Organic, messy data: 47.2%, $99.00, +1 (312) 847-1928, 12,847 users |
| Passive voice | "Mistakes were made", "Your request was processed" | Regulatory or legal text requiring passive voice | Active voice: "We couldn't save your changes", "We processed your request" |
| Lorem Ipsum | Latin placeholder text | Never acceptable | Real draft copy. If none exists, write functional placeholder text in the product voice. |
| Title Case On Every Header | Every heading uses Title Case | Established style guide requires Title Case | Sentence case for most headings. Reserve Title Case for proper nouns. |

### Operational UI (node04 exclusive)

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Fake density | Equal-size metric cards in a row, decorative panels around every group | Genuine dashboard where every metric changes a decision | Plain layout. Metrics breathe. Group with `border-t` or `divide-y`. |
| Hover-only action discovery | Row actions, delete buttons, or settings only visible on hover | Never acceptable on touch or operational surfaces | Actions visible without hover. Use icon buttons with labels. On tables, show actions in a dedicated column. |
| Unreadable small text | `text-xs` or smaller for primary information | Fine print / legal disclaimers / secondary metadata | `text-sm` minimum for operational text. `text-base` for primary information. |
| Inconsistent spacing | Random padding values, no rhythm | Never acceptable | Consistent spacing scale. Use token-based spacing. |
| Data-shaped hierarchy | Metrics that do not change a decision occupying primary screen position | A metric is genuinely the primary decision driver | Decision/action first. Show metrics only when they change a decision. |
| Hidden action affordance | Buttons styled as text, links styled as static text, no visible interactive cue | Design system uses text-only buttons with documented hover/focus states | Buttons look actionable without hover. Use background fill, border, or icon for affordance. |
| Decorative imagery on operational screens | Stock photos, illustrations, or gradient blobs on admin panels | Onboarding or empty-state illustration with clear purpose | No decorative imagery. Use real data, status indicators, and actionable UI. |

### Components

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Generic card look | `border + shadow + white background` on every grouping | Never acceptable as default | Remove border, use only background color, or use only spacing. Cards exist only when elevation communicates hierarchy. |
| Always one filled + one ghost button | Every CTA group has one primary filled + one secondary outline | Genuine secondary action that is equally important | Text links or tertiary styles to reduce visual noise. |
| Pill "New" / "Beta" badges | Rounded pill badges for status labels | Established design system uses pill badges consistently | Square badges, flags, or plain text labels. |
| Accordion FAQ sections | Expandable accordion for every FAQ | Short FAQ with 3-5 items | Side-by-side list, searchable help, or inline progressive disclosure. |
| 3-card carousel testimonials | Three testimonial cards with dot navigation | Never acceptable as default | Masonry wall, embedded social posts, or a single rotating quote. |
| Pricing table with 3 towers | Three pricing columns of equal height | Genuine 3-tier pricing with clear differentiation | Highlight the recommended tier with color and emphasis, not just extra height. |
| Modals for everything | Popup modal for simple actions | Destructive confirmation or complex form requiring focus | Inline editing, slide-over panels, or expandable sections. |
| Hand-built fake dashboard | Decorative dashboard mockup as product proof | Never acceptable as proof | Real screenshot, actual mini-component, or no visual when the page job is clearer without one. |
| Arbitrary gradient blob as product proof | Abstract gradient shape pretending to show the product | Never acceptable as proof | Real product image, relevant photography, or no visual. |

### Iconography

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Lucide / Feather exclusively | Default icon set with no consideration | Project already depends on Lucide, or user explicitly asks for it | Phosphor Icons, HugeIcons, Radix UI Icons, or Tabler Icons. One family per project. Standardize `strokeWidth` globally (1.5 or 2.0). |
| Cliche metaphor icons | Rocketship for "Launch", shield for "Security", lightbulb for "Idea" | Never acceptable as default | Less obvious icons: bolt, fingerprint, spark, vault. |
| Inconsistent stroke widths | Mixed `strokeWidth` values across icons in the same project | Never acceptable | Audit all icons. Standardize to one stroke weight. |
| Hand-rolled SVG icons | Custom-drawn icon paths for standard actions | A glyph is genuinely missing from all libraries and custom design is warranted | Install a second library or compose from primitives. Never draw icon paths from scratch. |
| Missing favicon | No favicon or default browser icon | Never acceptable | Always include a branded favicon. |

### Assets

| Anti-pattern | What it looks like | Override | Use instead |
|---|---|---|---|
| Stock-like visual crops | Blurred, cropped, atmospheric stock photos that do not show the real product | Atmospheric background for a brand hero with real product visual elsewhere | Real screenshot, actual mini-component, generated asset, relevant photography, or no visual. |
| Filler badges | Decorative badges, trust seals, or certifications that are not real | Real certifications with verifiable links | Remove filler badges. Show only real, verifiable trust signals. |
| Invented metrics | "99.99% uptime", "1M+ users", "Trusted by Fortune 500" without evidence | Real metrics with evidence | Remove unverifiable claims. Show only metrics you can prove. |
| Photo-credit captions as decoration | "Field study no. 12 - Ines Caetano" style captions on marketing pages | Genuine editorial publication with real photography credits | Remove decorative captions. |
| Version footers on marketing pages | "v1.4.2", "Build 0048" on marketing or landing pages | Developer documentation or internal tool | Remove version labels from marketing pages. |

## Pre-Flight Checklist

Run this matrix before outputting code. This is the last filter. If any box fails, the output is not done.

**This is not optional. Run every box. If any box fails, fix it before delivering.**

### Brief and direction

- [ ] Brief inference declared (one-line design read from `visual-direction-and-design-system.md`)?
- [ ] Dial values explicit and reasoned from the brief, not silently using baseline?
- [ ] Design system chosen from the system map, or aesthetic labeled honestly?
- [ ] Redesign mode detected and audit performed (if applicable, see `prototype-and-redesign.md`)?

### Color and theme

- [ ] No AI-purple / blue glow as default aesthetic?
- [ ] One accent color used identically across all sections (color consistency lock)?
- [ ] One theme (light, dark, or auto) for the whole page - no mid-page section flips?
- [ ] If premium-consumer brief: palette is NOT the beige+brass+espresso family?
- [ ] No mixing warm and cool grays within the same project?
- [ ] Shadows tinted to background hue, no pure-black drop shadows on light backgrounds?

### Typography

- [ ] Default sans is NOT Inter (or Inter is explicitly justified)?
- [ ] If serif is used: NOT Fraunces or Instrument_Serif (or explicitly brand-justified)?
- [ ] Different serif from your previous project (rotation)?
- [ ] No mixed-family emphasis (italic/bold of same family instead)?
- [ ] Every italic word with descender letters (y g j p q) has `leading-[1.1]` min + `pb-1`?
- [ ] No all-caps subheaders everywhere (sentence case or intentional small-caps instead)?

### Layout

- [ ] No centered hero when VARIANCE > 4 (unless editorial/manifesto)?
- [ ] No three equal feature cards as default?
- [ ] No card-on-card sections (cards only when elevation communicates hierarchy)?
- [ ] `min-h-[100dvh]` used, not `h-screen`?
- [ ] CSS Grid used for multi-column, not flexbox percentage math?
- [ ] `max-w` container present (no edge-to-edge stretch)?
- [ ] One corner-radius system applied consistently (or documented mixed rule)?
- [ ] No section flips to inverted mode mid-page?
- [ ] No 3+ consecutive sections with the same image+text-split layout?

### Content

- [ ] No generic names (John Doe, Acme Corp, Nexus, Flowbit)?
- [ ] No AI copywriting cliches (Elevate, Seamless, Unleash, Next-Gen)?
- [ ] No fake round numbers (99.99%, 50%, $100.00)?
- [ ] No Lorem Ipsum?
- [ ] Sentence case for most headings (not Title Case everywhere)?
- [ ] No em-dashes used as AI-style punctuation in visible UI text?
- [ ] Every visible string re-read for vague claims, forced metaphors, unverified numbers?

### Operational UI (if applicable)

- [ ] No fake density (equal metric cards, decorative panels around every group)?
- [ ] Actions visible without hover (no hover-only discovery)?
- [ ] `text-sm` minimum for operational text (no unreadable `text-xs`)?
- [ ] Metrics only shown when they change a decision?
- [ ] Buttons and rows visibly actionable without hover?
- [ ] No decorative imagery on operational screens?

### Mobile and multi-resolution (see `component-responsive-accessible-build.md`)

- [ ] Tested at 360px (small Android), 390px (standard iPhone), 768px (tablet portrait)?
- [ ] No component stacking/overlap at any tested viewport?
- [ ] No horizontal overflow at any tested viewport?
- [ ] Touch targets >= 44x44 CSS px with >= 8px spacing between adjacent targets?
- [ ] Fixed/sticky elements do not cover primary actions or interactive content?
- [ ] Primary action visible without hover on all viewports?
- [ ] Navigation reachable on all viewports?
- [ ] No `overflow-x: hidden` used to mask a layout problem (fixed the root cause instead)?

### Components and icons

- [ ] Icons from an allowed library (Phosphor / HugeIcons / Radix / Tabler), no hand-rolled SVG paths?
- [ ] One icon family per project, standardized strokeWidth?
- [ ] No cliche metaphor icons (rocket=launch, shield=security)?
- [ ] Favicon included?
- [ ] No accordion FAQ as default (unless short 3-5 item FAQ)?
- [ ] No 3-card carousel testimonials as default?
- [ ] Empty / loading / error states provided?

### Motion

- [ ] Every animation justified in one sentence (hierarchy / storytelling / feedback / state transition)?
- [ ] No animation using `top` / `left` / `width` / `height` (transform and opacity only)?
- [ ] No `window.addEventListener('scroll')` (using `useScroll()` / IntersectionObserver / CSS scroll-driven)?
- [ ] Reduced motion fallback provided for everything with MOTION > 3?
- [ ] `useEffect` animations have strict cleanup functions?

### Assets

- [ ] Real images used (gen-tool first, then Picsum-seed, then explicit placeholder slots)?
- [ ] No div-based fake screenshots?
- [ ] No hand-rolled decorative SVGs?
- [ ] No pure-text minimalism when images are warranted?
- [ ] No stock-like visual crops?
- [ ] No filler badges or invented metrics?
- [ ] No hand-built fake dashboard or gradient blob as product proof?

### Accessibility

- [ ] Button text readable against button background (WCAG AA 4.5:1 for body, 3:1 for large text)?
- [ ] Form inputs, placeholders, focus rings, labels pass WCAG AA?
- [ ] Focus-visible indicators present?
- [ ] Keyboard path tested for changed controls?
- [ ] Dialog focus management and return focus after close?
- [ ] Semantic HTML used before ARIA?
- [ ] `alt` text on meaningful images?

### System integrity

- [ ] One design system per project (no Material + shadcn mixed)?
- [ ] No nested-box layouts (cards inside cards inside cards)?
- [ ] No giant rounded wrapper sections around everything?
- [ ] No fake technical pills and decorative micro-labels?
- [ ] No scroll cues ("Scroll", "scroll to explore")?
- [ ] No section-numbering eyebrows ("00 / INDEX", "001 - Capabilities")?
- [ ] No decoration text strip at hero bottom ("BRAND. MOTION. SPATIAL.")?

---

**Acceptance criteria:** After reading this file, you can identify each anti-pattern by its concrete
identifier (hex values, font names, layout patterns), state the override condition (brownfield vs
greenfield / brand explicitly requires it), and run the pre-flight checklist to verify all boxes pass
before delivering.
