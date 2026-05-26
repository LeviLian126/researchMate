# Dashboard specification

## Visual posture

Use an operations-room or field-manual aesthetic: dense, readable, restrained. This is a resumption surface. Avoid generic SaaS hero blocks, vague slogans, oversized decorative cards, stock illustrations, remote icons, and marketing CTAs.

## Top-of-page contract

The first viewport must answer:

- What repo/branch is this?
- What is the current objective?
- What is the status?
- What should the next agent do first?
- What is blocked or risky?
- Which sources were used?

## Required sections

### Resume brief

Include status chips for branch, dirty/clean tree, confidence, last generated time, and source coverage.

### Agent start-here

Include a copyable prompt such as:

```text
Read context/index.html and context/context-state.json first. Continue from the next action list. Before editing, verify blockers and run the listed validation commands. At the end, update the handoff/state files and regenerate this dashboard.
```

### Next actions

Use a table with columns: priority, action, why, source, risk, done signal.

### Blockers and open questions

Do not hide missing information. Use severity levels: blocking, risky, unknown, informational.

### Changed and important files

Show changed files first, then source-of-truth files, then likely implementation hotspots. Include reason and source.

### Repo map

Show a compact depth-limited tree. Omit heavy/generated directories: `.git`, `node_modules`, `vendor`, `dist`, `build`, `.next`, `.venv`, `coverage`, `target`, `__pycache__`.

### Handoff ledger

Summarize latest `.agent/runs/*.md`, handoff files, decisions, tests, and review notes. Include dates if available.

### Validation and commands

Show tests run, tests not run, setup commands, lint/typecheck/build commands inferred from package files or instructions. Do not claim a command passed unless a source says it passed or the current agent actually ran it.

### Risk register

Include stale state, uncommitted changes, missing tests, ambiguous package manager, missing handoff, generated files, and any user-provided constraints not yet satisfied.

### Decision gates

List conditions under which the next agent must stop and ask rather than continue. Include stale branch, missing objective, contradictory task state, uncommitted changes that are not understood, failing tests, destructive migrations, or unclear ownership.

### Context health

Show confidence, freshness, source coverage, missing source count, and conflicts. This is the equivalent of a context recovery health check.

### Completion status

Use the status vocabulary: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT`. Include reason, attempted commands, and recommendation.

### Source audit

List every source read, every expected source missing, and the basis for confidence. This section is for agents as much as humans.

## Interaction rules

- Use vanilla JavaScript only.
- Allowed interactions: filter sections, copy resume prompt, toggle compact mode, theme mode, expand/collapse source details.
- Never require JavaScript to read the core state.
- Keep all links relative and local.
