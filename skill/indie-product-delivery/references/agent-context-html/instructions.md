# HTML Project Command Board

Build browser-openable project documentation that lets a founder, developer, or incoming agent understand the project without reconstructing it from chat, Markdown, and source trees. The landing board is the authoritative current evidence-backed snapshot. Use focused child pages for durable detail and a separate activity page for material version changes so neither density nor history obscures current truth.

Write documentation in English by default. Use the simplest clear file structure that fits the evidence volume. Keep the landing page compact and split substantial product, delivery, architecture, database, API, or operations material into directly linked topic pages. Do not force every project into the same tree, but do not compress a serious project into one low-density page merely to minimize file count. Use one shared local stylesheet when multiple pages need the same document system.

## Purpose

Make product, commercial, architecture, contract, and delivery truth legible as one coherent documentation set.

## Load the right reference

Read these files before building the corresponding part of a board:

| Need | Read |
| --- | --- |
| document contract, professional-neutral prose, section refinement, reader testing, and handoff | `references/durable-document-quality.md` |
| project, market, feature, roadmap, architecture, database, or API coverage | `references/agent-context-html/references/content-model.md` |
| HTML Effectiveness reconstruction, spatial forms, layout safety, and interaction | `references/agent-context-html/references/visual-interaction.md` |
| evidence, completeness, privacy, browser, and accessibility checks | `references/agent-context-html/references/validation.md` |

For the default HTML Effectiveness document system, copy `references/agent-context-html/assets/document-system.css` into the output and adapt it instead of regenerating a generic dashboard stylesheet. It contains the inspected palette, typography, document geometry, spatial components, contract explorers, and nested-layout fixes from the validated implementation. When the user supplies another reference, use the asset only as a layout-safety base and replace its visual parameters with the inspected reference values.

Use Node01 as the authority for product meaning, target user, buyer, value, MVP/MAP boundary, pricing, acceptance, and demand evidence. Use Node02 as the authority for system boundaries, contracts, data, trust, runtime shape, technology decisions, and architecture handoff. Do not replace either with a simplified assumption merely because the board needs a concise summary.

## Workflow

1. Establish the durable-document contract: target reader and decision, maintenance owner, language, existing template/terminology, fact sources, unknowns/conflicts, disclosure boundaries, required sections, and reader-test availability. Use the shared quality protocol for the complete draft, section refinement, style audit, and reader-test record.
2. Inspect the complete relevant evidence surfaces: code, tests, configuration, migrations/schema, routes or OpenAPI, maintained product documents, runtime-safe observations, and approved external sources. Prefer them in that order when claims conflict.
3. Build a source inventory before writing. Count the capabilities, routes/actions, schemas, database entities and all evidenced fields, relationships, policies, architecture components, decisions, risks, and roadmap records in scope. Use this inventory as the coverage manifest; every item must be rendered, marked unknown, or explicitly excluded with a reason.
4. Assemble the board facts using the content model. Record each material claim with an evidence path or an explicit `unknown`; preserve IDs, field names, commands, versions, routes, and caveats that make verification possible. Do not substitute one or two illustrative examples for an available complete ledger.
5. Organize the documentation in this reading order:
   - **Project summary** — what the product is, who it serves, the current problem, promised outcome, first success, commercial state, and pricing.
   - **Product and delivery** — capability map, journey/MVP boundary, acceptance and validation, plus shipped, in-progress, candidate, deferred, blocked, and unknown work.
   - **Architecture** — user-to-system/data flow, frontend and backend responsibilities, module boundaries, integrations, background work, and recovery/failure paths.
   - **Technology and contracts** — stack and material decisions; database entities and fields; API/actions with request, response, permission, and failure semantics.
   - **Control room** — release/validation state, decision record, evidence confidence, risks, blockers, and prioritized next actions.
6. Keep the landing page decision-oriented: identity, release boundary, commercial state, capability summary, top risks, next action, freshness, and links to every topic page. Put field-level contracts, complete endpoint behavior, detailed architecture, acceptance ledgers, and decision history on their topic pages.
7. Give every required region either source-grounded content or a visible unknown state. Do not omit pricing, API, database, or delivery coverage merely because the project has no evidence yet. Prefer complete ledgers over illustrative samples: document every evidenced route, entity, field, capability, risk, and decision in scope.
8. Keep every current-state page synchronized. For a major release, version, migration, incident, security review, or approved milestone, create or update the local activity page with date/version, changed scope, evidence, impact, and follow-up. Do not add routine refreshes or duplicate current-state prose there.
9. Apply the visual and interaction reference. When the user supplies a reference site, inspect its real DOM, computed styles, dimensions, breakpoints, component states, and interactions instead of approximating its mood from memory. Reconstruct the selected page archetype faithfully while replacing its subject matter with project documentation. Keep essential content visible without JavaScript.
10. Run the validation reference and the shared prose audit. Reconcile source-inventory counts against rendered counts, open every page in a browser when available, correct missing records, overflow, nested-grid collisions, keyboard traps, cross-page drift, misleading status wording, unsupported claims, and generic filler before handoff. Record whether independent reader testing ran; if it did not, state that limitation.

## Status and evidence discipline

- `shipped`, `done`, or `validated` require direct implementation, deployment, test, configuration, or maintained-contract evidence.
- `in-progress`, `partial`, `blocked`, `candidate`, `deferred`, `unknown`, and `untested` must name the missing proof, decision, dependency, or action that would move them.
- Keep an inferred claim visibly marked as inferred. When sources disagree, show the conflict and lower confidence rather than silently selecting a version.
- Make “real-time” mean the latest inspected evidence snapshot. Never simulate live telemetry or automatic progress updates without an existing, authorized data source.
- Exclude credentials, tokens, raw personal data, private payloads, and exploit details. Summarize their contract or security consequence instead.

## Implementation and handoff

Use semantic HTML, inline or local CSS, inline SVG, and minimal vanilla JavaScript by default. Avoid remote runtime dependencies, frameworks, remote fonts, and network calls unless the existing project or user explicitly requires them.

Do not declare a reference-driven result complete after changing only colors, fonts, or card styling. Match the reference's information geometry: content width, section rhythm, type scale, navigation, borders, radii, spacing, component composition, disclosure patterns, responsive transitions, and focus/interaction states. Reuse source code or assets only when their license or the user's authorization permits it; otherwise implement the observed design independently at equivalent visual fidelity.

In the final response, name the changed board, document type, evidence and validation checked, completed style audit, reader-test status, visible high-risk unknowns or reader-comprehension risks, and the next recommended action. Do not paste the generated HTML into chat.
