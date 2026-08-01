---
name: project-board
description: "Use when the user wants a self-contained HTML project board, control room, or browser-openable project documentation site that documents the current state of a repo or product from real evidence — capability map, delivery status, architecture, data and API contracts, risks, decisions, and next actions. Build it from repository truth or refresh an existing board. Trigger it whenever the user asks to build, generate, refresh, or make a dashboard, control room, project documentation site, or HTML documentation that shows where the project stands and what to do next, even when they don't call it a 'board'. Do not use it for a one-page Markdown doc, an ad-hoc chart, or an application's UI screens — those are not project-state documentation."
---

# Project Board

A project board is a self-contained HTML documentation set that renders the current truth of a repository or product from real evidence. A founder, a developer, or an incoming agent should be able to open the landing page and understand where the project stands and what to do next without reconstructing it from chat, Markdown, or the source tree.

## What the board contains

Build the board from the reading order in `references/board-spec.md` (page topology, the coverage manifest, the evidence record, required regions, look, and validation). The landing page stays decision-oriented and compact; durable detail lives on focused child pages. Cover what actually exists rather than a generic skeleton:

- **Project summary** — what the product is, who it serves, the current problem, promised outcome, first success, commercial state, pricing. One section that lets a reader decide whether this is real.
- **Delivery state** — capability map, the MVP/MAP boundary, acceptance, and the status of every capability: shipped, in progress, candidate, deferred, blocked, or unknown. A status carries its evidence; an `unknown` carries the path to resolve it.
- **Architecture** — the user-to-system and data flow, frontend and backend responsibilities, module boundaries, integrations, background work, and the recovery or failure paths. Enough that a new engineer knows where a change lands.
- **Contracts** — the technology decisions, the database entities and their evidence-backed field ledgers, and the API or actions with request, response, permission, and failure semantics. Complete ledgers, not a few illustrative endpoints.
- **Control room** — release and validation state, the decision record, evidence confidence, the blockers, and the prioritized next actions. This is the part a lead reads first on a rough morning.

You're free to add anything else that helps a reader act — a glossary, a "how to run it" block, an open-questions list, a risk heat view. The reading order above is the spine, not a ceiling; an agent-friendly handoff means writing what the next reader (human or agent) actually needs, not filling every named field.

## Voice: developer docs, plain and useful

The reader is a developer (or an agent acting for one). Write the way good developer documentation reads: Anthropic and OpenAI's own docs, not a marketing site. The goal is a reader who trusts the page because it's specific, accurate, and free of filler — the opposite of a generic AI dashboard mockup.

- **Lead with the decision.** Each page opens with what the reader came for: what it is, the current state, and what to act on. Put the dense ledgers below; don't bury the answer in setup.
- **Plain over polished.** Simple words, short sentences where they clarify, specific nouns and real verbs. Avoid jargon, hype, and marketing language ("seamless", "powerful", "leverage", "navigate the evolving"). State requirements as requirements and recommendations as recommendations.
- **Active voice and present tense.** "The API returns...", "the worker retries once...". Describe the system as it is now; reserve change-narration for the activity page.
- **One term per thing.** Same noun for the same actor, action, status, and interface. Don't cycle synonyms to dodge repetition.
- **Stable literals are sacred.** Preserve IDs, paths, routes, field names, entities, commands, versions, statuses, and evidence paths exactly — they're how a reader verifies a claim.
- **Show the limits and unknowns.** Keep every caveat, non-goal, conflict, and unresolved question that affects the reader. Don't invent facts, dates, numbers, or citations the sources don't support; an `unknown` with a resolution path beats a smoothed-over paragraph.

Apply the anti-AI-prose audit throughout: cut inflated significance, undue notability, trailing "-ing" non-analysis, vague attribution, the rule-of-three reflex, AI vocabulary, and template shapes (a card for every fact, uniform paragraph lengths, theatrical closers). Don't add generic "challenges and future outlook" sections. A dash, a technical term, a table, or a bold label isn't a defect by itself; the test is whether the reader gets the truth faster.

## Build it self-contained

Use semantic HTML, inline or local CSS (start from `assets/document-system.css`), inline SVG, and minimal vanilla JavaScript. Avoid remote runtime dependencies, frameworks, remote fonts, and network calls unless the project explicitly requires them. Essential content renders with JavaScript disabled. Reuse source or assets only when the license or authorization permits.

## Look: follow Anthropic's docs design

The reference look is the Anthropic docs style — clean, content-first, restrained. When the user supplies a specific reference site, inspect its real DOM, computed styles, dimensions, breakpoints, component states, and interactions rather than approximating its mood from memory, and reconstruct the selected page archetype faithfully while replacing its subject with this project's documentation.

Match information geometry, not just a palette: content width, type scale and line height, section rhythm, navigation shape, panel geometry, borders, radii, spacing, component composition, disclosure patterns, responsive transitions, and focus or interaction states. Changing only colors, fonts, or card styling doesn't complete a reference-driven task; a palette-only resemblance doesn't pass. The included `document-system.css` codifies the inspected palette, typography, document geometry, spatial components, and nested-layout fixes; adapt it to the supplied reference instead of generating a generic stylesheet.

## Truth over coverage theater

The board fails if it samples a few entities or endpoints to look complete. Build the coverage manifest first (counts of capabilities, operations, entities and their fields, decisions, risks), then render every evidenced item, or mark a missing category as `unknown` with a path to resolve it. A summary may precede a ledger but can't replace it. Status words are load-bearing and must stay consistent across pages: `shipped`/`done`/`validated` need direct evidence (test, deploy, config, maintained contract); `in-progress`, `partial`, `blocked`, `candidate`, `deferred`, `unknown`, `untested` must name the missing proof, decision, dependency, or action that would move them.

Exclude credentials, tokens, raw personal data, private payloads, and exploit details; keep only the contract, risk, or control needed to understand the system. Don't simulate live telemetry without an authorized data source; "real-time" means the latest inspected snapshot.

## Handoff

Because the board is handoff documentation for a person or the next agent, end with what makes the handoff work twice: name the board path and the changed pages, the evidence inspected, the browser validations actually run (and the ones not run), the high-risk unknowns or reader-comprehension risks, the current freshness, and the next recommended action. Don't paste the generated HTML into the response. Run the reader-model test in `references/board-spec.md` and record whether independent review ran.
