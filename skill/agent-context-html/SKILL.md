---
name: agent-context-html
description: generate and update a dense static html context dashboard for coding-agent handoff and repository resumption. use when the user asks to capture current project state, summarize repo structure, convert handoff notes into an html status page, help codex/claude/cursor/copilot/gstack resume work, build a human/agent-readable dashboard, or package a static context artifact from AGENTS.md, CLAUDE.md, TASK_STATE.md, .agent files, memory-bank docs, gstack artifacts, git status, recent commits, tests, blockers, and next steps.
---

# Agent Context HTML

## Core purpose

Produce a fast handoff artifact, not a project brochure. The output is a static HTML dashboard that lets a human or coding agent understand the current repository state in under two minutes and resume safely.

This skill is optimized for repository resumption, agent handoff, and context recovery. It borrows the operating shape of gstack-style skills such as `office-hours` and `plan-ceo-review`: run a preflight, recover context before acting, separate facts from inference, preserve user decision authority, produce a completion status, and leave a durable artifact.

## Compatibility contract

The top-level `SKILL.md` is ChatGPT-native and therefore keeps only `name` and `description` in YAML frontmatter. Do not add gstack-only YAML fields such as `allowed-tools`, `triggers`, `gbrain`, or `preamble-tier` to this file because native skill packaging expects only `name` and `description`.

For Claude Code / gstack-style installation, consult `references/gstack-porting.md`. It contains the equivalent `allowed-tools`, trigger list, context queries, preamble behavior, and routing notes to copy into a gstack skill file.

## Operating rules

- Treat `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `TASK_STATE.md`, `.agent/`, `memory-bank/`, gstack project artifacts, handoff notes, git status, git log, and repo structure as source material.
- Separate facts, inferred summaries, stale or missing information, and action recommendations.
- Optimize for resumption: current objective, next action, blockers, changed files, tests, risks, and commands must appear before background explanation.
- Use HTML only to improve readability: status ribbon, source confidence, section anchors, code/file chips, timelines, tables, collapsible details, copyable resume prompt, and compact repo map.
- 输出网页主体应以中文为主，专有名词、代码标识、状态词和必要小标题可保留英文；写入 HTML 时必须使用 UTF-8，避免中文变成 `?` 乱码。
- Do not turn the output into a marketing page, product landing page, generic documentation site, or architecture essay unless the user explicitly asks.
- Do not invent project facts. If no handoff or state file exists, reconstruct from git and mark the result as inferred.
- Keep external facts out of the generated page unless the user asks for public-source context. Generated HTML must not load remote assets.
- Prefer dedicated file inspection over broad shell scans when operating inside an agent runtime that provides Read/Grep/Glob/Edit tools. Use scripts for deterministic generation and validation.

## GStack-influenced protocol

Before generating or refreshing the dashboard:

1. Detect repo root, branch, dirty state, recent commits, and candidate context files.
2. Recover newest useful artifacts from repo-local files first, then optional gstack project directories when available.
3. Build a source pack that marks each item as source fact, inference, missing source, conflict, or stale signal.
4. If the current objective or requested output is ambiguous and the ambiguity affects safety, scope, or next action, stop and ask one decision question. Do not silently default.

During long runs, emit brief progress notes with what is done, next, and any surprise. Do not mutate git state just to produce progress notes.

After generation:

1. Validate the static dashboard.
2. Report a completion status using `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT`.
3. Include evidence: generated paths, validation command/result, sources used, missing sources, and limitations.
4. If a durable operational learning would save future agents time, suggest adding it to the repo's agent instructions or context ledger.

## Progressive loading

Load only what is needed:

- Read `references/workflow.md` for the full build or update process.
- Read `references/source-priority.md` before choosing what counts as source of truth.
- Read `references/dashboard-spec.md` before designing the HTML sections.
- Read `references/gstack-compatibility.md` before claiming compatibility with uploaded gstack-style skills.
- Read `references/gstack-porting.md` when the user wants Claude Code / gstack / OpenClaw installation shape.
- Read `references/output-contract.md` before writing files or packaging.
- Read `references/validation-checklist.md` before final delivery.

## Default workflow

1. Classify the request: initialize a dashboard, refresh an existing dashboard, convert a handoff note, or package a context artifact.
2. Inspect the repository safely. Prefer existing state files before broad source reading.
3. Build a source pack: sources found, facts, inferred state, stale/missing areas, confidence, conflicts, and resume-critical details.
4. Generate or update `context/index.html`, `context/assets/site.css`, `context/assets/site.js`, `context/context-state.json`, and optional root `context.html` redirect.
5. Run the generator when appropriate:
   ```bash
   python scripts/generate_context_dashboard.py --repo /path/to/repo --out /path/to/repo/context
   ```
6. Run validation before delivery:
   ```bash
   python scripts/validate_context_dashboard.py /path/to/repo/context
   ```
7. If the user requested a deliverable, package the generated context directory as a ZIP.
8. Report the generated files, sources used, missing sources, validation result, and any missing or inferred state.

## Required dashboard sections

The generated page must include these sections unless the source material clearly cannot support them. Empty sections must say what is missing.

1. Resume brief: objective, status, branch, last updated, confidence.
2. Agent start-here: copyable next prompt, immediate commands, and stop conditions.
3. Next actions: ordered by unlock value and risk.
4. Blockers and open questions: include owner or unknown owner.
5. Changed and important files: why each matters.
6. Repo map: compact tree, ignored heavy directories omitted.
7. Handoff ledger: latest runs, decisions, tests, review artifacts, and notes.
8. Validation and commands: tests run, tests not run, setup commands.
9. Risks: stale context, unverified assumptions, failing checks, unsafe changes.
10. Decision gates: explicit stop/ask conditions for ambiguity and unsafe continuation.
11. Context health: freshness, source coverage, confidence, and conflict summary.
12. Completion status: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` with evidence.
13. Source audit: files read, freshness signals, inferred areas, missing expected files.

## Script behavior

Use `scripts/generate_context_dashboard.py` for deterministic scaffolding or refreshes. The script is intentionally conservative: it scans known context files, git metadata, recent commits, selected config files, repo-local handoff files, optional gstack project artifacts, and a bounded repo tree; it does not parse the entire repository or call the network.

Use `scripts/validate_context_dashboard.py` to enforce required static files, required sections, no external assets, valid JSON state, one `h1`, local links, a minimum source audit, context-health section, decision-gate section, and completion-status section.

## Completion gates

Do not call the dashboard complete until:

- The dashboard opens as static HTML without a build step.
- The top of the page answers: what is happening, what changed, what is blocked, and what to do next.
- Every major claim is tied to a source file, git signal, or marked as inferred.
- The source audit lists missing expected files instead of silently omitting them.
- The dashboard includes a decision-gate section so an agent knows when not to continue.
- The dashboard includes completion status using the gstack-style status vocabulary.
- Validation passes or failures are reported with exact paths and fixes attempted.

## Delivery note

Final response must include:

- Link to the generated or updated ZIP if an artifact was requested.
- Files created or modified.
- Sources used and missing sources.
- Validation command and result.
- Completion status: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT`.
- Any limitations, especially missing handoff files, unavailable git metadata, lack of browser geometry testing, or partial gstack compatibility.
