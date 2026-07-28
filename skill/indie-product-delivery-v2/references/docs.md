# Durable Documents (Delivery)

A durable document is a *maintained source of truth* within a delivery: README, PRD, design doc, release or change note, or HTML project board. It outlives the task that produced it, so people will read it later without your context. This reference covers the durable-doc specifics — fact-grounding, the document contract, a reader-model test, and the handoff record. It applies on top of the generic prose rules (which live in the `plain-writing` skill when available; see the short fallback below).

## Prose fallback

Keep prose grounded and direct regardless of whether `plain-writing` is loaded: don't add facts, dates, numbers, or specificity the sources don't support; preserve source literals (IDs, routes, field names, commands, versions, statuses); lead with what the reader needs first; don't remove a caveat or boundary to smooth a paragraph; drop filler send-offs, inflated significance, and template sections that add no decision-relevant information. The full anti-AI-prose audit lives in the `plain-writing` skill — this line is just so delivery stays self-sufficient.

## Document contract

Before drafting a durable doc, recover from the repository and the current task (before asking the user):

- document type, target reader, the decision or action the reader should take, and the maintenance owner;
- existing template, terminology, and durable-document conventions to preserve;
- fact sources and their authority, material unknowns/conflicts, and content that must not be exposed;
- the required sections, acceptance criteria, and whether an independent reader is available.

Preserve source literals exactly — IDs, routes, field names, commands, versions, statuses, evidence paths. Don't invent product, contract, delivery, or operational facts to make a document sound complete.

## Draft and refine

1. Build the full fact inventory and document structure before prose; put summaries and conclusions last, after the facts and decisions are stable.
2. Write a complete first draft from that inventory; keep unknowns, conflicts, non-goals, limitations, and evidence visible instead of smoothing them into generic prose.
3. Update the durable artifact only after the complete first draft exists. Refine each section for purpose, necessary content, facts, evidence, and readability. Keep the same noun for the same actor, action, status, interface, and delivery state unless the source distinguishes them.

## Reader-model test

Use these questions, adapting only the nouns to the stated reader and document:

1. What is the document's core conclusion, current state, or requested decision?
2. Which source or evidence directly supports the most important claim?
3. What boundary, contract, non-goal, or limitation must the reader not infer beyond the document?
4. Which fact is unknown or disputed, and what would resolve it?
5. What should this reader decide, do, or verify next?
6. Which essential term, status, or interface name could be misunderstood, and what does it mean here?

When an isolated reviewer with no task context is available, give only the document and the questions; revise from what it misunderstands, then repeat the affected questions. A reviewer who already knows the repository or your intent isn't an independent reader test. When isolated review is unavailable, run a structured self-check against the same questions and mark the handoff `independent reader test not completed` — an allowed limited delivery, but never claim a new reader validated the document.

## Handoff record

Report the document type and location, source evidence inspected, completed content/writing/browser checks, reader-test status, high-risk unknowns or comprehension risks, and the next recommended action. For a durable *HTML* board, the `project-board` skill carries the board-specific coverage, evidence, reading-order, and browser requirements.

## When the deliverable is an HTML board

If the durable artifact is a self-contained HTML project board, use the `project-board` skill rather than this reference: it covers page topology, the coverage manifest, the evidence record, the required reading order, reference-driven look, and browser validation. The durable-doc contract and reader-model test above still apply — a board is a maintained source of truth too.
