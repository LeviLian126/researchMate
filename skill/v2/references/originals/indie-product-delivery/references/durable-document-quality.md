# Durable document quality

Use this protocol after the current delivery owner has recovered the facts, boundaries, evidence, and unknowns needed for a durable document. It applies to maintained README files, PRDs, design documents, change or release notes, HTML project boards, and similar project sources of truth.

This protocol does not select the delivery owner, approve an external action, or replace a product, contract, security, release, or evidence gate.

Also apply `references/human-readable-document-writing.md` to the document's prose and structure.

## 1. Establish the document contract

Before drafting, record internally or in the document workspace:

- document type, target reader, intended reader decision or action, and maintenance owner;
- existing template, terminology, and durable-document conventions to preserve;
- fact sources, their authority, material unknowns/conflicts, and content that must not be exposed;
- the required sections, acceptance criteria, and whether independent reader testing is available.

Recover these from the repository and current task before asking. Do not invent product, contract, delivery, or operational facts to make a document sound complete. Preserve source literals such as IDs, routes, field names, commands, versions, statuses, and evidence paths.

## 2. Draft and refine

1. Build the full fact inventory and document structure before prose. Put summaries and conclusions last, after the underlying facts and decisions are stable.
2. Write a complete first draft from that inventory. Keep unknowns, conflicts, non-goals, limitations, and evidence visible instead of smoothing them into generic prose.
3. Update the durable artifact only after the complete first draft exists. Refine each section for purpose, necessary content, facts, evidence, and readability. When the author is available, request one consolidated feedback pass and apply focused edits. Otherwise complete the evidence and writing audit without pretending that author feedback occurred.
4. Keep terms stable. Use the same noun for the same actor, action, status, interface, and delivery state unless the source distinguishes them.

## 3. Test the reader model

Use these questions, adapting only the nouns to the stated reader and document:

1. What is the document's core conclusion, current state, or requested decision?
2. Which source or evidence directly supports the most important claim?
3. What boundary, contract, non-goal, or limitation must the reader not infer beyond the document?
4. Which fact is unknown or disputed, and what would resolve it?
5. What should this reader decide, do, or verify next?
6. Which essential term, status, or interface name could be misunderstood, and what does it mean here?

When an authorized isolated reviewer with no task context is available, provide only the document and questions. Use its misunderstandings to revise the affected sections, then repeat the affected questions. Do not treat a reviewer that already knows the repository or author intent as an independent reader test.

When isolated review is unavailable, run a structured self-check against the same questions and mark the handoff as `independent reader test not completed`. This is an allowed limited delivery, but never claim that a new reader validated the document.

## 4. Handoff record

Report the document type and location, source evidence inspected, completed content, writing, and browser checks, reader-test status, high-risk unknowns or comprehension risks, and the next recommended action.

For HTML boards, also follow `agent-context-html` coverage, accessibility, and browser requirements. Document density, contract completeness, and evidence labels take priority over stylistic smoothing.
