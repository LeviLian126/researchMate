# GStack / Claude Code porting notes

The top-level skill is ChatGPT-native. To install the same behavior in a gstack or Claude Code skill system, create a host-specific skill file from this template and keep the scripts/references directories unchanged.

## Suggested gstack frontmatter

```yaml
---
name: agent-context-html
preamble-tier: 3
version: 0.2.0
description: |
  Agent Context HTML — generate a dense static HTML dashboard from repo structure,
  handoff notes, AGENTS.md, CLAUDE.md, TASK_STATE.md, .agent files, memory-bank,
  gstack artifacts, git status, recent commits, tests, blockers, and next steps.
  Use when asked to save context, restore context, generate a handoff, summarize repo
  state, produce an HTML dashboard for humans/agents, or help Codex/Claude/Cursor/
  Copilot resume work safely.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Write
  - Edit
  - WebSearch
triggers:
  - context dashboard
  - agent handoff
  - resume context
  - save context
  - generate handoff html
  - repo status dashboard
gbrain:
  schema: 1
  context_queries:
    - id: current-ledger
      kind: filesystem
      glob: "{repo_root}/{TASK_STATE.md,.agent/context.json,.agent/handoff.md,.agent/decisions.md}"
      render_as: "## Current repo context ledger"
    - id: recent-agent-runs
      kind: filesystem
      glob: "{repo_root}/.agent/runs/*.md"
      sort: mtime_desc
      limit: 5
      render_as: "## Recent agent runs"
    - id: recent-design-docs
      kind: filesystem
      glob: "~/.gstack/projects/{repo_slug}/*-design-*.md"
      sort: mtime_desc
      limit: 3
      render_as: "## Recent design docs"
    - id: recent-ceo-plans
      kind: filesystem
      glob: "~/.gstack/projects/{repo_slug}/ceo-plans/*.md"
      sort: mtime_desc
      limit: 3
      render_as: "## Recent CEO plans"
    - id: latest-handoff
      kind: filesystem
      glob: "~/.gstack/projects/{repo_slug}/*-handoff-*.md"
      sort: mtime_desc
      limit: 3
      render_as: "## Recent handoff notes"
---
```

## Minimal gstack workflow body

```markdown
# Agent Context HTML

## Preamble

1. Detect repo root, branch, dirty state, and recent git activity.
2. Read AGENTS.md, CLAUDE.md, TASK_STATE.md, .agent/context.json, .agent/runs, memory-bank, and newest gstack artifacts if present.
3. If a handoff note exists, use it as source material. Do not delete it unless the user explicitly asks.
4. If no source state exists, reconstruct from git and mark all conclusions as inferred.

## Workflow

Run:

```bash
python ~/.claude/skills/gstack/agent-context-html/scripts/generate_context_dashboard.py --repo . --out ./context
python ~/.claude/skills/gstack/agent-context-html/scripts/validate_context_dashboard.py ./context
```

Then report:

- STATUS: DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT
- REASON: one line
- ATTEMPTED: generation and validation commands
- RECOMMENDATION: next action for the user or next agent
```

## Optional Claude Code hooks

SessionStart can print `context/context-state.json` or a short summary from `context/index.html` as startup context. Claude Code hook docs allow `SessionStart` hooks to add context at startup/resume/compact.

Stop hooks can check whether `TASK_STATE.md`, `.agent/context.json`, or `context/context-state.json` changed before allowing an agent to finish. Use this only with explicit team agreement because hooks can change agent flow.

## Privacy and safety

- Do not enable telemetry by default.
- Do not sync gbrain or write to `~/.gstack` unless the user has opted in.
- Do not commit, push, delete handoff notes, or mutate project files outside `context/` unless explicitly requested.
