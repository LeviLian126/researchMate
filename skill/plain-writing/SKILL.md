---
name: plain-writing
description: "Use whenever you create, draft, revise, or review Markdown or HTML prose — documentation, release notes, READMEs, reports, explanations, summaries, or any written deliverable — to keep the writing grounded, specific, and free of AI flavor: direct instead of inflated, hedged, or template-shaped. Apply it whenever the user asks you to write, polish, edit, summarize, 'remove AI tone', 'make it sound human', or 'say it in plain words', or whenever you are about to produce more than a few sentences of prose, even when they don't explicitly ask for a style review. Do not use it for source code, configuration, JSON, lockfiles, or data where only structural correctness matters."
---

# Plain Writing

Write so a person can quickly understand and trust what's on the page. The goal is reader comprehension, not evading a detector or performing a tone — those aren't the same. An evasion-style text still reads as evasive; the aim is plainness and truth.

This is the general, audience-neutral writing skill. When a task has a specific reader (for example, building developer-facing project documentation as HTML), apply it alongside the more specific skill that owns that format.

## Write for a real reader

Identify who reads this and what they need to understand, decide, or do. Recover the existing language, voice, and terminology before drafting; match a supplied author sample or established project voice when present. Lead with what the reader needs first. Use active voice and present tense when they make the actor and behavior clearer. Prefer familiar words, specific nouns, and direct verbs over jargon, ceremony, or marketing language. State requirements as requirements and recommendations as recommendations. Keep technical and reference documents neutral. Don't invent first-person perspective, humor, emotion, or irregular rhythm to simulate an author's voice.

## Preserve truth before style

Keep every supported claim, exception, limitation, non-goal, and unresolved question that affects the reader. Don't add facts, dates, numbers, names, citations, confidence, or specificity the sources don't support — swapping a vague claim for a specific one is allowed only when the specific comes from the source or the user.

Preserve source literals unless the underlying fact changes: commands, paths, identifiers, routes, field names, versions, statuses; quoted text, link targets, code blocks, schemas, configuration; product terms, contract language, evidence labels, domain vocabulary. Don't drop a caveat, risk, or boundary to make a paragraph smoother.

## Choose structure for the information

Paragraphs for explanation and argument, numbered lists for sequences, bullets for independent items, tables for comparable repeated fields. Don't force every idea into a heading, a three-item list, a bold label, or identical section shapes. Delete a sentence that only restates its heading; merge sections when the heading adds no navigation. A table or checklist is fine when it makes a contract faster to scan — prose isn't automatically more human. Keep one name for the same actor, action, status, or interface; don't cycle synonyms to avoid repetition. Describe the system as it is now; reserve change-narration for changelogs and migration notes.

## Remove AI tells

Review the complete draft for combinations of the patterns below. Each is harmless alone; several together read as a generic AI text. Rewrite when several reinforce or one clearly obstructs the reader; prefer a concrete fact, owner, action, condition, example, source, or limit.

- **Inflated significance** — stands as a testament, plays a vital/pivotal/crucial role, underscores its importance, reflects a broader trend, marking a shift, a key turning point. Cut the framing and state the fact.
- **Undue notability** — "widely cited", "extensive coverage", "leading expert", padding with sources for volume. Notability is shown by the facts, not asserted.
- **Superficial -ing analyses** — trailing "-ing" phrases ("...optimizing...", "...streamlining...") that imply analysis without adding a fact. Add the fact or delete.
- **Vague attribution** — "experts say", "many users", "it is often noted". Name the source or drop the claim.
- **Em dash overuse** — a stylistic fingerprint when default. Use them only when the pause earns it; a voice that already uses them keeps its frequency.
- **Rule of three** — forcing ideas into three-part lists, "X, Y, and Z", where two or four is what's true. Don't pad ideas into a triple.
- **AI vocabulary** — seamless, powerful, leverage, robust, delve, landscape, tapestry, navigate the evolving, at the intersection of, where "x meets y". Use the plain project term.
- **Negative parallelism** — "not just X, but Y", "it's not about A, it's about B" as a rhythm rather than a real contrast. Use real contrast or none.
- **Filler and signposting** — chatbot greetings, offers to continue, "Let's dive in", commentary about producing the document, generic "challenges and future outlook" sections.
- **Template shapes** — uniform paragraph lengths, repeated section openings, a card or bold label for every fact, theatrical fragments, manufactured punchlines, aphorisms, fake-candid questions, metaphors replacing a concrete explanation.

Don't use a word blacklist. An em dash, a passive construction, a title-case heading, a technical term, a bold label, a list, or a table is not a defect by itself. Quoted material, proper names, necessary legal/contract language, and an author's habits outrank generic style preferences.

## Read the result as a person would

Before handoff, read the changed prose in context, not just the diff. Confirm a reader can identify: what it's about; the current fact, conclusion, or action needed; the evidence behind material claims; the important limit, unknown, or exception; and what to decide, do, or verify next when a next step exists. Run this audit internally; don't add a style score or an anti-pattern report unless the user asks. Optimize for comprehension, not for evasion.
