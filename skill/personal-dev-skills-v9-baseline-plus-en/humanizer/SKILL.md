---
name: humanizer
description: |
  Improve the naturalness, author consistency, factual fidelity, and readability of prose
  without changing its meaning. Use when editing or reviewing ordinary prose, technical
  documentation, Markdown/HTML project boards, code reviews, release notes, runbooks,
  Chinese/English mixed-language text, or agent-to-user communication. Detect and revise
  clusters of AI-shaped writing patterns, but preserve facts, identifiers, caveats,
  repository conventions, and a user's established voice.
license: MIT
metadata:
  version: "2.9.2"
---

# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human. This guide is based on Wikipedia's "Signs of AI writing" page, maintained by WikiProject AI Cleanup.

## Your Task

When given text to humanize:

1. **Identify AI patterns** - Scan for the patterns listed below.
2. **Preserve the information, not the shape** - Every claim in the original survives into the rewrite, but depth doesn't have to be uniform: compress the dull parts, dwell where a human would, and merge or split paragraphs freely. When keeping the information and mirroring the original's structure pull in different directions, the information wins.
3. **Never invent facts** - The rewrite must not contain any fact, name, number, date, quote, or citation that isn't in the source text. Swapping a vague claim for a specific one is allowed only when the specific comes from the source or from the user; if a sentence needs real-world detail to work, ask for it or write the plain version without it. Opinions and reactions are voice, not facts: where PERSONALITY AND SOUL applies you may add stance, but never new factual claims. (In fiction, invented detail is the job. This rule governs everything else.)
4. **Match the voice** - Fit the intended tone (formal, casual, technical). Add personality only when the content and the author's voice call for it (see PERSONALITY AND SOUL).

How you're invoked changes what you deliver (see Invocation Modes). Run the draft → audit →
final loop internally by default; expose intermediate material only when the user asks for
the audit or alternatives.

## Voice Calibration

If the user provides a writing sample (their own previous writing), analyze it before rewriting:

1. Read the sample first. Note its sentence lengths, vocabulary, paragraph openings, punctuation, recurring phrases, and transitions.
2. Match those habits instead of merely deleting AI patterns. Do not upgrade casual words or regularize deliberate quirks.
3. Without a sample, use the default behavior below.

A sample outranks generic style rules, including the em dash rule in §14: if the sample uses
em dashes, keep them when they serve the author's voice. Accuracy and the artifact's technical
contract still outrank the sample.

## PERSONALITY AND SOUL

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop. Good writing has a human behind it.

**Apply this section only when the content and the author's voice call for it** - blog posts, essays, opinion, personal writing. For encyclopedic, technical, legal, or reference text, neutral and plain *is* the correct human voice; don't inject opinions or first person there.

When voice is appropriate, avoid uniform sentence structures, bloodless neutrality, and perfect organization. Let the writer have opinions, uncertainty, mixed feelings, humor, asides, and uneven rhythm. Never add factual claims to create that personality.

## Load only the pattern set you need

Read the relevant reference before rewriting. Do not load every catalogue for a short or
narrowly scoped edit.

| Text or suspected problem | Read |
|---|---|
| significance inflation, promotional wording, vague attribution, AI vocabulary, false ranges, passive fragments | `references/content-and-language-patterns.md` |
| dash, bold, list, heading, chatbot, cutoff, sycophancy, and communication artifacts | `references/style-and-communication-patterns.md` |
| filler, hedging, generic conclusions, rhetorical scaffolding, manufactured punchlines, and false-positive guidance | `references/filler-rhetoric-and-detection.md` |
| README, API docs, architecture notes, PRs, reviews, runbooks, incidents, release notes, technical explanations, or Chinese/English mixed-language prose | `references/technical-documentation-and-bilingual-style.md` |

Patterns are evidence, not a detector verdict. Preserve isolated features that serve the author, repository convention, or technical meaning. Rewrite clusters that make the prose generic, inflated, evasive, repetitive, or shaped like chatbot correspondence.

## Technical documentation default

For README files, API and architecture notes, reviews, runbooks, release notes, HTML
project boards, and agent-to-user conversation, use a plain, precise technical voice by
default. Preserve identifiers, commands, filenames, evidence status, uncertainty, caveats,
and repository terminology. Remove filler and repetition, but never smooth away a limitation
or turn an inference into a fact. Run this pass after implementation facts and document
structure are stable; it is a default prose pass, not permission to change technical meaning.

If the source already meets the factual, technical, reader, and voice requirements, leave it
unchanged. Do not edit merely to demonstrate that the skill ran.

## Invocation Modes

**Pasted text (default).** The user gives text in the conversation. Run the full loop below
internally and deliver only the final rewrite unless the user asks to see the audit or draft.

**File mode.** The user points at a file. Read it, run the draft → audit → final loop internally, then rewrite the file in place so it ends up containing only the final rewrite. Humanize the prose only: leave code blocks, frontmatter, data, and link targets untouched. In the conversation, report a short summary of what changed rather than pasting the whole rewrite back.

**Embedded mode.** Another task or agent is using this skill as one step of a larger job (a PR description, a commit message, a doc). Run the loop internally and output only the final text. No draft, no audit bullets, no summary. The caller wants prose, not ceremony.

## Process and Output

1. Read the input carefully and identify every instance of the patterns above.
2. Write a **draft rewrite**. Check that it reads naturally aloud, varies sentence length, prefers specific details and simple constructions (is/are/has), and keeps the appropriate register.
3. Internally check two questions: what still sounds machine-shaped, and whether the rewrite
states any fact, name, number, date, or citation that is not in the source. Do not turn these
checks into clarification questions for the user. A fabrication is a defect even when it
sounds more human than the vague original.
4. Revise into a **final rewrite** that addresses them. Apply the dash precedence in §14: author samples and established technical or repository conventions outrank the default general-purpose ban.

In pasted-text mode, deliver the draft, the brief "still-AI" bullets, the final rewrite, and (optionally) a short summary of changes. In file and embedded modes, run the same loop but deliver only what the mode calls for (see Invocation Modes).

## Reference

This skill is based on [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup. The patterns documented there come from observations of thousands of instances of AI-generated text on Wikipedia.

Key insight from Wikipedia: "LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely result that applies to the widest variety of cases."
