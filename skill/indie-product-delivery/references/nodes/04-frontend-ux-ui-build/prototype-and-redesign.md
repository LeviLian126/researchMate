# Prototype and Redesign

> **Goal:** Handle external design material, audit existing work, and modernize safely without breaking
> protected facts.
>
> **Owns:** material classification, redesign audit, modernization priority, image-first workflow, variant exploration, protected facts
>
> **Does NOT own:** visual direction (`visual-direction-and-design-system.md`), browser verification (`browser-proof-and-debug.md`)

## Classify Supplied Material

Treat external material as evidence with limits. A screenshot, Figma frame, export, or prototype is a
candidate input, never an authority above product scope, system contracts, existing accessibility, or
repo truth.

| Material | Useful for | Never authoritative for |
|---|---|---|
| screenshot | hierarchy, density, composition, visual mood | behavior, hidden states, accessibility, data/auth truth |
| Figma / Stitch / v0 | IA experiment, content inventory, component intent | production code, dependencies, backend or permission behavior |
| exported HTML | structure/copy/assets inventory | repo architecture, security, responsive/accessibility completeness |
| brand asset | existing identity, color/type/photo direction | automatic page layout or interaction policy |
| generated image / reference | subject/art direction and asset exploration | factual product proof or live UI state |
| existing site | working routes, conversion, content, behavior to preserve | permission to replace brand/product meaning |

When material conflicts with Node01 scope, Node02 contract, Node03 behavior, current repo system, or
accessibility requirements, preserve the useful intention and rebuild the unsafe detail.

## Audit Existing Work

Classify the work as targeted evolution, broad redesign, or approved repositioning.

- **Targeted evolution:** audit only the affected page and its direct paths. Lower risk, faster
  delivery. ~70% of value at ~40% of risk.
- **Broad redesign:** build a preserve/retire/improve record before implementation. Higher risk,
  requires explicit approval.
- **Approved repositioning:** brand or product identity is changing. Greenfield approach with
  preserved content.

### Preservation checklist

| Area | Preserve / check before style change |
|---|---|
| routes / navigation | URL, anchors, deep links, nav labels, active state, search/wayfinding |
| conversion / forms | fields, names, order, validation, consent, primary CTA, confirmation |
| content / proof | approved claims, pricing, legal copy, testimonials, evidence, brand voice |
| analytics / SEO | event names, metadata, canonical/OG, structured data where relevant |
| behavior / states | auth, permission, loading, empty, error, mobile, accessibility wins |
| brand | logo, wordmark, approved colors/type/assets, trust markers |
| implementation | framework, tokens, primitives, asset path, performance constraints |

## Modernization Priority

Apply changes in this order for maximum visual impact with minimum risk. Stop when the brief is
satisfied.

1. **Typography refresh** - biggest visual lift per unit of risk. Swap default fonts, tighten tracking,
   increase display size, introduce Medium/SemiBold weights.
2. **Color recalibration** - desaturate accents, unify neutrals (one gray family), keep brand accent,
   tint shadows to background hue.
3. **Hover and active states** - add background shift, slight scale (`scale(0.98)`), or translate
   (`-translate-y-[1px]`) on press. Add visible focus rings. Makes the interface feel alive.
4. **Layout and spacing** - proper CSS Grid, `max-w` container, consistent padding, optical alignment,
   double the whitespace for marketing pages.
5. **Replace generic components** - swap cliche patterns (3 equal cards, accordion FAQ, 3-tower
   pricing) for modern alternatives (bento grid, searchable help, highlighted tier).
6. **Add loading, empty, and error states** - skeleton loaders matching final layout, composed empty
   states with next actions, inline error messages. Makes the surface feel finished.
7. **Typography scale and spacing polish** - the premium final touch. Variable font animation,
   outlined-to-fill transitions, text mask reveals.

## Image-First Workflow

For visually critical pages (public heroes, landing pages, portfolios, redesigns where visual quality
matters), follow an image-first workflow when image generation is available:

1. **Generate or obtain reference images first** - do not begin with freeform coding. The image is the
   design source; the code is the translation layer.
2. **One section = one image** (in Codex) - do not compress too many sections into one unreadable
   board. Generate separate large images per section so text, spacing, and typography stay analyzable.
3. **Do not crop old images for section extraction** - cropping destroys spacing accuracy, type scale
   relationships, and layout proportions. Generate a fresh standalone image for each section.
4. **Deeply analyze before implementing** - extract visible text, typography relationships, spacing
   rhythm, button styling, color palette, component structure, and layout logic from each image.
5. **Implement to match the reference** - do not drift into a generic coded layout during
   implementation. Preserve layout logic, spacing rhythm, typography mood, and component style.
6. **Regenerate unclear sections** - if a section image is not clear enough, generate a fresh
   standalone image rather than guessing. Preserve the same visual language across all images.

### Anti-drift rule

A common failure mode is design drift: the generated images look strong, but the coded result becomes
generic. Strictly avoid this. During implementation:
- Do not simplify into default templates.
- Do not replace distinctive sections with generic rows.
- Do not compress generous spacing into dense layout.
- Do not replace strong typography with plain hierarchy.
- Do not remove the page visual identity for convenience.

## Variant Exploration

Variant exploration is optional and limited to public visual-critical pages, an important redesign with
real direction uncertainty, or explicit user request. It is not for dashboard polish, a routine UI bug,
or a surface governed by a mature design system.

When a new frontend page is requested or the user asks to change the current visual direction, create
2-3 simple, visibly different demos for the user to choose from. If the frontend direction is already
established, skip this exploration and follow the existing system.

- Show 2-3 simple, visibly different directions.
- Let the user select the direction before production implementation.
- Extract the selected direction reusable constraints and follow the existing system.
- Do not create comparison servers, persistent taste profiles, telemetry, autonomous generation loops,
  or project-local design artifact systems. The output is an approved direction and implementation
  constraints, not a separate product.

## Protected Facts

Never modify without explicit user approval:

- URL structure / route slugs
- Primary nav labels
- Form field names or order (breaks analytics + autofill)
- Brand logo or wordmark
- Existing legal / consent / cookie copy
- Analytics event names
- Approved claims, pricing, testimonials

Modernize in order: clarity and hierarchy, typography/rhythm, states/feedback, color calibration,
layout composition, then replacement of a section or block. Do not silently change route slugs,
analytics events, form meaning, legal copy, or brand identity.

## Hand Off Protected Facts

State preserve, retire, improve, and deferred items. Update current-state frontend docs only when
durable direction, behavior, state coverage, or asset/system choices changed. Use
`../08-agent-context-html/README.md` when updating a long-lived HTML project board.

---

**Acceptance criteria:** After reading this file, you can classify any external material by its
evidence limits, run a preserve/retire/improve audit on existing work, apply modernization in the
correct priority order, follow the image-first workflow for visually critical pages, explore variants
only when justified, and identify every protected fact that must not change silently.
