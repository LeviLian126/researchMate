# AGENTS.md

Guidance for coding agents that maintain this Humanizer package. Keep the package portable across Markdown-based skill hosts and keep the runtime rules, reference catalogues, human-facing documentation, and distribution metadata synchronized.

## What this repository is

Humanizer is a portable writing skill. `SKILL.md` is the control plane: it defines the trigger, the editing contract, invocation modes, and the draft-audit-final loop. The detailed 33-pattern catalogue and technical-document guidance live in `references/` and load only when relevant. There is no required build step.

Do not describe Claude Code, OpenCode, Codex, or another harness as the only supported runtime. Harness-specific plugin files are optional distribution surfaces, not the source of writing behavior.

## Key files

| File | Responsibility |
|---|---|
| `SKILL.md` | runtime entrypoint, core editing contract, routing, modes, and output behavior |
| `references/content-and-language-patterns.md` | patterns 1–13 |
| `references/style-and-communication-patterns.md` | patterns 14–22 |
| `references/filler-rhetoric-and-detection.md` | patterns 23–33 and false-positive guidance |
| `references/technical-documentation-and-bilingual-style.md` | technical artifact contracts and Chinese/English writing guidance |
| `README.md` | installation, usage, pattern index, and version history for people |
| `.claude-plugin/plugin.json` | optional Claude Code package manifest |
| `scripts/validate-package.py` | dependency-free synchronization and package checks |

## The maintenance contract

- **Patterns:** keep patterns 1–33 present exactly once across the three pattern references. If a pattern is added, removed, or renumbered, update the README table, its pattern-count heading, examples, and cross-references in the same change.
- **Version:** keep `metadata.version` in `SKILL.md`, the newest README version-history entry, and `.claude-plugin/plugin.json` synchronized. Keep version under `metadata`; a top-level `version` key is not portable across Agent Skills hosts.
- **Progressive disclosure:** keep `SKILL.md` focused on behavior and routing. Put long catalogues, artifact variants, and detailed examples in the referenced file that owns them. Do not duplicate the same rule in several files.
- **Portability:** preserve valid YAML and avoid nonportable frontmatter keys. Keep install and usage language harness-neutral.
- **Facts and voice:** rewriting must not invent facts, citations, names, dates, numbers, or unsupported specificity. A user writing sample, repository convention, and artifact contract outrank a generic style preference.
- **False positives:** do not treat one dash, passive sentence, formal term, or grammatical prose as proof of AI authorship. New rules need a clear failure pattern and an applicability boundary.
- **Non-obvious fixes:** when a change addresses a recurring mis-edit or tone failure, add a short README version-history note explaining the behavior corrected.

## Editing the instructions

Treat the prompt as a product contract. State the desired result before procedural detail, explain why a non-obvious rule matters, and use hard prohibitions only for consequential failures such as fabrication or loss of source meaning. Preserve the distinction between general prose, technical documentation, legal or reference text, and writing where personality is appropriate.

Do not optimize for detector evasion or claim that the skill can determine authorship. Its purpose is readable, accurate prose that sounds like the intended author and fits the artifact.

## Validation

Run the package validator after every behavioral or metadata change:

```bash
python scripts/validate-package.py
```

Before publishing, also verify that all local references resolve, the pattern sequence is complete, examples preserve source facts, package metadata and license remain present, and any supported host-specific validator still passes.
