# Project Board Specification

Build a complete, evidence-grounded HTML documentation set from repository truth. Read this before generating a board.

## Sections
- [Page topology](#page-topology)
- [Coverage manifest](#coverage-manifest)
- [Evidence record](#evidence-record)
- [Required regions and reading order](#required-regions-and-reading-order)
- [Landing page](#landing-page)
- [Current-state and activity pages](#current-state-and-activity-pages)
- [Look — Anthropic docs by default](#look--anthropic-docs-by-default)
- [Implementation](#implementation)
- [Browser validation](#browser-validation)
- [Reader-model test and handoff](#reader-model-test-and-handoff)

## Page topology

Choose page boundaries by information responsibility. Combine low-volume topics when it reads better; split a topic only when a single page would hide complete ledgers behind an overview.

| Surface | Responsibility |
|---|---|
| current snapshot (landing) | project identity, verified release boundary, commercial state, capability summary, top risks, next action, freshness, navigation |
| product | audience, buyer, beneficiary, problem, promise, scenarios, first success, market evidence, alternatives, distribution, pricing, trust, non-goals |
| delivery | capability map, user journeys, MVP/MAP boundary, acceptance, implementation evidence, validation, owner, risk, roadmap status |
| architecture | frontend/backend/data/integration/work/runtime boundaries, request and data flows, ownership, failure/recovery, decisions |
| database contracts | entity map and every evidenced table, field, type, nullability, default, key, constraint, index, tenant rule, RLS, lifecycle, relation |
| API contracts | every evidenced endpoint/action with caller, auth, permission, request, validation, response, status, failure, idempotency/asynchrony, source, test proof |
| operations and decisions | environment/release state, run commands, observability, security, costs, blockers, risks, decision ledger, ordered actions |
| activity | material historical releases, migrations, incidents, security reviews, experiments, approved milestones only |

Keep page names descriptive and navigation consistent; don't introduce modes or a client-side router.

## Coverage manifest

Build a countable inventory before composing pages — this is a completion boundary, not a planning note.

| Source surface | Inventory unit |
|---|---|
| product and roadmap docs | every maintained capability, story/requirement ID, acceptance condition, status-bearing item, price/package fact, risk, decision in scope |
| frontend and backend | every user-visible route/surface and every material action, handler, integration, background job, authorization boundary |
| OpenAPI, route schemas, action contracts | every operation plus every referenced request, response, error, permission, async/idempotency semantic |
| migrations and maintained schemas | every table/entity, every evidenced field, PK/FK, unique/index/check/enum constraint, referential action, RLS/tenant rule, lifecycle rule |
| tests and configuration | every result or setting that supports a shipped/validated/environment/dependency/operational claim |
| architecture and decision records | every material component, boundary, handoff, failure/recovery path, selected option, rejected alternative, revisit trigger |

Record expected and rendered counts by category. Render every inventory item in a full ledger, or record an explicit exclusion with its reason and source. A diagram or summary may precede a ledger but can't replace it. Use examples to explain a pattern only after complete coverage exists; if volume is large, split across linked pages or compact expandable records instead of sampling down to a demo.

## Evidence record

Attach this compact record to material facts, status-bearing rows, diagrams, and decisions:

| Field | Record |
|---|---|
| status | shipped / in-progress / candidate / deferred / blocked / unknown / a validation state |
| evidence | precise source path, test, config, migration, route, command result, maintained doc, or approved external source |
| confidence | confirmed / partial / inferred / absent |
| gap | missing fact, conflict, risk, or the next action that would resolve it |

Keep source labels explaining why the linked source matters; mark inference and conflicts explicitly; never let a status claim outrun its evidence. Exclude credentials, tokens, personal data, raw production payloads, private URLs, and exploit details — preserve only the contract, risk, or control needed to understand the system.

## Required regions and reading order

Give every required region either source-grounded content or a visible `unknown` state; don't omit pricing, API, database, or delivery coverage because evidence is thin yet.

1. **Project summary and market reality** — what the product is, who it serves, current problem, promised outcome, first success, commercial state, pricing.
2. **Capability map and delivery** — capability map, journey/MVP boundary, acceptance and validation, shipped/in-progress/candidate/deferred/blocked/unknown work, implementation evidence.
3. **Architecture and runtime shape** — user-to-system and data flow, frontend/backend responsibilities, module boundaries, integrations, background work, recovery/failure paths.
4. **Technology and data contracts** — stack and material decisions; database entities and fields; API/actions with request, response, permission, and failure semantics.
5. **Control room** — release/validation state, decision record, evidence confidence, risks, blockers, prioritized next actions.

Keep every current-state page synchronized, link the landing page to each topic page, and have each topic link back.

## Landing page

Keep it decision-oriented and compact: identity, release boundary, commercial state, capability summary, top risks, next action, freshness, links to every topic page. Put field-level contracts, complete endpoint behavior, detailed architecture, acceptance ledgers, and decision history on their topic pages.

## Current-state and activity pages

For a major release, version, migration, incident, security review, or approved milestone, create or update the activity page with date/version, changed scope, evidence, impact, and follow-up. Don't add routine refreshes or duplicate current-state prose there. The activity page links from the board, contains only material historical records, and never contradicts or replaces the current snapshot.

## Look — Anthropic docs by default

The default look is the Anthropic docs design: an ivory/off-white paper background, serif headings, a single restrained accent, content-first layout with generous whitespace, and text-led navigation. `assets/document-system.css` already encodes this baseline (the palette tokens, document geometry, spatial components, and nested-layout fixes). Start from it and adapt; don't generate a generic dashboard stylesheet. Essential content renders with JavaScript disabled.

When the user supplies a different reference site, inspect its real DOM, computed styles, dimensions, breakpoints, component states, and interactions. Reconstruct the selected page archetype faithfully while replacing its subject with this project's documentation. Match — at matching viewport sizes — content width, type scale and line height, section rhythm, navigation shape, panel geometry, borders/radii, density, disclosure behavior, breakpoint transitions, focus/interaction states. A palette-only resemblance doesn't pass.

## Implementation

Use semantic HTML, inline or local CSS (start from `assets/document-system.css`), inline SVG, and minimal vanilla JavaScript. Avoid remote runtime dependencies, frameworks, remote fonts, and network calls unless the project explicitly requires them. Reuse source code or assets only when license or authorization permits; otherwise implement the observed design independently at equivalent visual fidelity.

## Browser validation

Open the board directly and confirm essential content renders with JavaScript disabled. At desktop, constrained desktop, tablet, and mobile widths, inspect horizontal overflow, long source paths, dense tables, code blocks, sticky navigation, disclosure controls, and diagrams. Exercise navigation, filters, disclosure, copy controls, and links by keyboard; confirm visible focus, meaningful labels, no keyboard traps. Check contrast, status text/markers beyond color, reduced-motion behavior, semantic headings/landmarks, and labels for non-text visuals.

When a reference governs the look, compare the implementation against the archetype at matching viewports — content width, type scale, section rhythm, navigation, spacing, disclosure behavior, breakpoint transitions, focus/interaction states. Inspect every repeated component instance, not just the first example: nested grids inside half-width cards, the longest heading or path, the densest table, every diagram family, filtered/expanded states. Reject clipped text, overlapping labels or arrows, ordinary-card scrollbars, and page-level horizontal overflow.

Reconcile the coverage manifest before handoff: source capability/status records = rendered records plus explicit exclusions; source operations = endpoint/action index and detail; source entities and all evidenced fields = entity/field records; source relationships/constraints/indexes/access = integrity/access records; source components/decisions/risks/actions = maps or ledgers. Investigate every count mismatch; don't call a page complete when it lists only "representative", "typical", "key", or "example" records unless the user asked for a sample. A missing price, schema, route, deployment fact, or validation result must be visible as `unknown` with a path to resolve it.

## Reader-model test and handoff

Before declaring done, test readability (adapt nouns to the stated reader):

1. What is the board's current conclusion, state, or requested decision?
2. Which source or evidence directly supports the most important claim?
3. What boundary, contract, non-goal, or limitation must the reader not infer beyond the board?
4. Which fact is unknown or disputed, and what would resolve it?
5. What should the reader decide, do, or verify next?
6. Which essential term, status, or interface name could be misunderstood, and what does it mean here?

Record the handoff: board path, facts/evidence inspected, validations run, high-risk unknowns or conflicts, reader-test status (and the limitation if independent review was unavailable), and the next recommended action. Don't claim browser validation you didn't perform.
