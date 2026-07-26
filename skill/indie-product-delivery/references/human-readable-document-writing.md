# Human-readable document writing

Use this guide whenever the skill creates or materially edits Markdown or HTML
documentation. It applies to prose and document structure, not to source code,
data, frontmatter, or link targets.

## Write for a real reader

Identify who will read the document and what they need to understand, decide, or
do. Recover the existing language, voice, terminology, and document conventions
before drafting. Match a supplied author sample or established project voice
when one exists. Use English for new skill documentation unless the repository
or user establishes another language.

Lead with the information the reader needs first. Use active voice and present
tense when they make the actor and behavior clearer. Prefer familiar words,
specific nouns, and direct verbs over jargon, ceremony, or marketing language.
State requirements as requirements and recommendations as recommendations.
Keep technical and reference documents neutral. Do not invent first-person
perspective, humor, emotion, or irregular rhythm to simulate an author.

## Preserve truth before style

Keep every supported claim, exception, limitation, non-goal, and unresolved
question that affects the reader. Do not add facts, dates, numbers, names,
citations, confidence, or specificity that the sources do not support.

Preserve source literals unless the underlying fact changes:

- commands, paths, identifiers, routes, field names, versions, and statuses;
- quoted text, link targets, code blocks, schemas, and configuration;
- product terms, contract language, evidence labels, and domain vocabulary.

Do not remove a caveat, risk, contradiction, permission rule, or recovery
condition to make a paragraph smoother.

## Choose structure for the information

Use paragraphs for explanation and argument, numbered lists for sequences,
bullets for independent items, and tables for repeated fields that readers need
to compare. Do not force every idea into a heading, three-item list, bold label,
card, or identical section shape.

Delete a sentence that only repeats its heading. Merge fragmented sections when
the heading adds no navigation value. Keep a table or checklist when it makes a
technical contract faster to scan; prose is not automatically more human.

Write examples with meaningful project terms. Keep one name for the same actor,
action, status, or interface instead of cycling through synonyms. In current
documentation, describe the system as it is. Reserve change-oriented narration
for changelogs, release notes, migration guides, and other version-scoped
documents.

## Audit clusters of artificial prose

Review the complete draft for combinations of these patterns:

- inflated significance, promotional claims, fake urgency, or generic praise;
- vague authorities, unsupported predictions, invented precision, or
  speculation used to fill a factual gap;
- abstract AI-favored vocabulary where a plain project term would be clearer;
- trailing participle phrases that imply analysis without adding a fact;
- repeated three-part lists, false ranges, slogan-like contrasts, or synonym
  cycling;
- chatbot greetings, signposting, offers to continue, or commentary about
  producing the document;
- template sections such as generic challenges, future outlook, key takeaways,
  or conclusions that add no decision-relevant information;
- uniform paragraph lengths, repeated section openings, mechanical bold labels,
  or a card for every fact;
- theatrical fragments, manufactured punchlines, aphorisms, fake-candid
  questions, or metaphors that replace a concrete explanation.

Rewrite when several signals reinforce each other or when one clearly obstructs
the reader. Prefer a concrete fact, owner, action, condition, example, source, or
limit. End on the last useful conclusion or next action instead of an upbeat
send-off.

Do not use a word blacklist. An em dash, passive construction, title-case
heading, technical term, bold label, list, or table is not a defect by itself.
Quoted material, proper names, necessary legal or contract language, and an
author's established habits outrank generic style preferences.

## Read the result as a person would

Before handoff, read the changed prose in context rather than reviewing only the
diff. Confirm that a reader can identify:

1. what the document is about;
2. the current fact, conclusion, or required action;
3. the evidence or contract behind material claims;
4. the important limit, unknown, or exception;
5. what to decide, do, or verify next, when a next step exists.

Run this audit internally. Do not add a style score, anti-pattern report, or
fixed response template unless the user requests one. Optimize for reader
comprehension, not for evading an AI-writing detector.
