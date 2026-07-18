# Durable document quality

Use this protocol after the current delivery owner has recovered the facts, boundaries, evidence, and unknowns needed for a durable document. It applies to maintained README files, PRDs, design documents, change or release notes, HTML project boards, and similar project sources of truth. It does not select the delivery owner, approve an external action, or replace a product, contract, security, release, or evidence gate.

## 1. Establish the document contract

Before drafting, record internally or in the document workspace:

- document type, target reader, intended reader decision or action, maintenance owner, and language;
- existing template, terminology, and durable-document conventions to preserve;
- fact sources, their authority, material unknowns/conflicts, and content that must not be exposed;
- the required sections, acceptance criteria, and whether independent reader testing is available.

Recover these from the repository and current task before asking. Do not invent product, contract, delivery, or operational facts to make a document sound complete. Preserve source literals such as IDs, routes, field names, commands, versions, statuses, and evidence paths.

Use the project's established language; otherwise use English for HTML project documentation. Write in a clear, restrained, professional, neutral voice. Do not manufacture first-person perspective, personality, humor, uncertainty, or irregular rhythm to simulate human authorship.

## 2. Draft and refine

1. Build the full fact inventory and document structure before prose. Put summaries and conclusions last, after the underlying facts and decisions are stable.
2. Write a complete first draft from that inventory. Keep unknowns, conflicts, non-goals, limitations, and evidence visible instead of smoothing them into generic prose.
3. Update the durable artifact only after the complete first draft exists. Then refine each section through its purpose, necessary content, fact/evidence check, and final edit. When the author is available, request one consolidated pass of section feedback and apply it as focused edits. When they are not, complete the evidence and prose audit without blocking or pretending that author feedback occurred.
4. Keep terms stable. Use the same noun for the same actor, action, status, interface, and delivery state unless the source distinguishes them.

## 3. Audit for clarity and artificial prose

Audit the complete draft without weakening its factual or contractual meaning.

- Replace inflated significance, marketing language, vague authority, generic positive conclusions, template "challenges" or "future outlook" sections, chatbot framing, unsupported predictions, invented precision, and filler.
- Prefer concrete evidence, explicit subjects, direct verbs, short plain constructions, and claims a reader can trace to a source.
- Remove needless parallel lists, ornamental transitions, synonym cycling, inconsistent terminology, and claims that restate a heading without adding information.
- Treat em/en dashes, title case headings, mechanical bolding, and emoji as review signals, not automatic violations. Change them only when they make the document less natural, less readable, or inconsistent with its established style.
- Preserve valuable human signals already supported by the source: unusual specific detail, defensible caveats, real limits, project vocabulary, and uncertainty that affects a decision.
- Never remove a status, caveat, risk, contradiction, source path, field name, or contract condition merely to make prose smoother.

## 4. Test the reader model

Use these questions, adapting only the nouns to the stated reader and document:

1. What is the document's core conclusion, current state, or requested decision?
2. Which source or evidence directly supports the most important claim?
3. What boundary, contract, non-goal, or limitation must the reader not infer beyond the document?
4. Which fact is unknown or disputed, and what would resolve it?
5. What should this reader decide, do, or verify next?
6. Which essential term, status, or interface name could be misunderstood, and what does it mean here?

When an authorized isolated reviewer with no task context is available, provide only the document and questions. Use its misunderstandings to revise the affected sections, then repeat the affected questions. Do not treat a reviewer that already knows the repository or author intent as an independent reader test.

When isolated review is unavailable, run a structured self-check against the same questions and mark the handoff as `independent reader test not completed`. This is an allowed limited delivery, but never claim that a new reader validated the document.

## 5. Handoff record

Report the document type and location, source evidence inspected, completed content/style/browser checks, reader-test status, high-risk unknowns or reader-comprehension risks, and the next recommended action. For HTML boards, also follow `agent-context-html` coverage, accessibility, and browser requirements; document density, contract completeness, and evidence labels take priority over stylistic smoothing.
