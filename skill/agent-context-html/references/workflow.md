# Workflow

## 1. Determine mode

- Initialize: no existing `context/index.html` exists.
- Refresh: existing dashboard exists and repo state changed.
- Convert handoff: user provides a handoff note, `TASK_STATE.md`, or `.agent/context.json`.
- Package: user wants a ZIP for sharing.

## 2. Inspect sources

Read source files in priority order. Use bounded scans. Do not traverse heavy/generated directories.

Recommended shell checks when available:

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --short
git log --oneline -8
git diff --stat
```

Then inspect likely source files:

```text
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
TASK_STATE.md
.agent/context.json
.agent/handoff.md
.agent/decisions.md
.agent/runs/*.md
memory-bank/*.md
README.md
package.json
pyproject.toml
Cargo.toml
go.mod
Makefile
```

## 3. Build source pack

Produce internal notes with:

- Facts: directly observed.
- Inferences: repo patterns or missing-source reconstruction.
- Missing context: expected files not found.
- Conflicts: sources disagree.
- Resume-critical items: what the next agent needs first.

## 4. Generate HTML

Prefer `scripts/generate_context_dashboard.py` for speed and consistency. Customize the generated content only when it improves resumption accuracy.

## 5. Validate

Run `scripts/validate_context_dashboard.py`. Fix blocking failures. If the repo is not available or git commands fail, show the limitation in the final note and in the dashboard source audit.

## 6. Package

Package only the dashboard directory and any required local assets unless the user asks to package the whole repo. Use a clear name such as `agent-context-dashboard.zip` for generated dashboards. When packaging the skill itself, use `skill.zip`.
