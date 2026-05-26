# Source priority

## Source-of-truth order

When sources disagree, use this order and call out the conflict:

1. User's current request and explicit constraints.
2. Current working tree facts: git status, diff stat, file existence, generated artifacts.
3. Current agent state files: `TASK_STATE.md`, `.agent/context.json`, `.agent/handoff.md`, `.agent/runs/*.md`, `.agent/decisions.md`.
4. Tool-specific instructions: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`.
5. GStack project artifacts when explicitly available: `~/.gstack/projects/{repo_slug}/*-design-*.md`, `ceo-plans/*.md`, `checkpoints/*.md`, `timeline.jsonl`, `*-handoff-*.md`.
6. Memory bank files: `memory-bank/activeContext.md`, `progress.md`, `projectbrief.md`, `systemPatterns.md`, `techContext.md`.
7. Recent git activity: branch, recent commits, changed files, stashes.
8. Project docs and configs: README, package manifests, pyproject, Cargo, go.mod, Makefile, CI configs.
9. Inference from repo structure.

## Freshness rules

- Treat explicit handoff/state files as fresh only when they mention recent branch, changed files, current objective, or next steps.
- Treat git status and current files as fresh facts.
- Treat README and product docs as background unless recently edited or referenced by state files.
- Mark inferred conclusions with `inferred` in `context-state.json` and visible copy.
- Mark missing expected files in the source audit. Missing context is a first-class finding.

## Conflict handling

If two sources disagree:

- Show both values in the source audit.
- Prefer the higher-priority source.
- Add an open question if the conflict affects next action or safety.

Examples:

- `TASK_STATE.md` says tests passed, but git status shows new test files after that timestamp: mark tests as stale.
- `AGENTS.md` says use pnpm, but package-lock exists and no pnpm-lock exists: mark package manager as ambiguous.
- Handoff says branch `feature/a`, current branch is `feature/b`: mark handoff possibly copied or stale.
