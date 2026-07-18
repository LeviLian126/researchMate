# Project Documentation Validation

Use this checklist after generating or refreshing a project HTML documentation set. It is useful only if a new reader can distinguish facts, gaps, contracts, and decisions without re-reading the conversation or source tree.

## Purpose

Verify that the board is complete, evidence-grounded, safe to share, and usable in a browser.

## Workflow

Run the content, evidence, and browser checks below after writing; repair blockers before handoff and state any check that could not be performed.

## Content coverage

- Confirm English is the default output language unless the user or established project requirement explicitly selected another language.
- Confirm the landing page remains a compact current snapshot and substantial product, delivery, architecture, database, API, or operations detail has a clear topic page instead of being reduced to a superficial summary.
- Confirm global navigation reaches every topic page, each child page links back to the current snapshot, page titles are unambiguous, and the same fact does not drift across pages.

Check that each required region contains evidence-backed content or an explicit unknown state:

- project description, target user/buyer/beneficiary, problem, promise, first success, commercial state, and price/entitlement;
- capability map, MVP/MAP boundary, shipped/in-progress/candidate/deferred/unknown delivery state, acceptance, and validation;
- frontend/backend/data/integration/runtime flow with ownership, dependencies, and material failure/recovery behavior;
- technology decisions, database entities and fields, API/actions, authentication/permission, and contract proof;
- release/validation state, risks, blockers, decisions, evidence confidence, and next actions.

For database and API pages, compare the rendered ledgers with the maintained migration/schema and OpenAPI/routes. Sampling a few entities or endpoints is insufficient when complete contracts are available.

Reconcile the coverage manifest before handoff:

- source capability/status records = rendered capability/status records plus explicit exclusions;
- source operations/actions = endpoint/action index and detail records;
- source entities and all evidenced fields = database entity and field records;
- source relationships, constraints, indexes, and access policies = rendered integrity/access records;
- source architecture components, decisions, risks, and actions = rendered maps or ledgers.

Investigate every count mismatch. Do not describe a page as complete when it contains only representative, typical, key, or example records unless the user explicitly requested a sample.

When an activity page exists, check that it is linked from the board, contains only material historical records,
and does not contradict or replace the current snapshot.

Check that a missing price, schema, route, deployment fact, or validation result is visible as `unknown` with a concrete path to resolve it. Do not silently omit a mandatory category.

## Evidence and safety

- Verify every `shipped`, `done`, `validated`, or equivalent claim against a path, test, configuration, command result, maintained contract, or authorized observation.
- Verify every `in-progress`, `partial`, `blocked`, `candidate`, `unknown`, or `untested` item names its gap, dependency, decision, or next action.
- Check source labels explain why the linked source matters. Mark inference and conflicts explicitly.
- Exclude credentials, tokens, personal data, raw production payloads, private URLs, and exploit details; preserve only the contract, risk, or control needed to understand the system.

## HTML and browser checks

- Open the board directly and confirm its essential content renders with JavaScript disabled.
- At desktop, constrained desktop, tablet, and mobile widths, inspect horizontal overflow, long source paths, dense tables, code blocks, sticky navigation, details controls, and diagrams.
- Exercise the table of contents, filters, disclosure controls, copy controls, and architecture links by keyboard. Confirm visible focus, meaningful labels, and no keyboard traps.
- Check contrast, status text/markers beyond color, reduced-motion behavior, semantic headings/landmarks, and labels or alternatives for non-text visuals.
- When a reference site governs the frontend, compare the implementation with the selected reference archetype at matching viewport sizes. Check content width, type scale/line height, section rhythm, navigation, panel geometry, borders/radii, density, disclosure behavior, breakpoint transitions, and focus/interaction states. A palette-only resemblance does not pass.
- Inspect every repeated component instance, not only the first example. Include nested grids inside half-width cards, the longest heading/path, the densest table, every diagram family, and filtered/expanded states. Reject clipped text, overlapping labels or arrows, ordinary-card scrollbars, and page-level horizontal overflow.

## Handoff record

Report the board path, facts/evidence inspected, validations run, high-risk unknowns or conflicts, and the next recommended action. Do not claim browser validation that was not performed.
