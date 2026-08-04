# The unreasonable effectiveness of HTML

> Complete Markdown transcript of the readable homepage content at https://thariqs.github.io/html-effectiveness/. Links are made relative to the preserved Apache-2.0 snapshot in `../originals/html-effectiveness/`. Copyright 2026 Anthropic PBC; licensed under Apache-2.0.

Companion to the blog post.

Twenty self-contained `.html` files an agent produced instead of a wall of markdown. Each one trades a document you'd skim for one you'd actually read — open any of them directly in a browser. Grouped by the kind of work they replace.

- Exploration & Planning — 3
- Code Review — 3
- Design — 2
- Prototyping — 2
- Diagrams — 2
- Decks — 1
- Research — 2
- Reports — 2
- Custom Editors — 3
- [Know your unknowns](../originals/html-effectiveness/unknowns/index.html) — 11

## 01 · Exploration & Planning

When you're not sure what you want yet. Ask the agent to fan out across several directions and lay them next to each other so you can point at one — instead of reading three sequential walls of text and trying to hold them all in your head. And once you've picked, turn the pick into a plan the implementer can actually read.

- [Three code approaches](../originals/html-effectiveness/01-exploration-code-approaches.html) — Side-by-side comparison of three ways to solve the same problem, with trade-offs called out inline.
- [Visual design directions](../originals/html-effectiveness/02-exploration-visual-designs.html) — A handful of layout and palette options rendered live so you can react to them, not imagine them.
- [Implementation plan](../originals/html-effectiveness/16-implementation-plan.html) — Milestones on a timeline, a data-flow diagram, inline mockups, the risky code, and a risk table — the plan you hand off.

## 02 · Code Review & Understanding

Diffs and call-graphs are spatial information; markdown flattens them. Let the agent render the change as an annotated diff, draw the module as boxes and arrows, or write the PR description your reviewers actually want — so the shape of the code is visible at a glance.

- [Annotated pull request](../originals/html-effectiveness/03-code-review-pr.html) — A diff rendered with margin notes, severity tags and jump links — easier to scan than scrolling a terminal.
- [PR writeup for reviewers](../originals/html-effectiveness/17-pr-writeup.html) — The author's side: motivation, before/after, a file-by-file tour with the *why*, and where to focus the review.
- [Module map](../originals/html-effectiveness/04-code-understanding.html) — An unfamiliar package drawn as boxes and arrows, with the hot path highlighted and entry points listed.

## 03 · Design

HTML *is* the medium your design system ships in, so it's the natural format for talking about it. Tokens become swatches, components become contact sheets, and the artifact can be fed straight back into the next prompt.

- [Living design system](../originals/html-effectiveness/05-design-system.html) — Colors, type scale and spacing tokens pulled from a repo and rendered as swatches you can copy from.
- [Component variants](../originals/html-effectiveness/06-component-variants.html) — Every size, state and intent of one component laid out on a single sheet for review.

## 04 · Prototyping

Motion and interaction can't be described, only felt. A throwaway page with the real easing curve or the real click-through tells you in five seconds what a paragraph of prose never could.

- [Animation sandbox](../originals/html-effectiveness/07-prototype-animation.html) — The transition in isolation with sliders for duration and easing, so you can tune it before wiring it in.
- [Clickable flow](../originals/html-effectiveness/08-prototype-interaction.html) — Four screens linked together — enough fidelity to feel whether the interaction is right.

## 05 · Illustrations & Diagrams

Inline SVG gives the agent a real pen. Ask for the figures for a post or a flowchart of a process and get vector art you can tweak by hand or paste straight into the final document.

- [SVG figure sheet](../originals/html-effectiveness/10-svg-illustrations.html) — The diagrams for a blog post, drawn inline so they can be tweaked and copied out one by one.
- [Annotated flowchart](../originals/html-effectiveness/13-flowchart-diagram.html) — A deploy pipeline drawn as a real flowchart — click any step to see what runs, timings, and failure paths.

## 06 · Decks

A handful of `<section>` tags and twenty lines of JS is a slide deck. Point the agent at a Slack thread or a design doc and get something you can arrow-key through in a meeting — no Keynote, no export step.

- [Arrow-key slide deck](../originals/html-effectiveness/09-slide-deck.html) — A short presentation as one HTML file. Left and right to navigate, no build step.

## 07 · Research & Learning

An explainer with collapsible sections, tabbed code samples and a glossary in the margin reads very differently from the same words dumped linearly. The agent can build the scaffolding that makes a new topic navigable.

- [How a feature works](../originals/html-effectiveness/14-research-feature-explainer.html) — "Explain rate limiting in this repo" — TL;DR box, collapsible request-path steps, tabbed config snippets, and an FAQ.
- [Concept explainer](../originals/html-effectiveness/15-research-concept-explainer.html) — Consistent hashing taught with a live ring you can add/remove nodes from, a comparison table, and a hover-linked glossary.

## 08 · Reports

Recurring documents — status updates, post-mortems — benefit most from a bit of structure and color. A small chart and a colored timeline turn something people skim into something they actually read.

- [Weekly status](../originals/html-effectiveness/11-status-report.html) — What shipped, what slipped, and a small chart — formatted for a quick skim on Monday morning.
- [Incident timeline](../originals/html-effectiveness/12-incident-report.html) — A post-mortem with a minute-by-minute timeline, log excerpts and the follow-up checklist.

## 09 · Custom Editing Interfaces

Sometimes it's hard to describe what you want in a text box. Ask for a throwaway editor for the exact thing you're working on — and always end with an export button that turns whatever you did in the UI back into something you can paste into the agent or commit. You stay in the loop; the loop gets tighter.

- [Ticket triage board](../originals/html-effectiveness/18-editor-triage-board.html) — Drag thirty tickets across Now / Next / Later / Cut, then copy the final ordering out as markdown.
- [Feature flag editor](../originals/html-effectiveness/19-editor-feature-flags.html) — Toggles grouped by area, dependency warnings when a prerequisite is off, and a "copy diff" button for just the changed keys.
- [Prompt tuner](../originals/html-effectiveness/20-editor-prompt-tuner.html) — Editable template on the left with variable slots highlighted; three sample inputs on the right re-render live as you type.

Everything on this page is itself a single `.html` file. See also: [Know your unknowns](../originals/html-effectiveness/unknowns/index.html).

View the repo · https://thariqs.github.io/html-effectiveness/
