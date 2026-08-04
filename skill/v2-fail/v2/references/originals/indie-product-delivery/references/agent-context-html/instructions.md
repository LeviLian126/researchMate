# HTML Project Command Board

Build browser-openable project documentation that a founder, developer, or incoming agent can understand without reconstructing the project from chat, Markdown, and source trees. The landing board is the authoritative, evidence-backed snapshot. Put durable detail on focused child pages and material version changes on a separate activity page.

## Load the right reference

Read these files before building the corresponding part of a board:

| Need | Read |
| --- | --- |
| readable prose and document structure | `references/human-readable-document-writing.md` |
| document contract, section refinement, reader testing, and handoff | `references/durable-document-quality.md` |
| project, market, feature, roadmap, architecture, database, or API coverage | `references/agent-context-html/references/content-model.md` |
| HTML Effectiveness reconstruction, spatial forms, layout safety, and interaction | `references/agent-context-html/references/visual-interaction.md` |
| evidence, completeness, privacy, browser, and accessibility checks | `references/agent-context-html/references/validation.md` |

For the default HTML Effectiveness document system, copy `references/agent-context-html/assets/document-system.css` into the output and adapt it instead of regenerating a generic dashboard stylesheet. The file contains the inspected palette, typography, document geometry, spatial components, contract explorers, and nested-layout fixes.

When the user supplies another reference, use this asset only as a layout-safety base. Replace its visual parameters with values inspected from the supplied reference.

Use Node01 as the authority for product meaning, target user, buyer, value, MVP/MAP boundary, pricing, acceptance, and demand evidence. Use Node02 as the authority for system boundaries, contracts, data, trust, runtime shape, technology decisions, and architecture handoff. Do not replace either with a simplified assumption merely because the board needs a concise summary.

## Workflow

1. Establish the durable-document contract: target reader and decision, maintenance owner, existing template/terminology, fact sources, unknowns/conflicts, disclosure boundaries, required sections, and reader-test availability. Use the shared writing and quality protocols for the complete draft, section refinement, writing audit, and reader-test record.
2. Inspect the complete relevant evidence surfaces: code, tests, configuration, migrations/schema, routes or OpenAPI, maintained product documents, runtime-safe observations, and approved external sources. Prefer them in that order when claims conflict.
3. Build a source inventory before writing. Count the capabilities, routes/actions, schemas, database entities and evidenced fields, relationships, policies, architecture components, decisions, risks, and roadmap records in scope. Use this inventory as the coverage manifest. Render every item, mark it unknown, or exclude it with a reason.
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
10. Run the validation reference and shared writing audit. Reconcile source-inventory counts against rendered counts. Open every page in a browser when available, then correct missing records, overflow, nested-grid collisions, keyboard traps, cross-page drift, misleading status wording, unsupported claims, and generic filler. Read the rendered page as a whole and remove repeated section openings, heading restatements, card-per-fact layouts, and other template residue. Record whether independent reader testing ran and state the limitation when it did not.

## Status and evidence discipline

- `shipped`, `done`, or `validated` require direct implementation, deployment, test, configuration, or maintained-contract evidence.
- `in-progress`, `partial`, `blocked`, `candidate`, `deferred`, `unknown`, and `untested` must name the missing proof, decision, dependency, or action that would move them.
- Keep an inferred claim visibly marked as inferred. When sources disagree, show the conflict and lower confidence rather than silently selecting a version.
- Make “real-time” mean the latest inspected evidence snapshot. Never simulate live telemetry or automatic progress updates without an existing, authorized data source.
- Exclude credentials, tokens, raw personal data, private payloads, and exploit details. Summarize their contract or security consequence instead.

## Implementation and handoff

Use semantic HTML, inline or local CSS, inline SVG, and minimal vanilla JavaScript by default. Avoid remote runtime dependencies, frameworks, remote fonts, and network calls unless the existing project or user explicitly requires them.

Changing only colors, fonts, or card styling does not complete a reference-driven task. Match the reference's information geometry: content width, section rhythm, type scale, navigation, borders, radii, spacing, component composition, disclosure patterns, responsive transitions, and focus or interaction states.

Reuse source code or assets only when their license or the user's authorization permits it. Otherwise implement the observed design independently at equivalent visual fidelity.

In the final response, name the changed board, document type, evidence and validation checked, completed writing audit, reader-test status, visible high-risk unknowns or reader-comprehension risks, and the next recommended action. Do not paste the generated HTML into chat.
