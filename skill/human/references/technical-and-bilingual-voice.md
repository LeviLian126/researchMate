# Technical Documentation and Bilingual Style

Use this guide for README files, architecture and API documentation, design notes, PR descriptions, code review findings, runbooks, incident updates, release notes, and technical explanations. Apply the lexical patterns as an audit, not as a mechanical word ban.

## Preserve the technical contract first

Before rewriting, lock facts that must not drift: identifiers, paths, commands, API shapes, versions, dates, numbers, environment names, test results, evidence level, limitations, and security or failure semantics. Do not upgrade "verified locally" to "deployed," "one measured run" to a latency distribution, or "planned" to "implemented." If the source is ambiguous, keep the ambiguity visible or ask for the missing fact.

Read the relevant code, configuration, schema, tests, or maintained document when the task requires accuracy. A fluent rewrite that contradicts the implementation is a regression.

## Write for the reader's next action

Choose the reader and job before the structure. Put the decision, current behavior, risk, or required action first. Background follows only when it helps the reader understand or act.

| Artifact | Lead with | Preserve |
|---|---|---|
| README or guide | what the system does, who it is for, and the shortest valid path | prerequisites, boundaries, commands, expected result, and failure recovery |
| architecture or design note | the problem, selected boundary, and trade-off | owners, data flow, public contracts, alternatives, migration, and unknowns |
| API or schema documentation | observable contract | required and optional fields, validation, auth, errors, compatibility, and examples |
| PR description | motivation and behavioral change | before/after, file or subsystem tour, risk, tests, rollout, and review focus |
| code review finding | violated contract and consequence | location, evidence, severity, and narrow repair direction |
| runbook | trigger condition and immediate action | commands, expected observations, decision points, escalation, and recovery |
| incident update | current impact and containment | known facts, uncertainty, timeline, owner, and next checkpoint |
| release note | user-visible or operator-visible change | eligibility, migration or action required, limitation, and evidence |

## Use a direct technical voice

Address the reader as "you" when giving instructions. Use present tense for current behavior and active voice when the actor matters. Prefer simple verbs: "returns," "stores," "rejects," "retries," and "deletes." Avoid anthropomorphism such as "the server thinks" when the code evaluates a condition.

Use precise technical terms consistently. Do not cycle synonyms for variety when one domain term owns the concept. Explain unfamiliar terms once, then reuse them. Use meaningful names in examples instead of `foo` and `bar` when the names help reveal the contract.

Use sentence-case headings. Follow a heading with an orienting sentence before another heading or a long list. Number procedures; use bullets for short non-sequential sets; use tables when readers compare the same fields across items. Avoid vertical lists where every item is a bold label followed by one sentence. Merge them into prose or a real table when the relationship is the point.

Avoid marketing language, generic praise, and significance inflation. State what changed and the measured consequence. Replace "a powerful, seamless solution" with the behavior that makes the solution useful. Replace vague authority such as "industry best practices say" with a named source or remove the claim.

## Keep links, UI, and examples usable

Use descriptive link text rather than "click here." Follow the repository's relative-link convention and verify new or changed links. When a heading changes, search for deep links that target it. Use code formatting for commands, paths, API elements, filenames, and literal values; use bold text for UI labels only when that convention helps the reader.

Introduce steps with a complete sentence. Put the condition and location before the action: "On the **Settings** page, select..." State optional actions explicitly. Include the expected output or verification where a reader could otherwise misread success.

For experimental features, label the status near the first explanation and state what may change. Do not use a generic warning box when the limitation belongs in the normal explanation.

## Review the finished document

Read the output once for factual preservation and once for human flow. Check that:

- each section answers a distinct reader question;
- claims match the code or cited evidence;
- requirements and recommendations are distinguishable;
- headings, links, examples, and terminology are consistent;
- caveats remain near the claims they limit;
- the ending stops after the useful next action rather than offering generic follow-up help.

A natural technical document can be neutral. Do not inject first person, jokes, opinions, or unevenness merely to prove a human wrote it. Human quality here means judgment, specificity, proportion, and respect for the reader's time.

## Chinese and English technical style

Use the user's language unless asked otherwise. Preserve identifiers and established technical terms when translation would make the text less precise.

## Chinese

Write complete, natural Chinese sentences. Put the subject and action close together. Prefer concrete verbs such as "读取、校验、拒绝、写入、重试、回滚" over noun-heavy constructions such as "进行读取操作" or "实现对……的支持能力." Keep related reasoning in a paragraph instead of splitting every clause into a presentation-style line.

Avoid translation-shaped openings and transitions when they add no information: "值得注意的是、需要指出的是、从某种意义上说、在……方面、基于上述分析、综上所述." Remove formulaic contrasts such as "不仅……更……" unless both halves represent a real distinction. Do not force three parallel phrases, slogan endings, or a broad "未来展望" section.

Keep widely used technical terms in English when that is clearer, and define them in Chinese on first use if the audience needs it. Do not translate identifiers, commands, file paths, API names, library names, or log text. Use Chinese punctuation in prose and code punctuation inside code spans. Do not insert spaces mechanically between every Chinese word and English identifier; follow the repository's existing style consistently.

## English

Use plain international English. Prefer active voice, present tense, contractions when the tone permits, and short concrete verbs. Avoid Latin abbreviations when a full phrase is clearer. Use consistent terminology instead of elegant variation. Keep sentences varied because the ideas vary, not because a detector rewards variance.

Do not imitate corporate marketing or chatbot politeness. Remove "Certainly," "I hope this helps," "let me know," and offers to continue from artifacts that will live in a repository. Avoid title case in headings unless the repository requires it. Use the repository's punctuation and spelling convention; do not normalize a deliberate author voice merely because another convention exists.

## Both languages

A user-provided writing sample outranks generic style preferences unless it conflicts with accuracy, safety, or the artifact's contract. Match the sample's rhythm and level of formality without copying its factual claims into a different context. Preserve useful quirks; remove patterns only when they form a cluster that makes the text generic, inflated, evasive, or obviously machine-mediated.
