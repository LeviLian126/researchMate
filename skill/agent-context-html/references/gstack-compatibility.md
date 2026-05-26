# GStack compatibility audit

This skill is not a verbatim copy of the uploaded `office-hours` or `plan-ceo-review` skills. It is a ChatGPT-native skill that intentionally maps their operating conventions into a dashboard-generation workflow.

## Compatibility scorecard

| GStack pattern | Requirement observed in uploaded skills | How this skill implements it |
|---|---|---|
| Preamble before work | Gather branch, repo mode, telemetry flags, routing state, checkpoint state, and recent artifacts | `workflow.md` and the generator preflight gather repo root, branch, status, recent commits, context files, and optional gstack artifacts |
| Context recovery | At session start or after compaction, recover recent artifacts and summarize useful state | Dashboard first sections are `resume`, `start-here`, `next-actions`, and `context-health`; generator scans `.agent`, `memory-bank`, AGENTS/CLAUDE files, git signals, and optional gstack project dirs |
| Source queries / gbrain | Skills declare `gbrain.context_queries` for prior sessions, design docs, builder profile, reviews, and timelines | `source-priority.md` and generator source candidates encode deterministic local equivalents; `gstack-porting.md` includes gbrain query examples for a gstack installation |
| AskUserQuestion / decision authority | High-stakes ambiguity stops and asks; no silent defaults | This skill requires a decision gate when ambiguity changes scope, safety, or next action; dashboard includes a visible `decision-gates` section |
| Voice | Concrete builder-to-builder style, direct status, no filler | The dashboard spec requires operations-room/field-manual tone and forbids marketing posture |
| Completion Status Protocol | Report `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` with evidence | Dashboard includes `completion-status`; final delivery must use the same vocabulary |
| Context Health | Progress summaries, reassess loops, context-save/restore bias | Dashboard includes `context-health`; long skill sessions should emit progress notes |
| Continuous checkpoint | WIP commit metadata can include `[gstack-context]` | The generator reads recent git state and can surface `[gstack-context]` in commit bodies if available, but does not auto-commit |
| Telemetry | Local/opt-in analytics written at skill end | Not copied by default. This skill avoids telemetry unless the host skill system provides explicit opt-in. See `gstack-porting.md` for optional local-only logging hooks |
| Review/handoff cleanup | CEO review cleans obsolete handoff notes after completion | This skill does not delete handoff files. It treats handoff history as source material. Cleanup must be explicit user instruction |

## Non-goals

- Do not copy the long gstack preamble verbatim into the ChatGPT-native top-level `SKILL.md`; it would add host-specific commands and fields that native skill packaging does not require.
- Do not write telemetry, update `~/.gstack`, commit, or delete handoff notes unless the user explicitly asks or a gstack host skill wrapper handles it.
- Do not turn the dashboard into a review skill. It can summarize review artifacts, but it does not replace `office-hours` or `plan-ceo-review`.

## Definition of "aligned"

Treat this skill as aligned only when all of the following are true:

1. It uses repo-local and handoff sources before broad inference.
2. It surfaces missing context as a first-class finding.
3. It keeps next actions and blockers above background information.
4. It includes explicit decision gates and completion status.
5. It validates output before delivery.
6. It provides a gstack porting template without breaking native skill packaging.
