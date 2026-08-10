# HTML Agent Context and Project Board

Use this node for the project's default HTML project board under `docs/`, whether the task
is implementation, maintenance, review, or documentation. The board is the durable visual
context for current product, architecture, code, evidence, and release truth. Ordinary
Markdown may still be edited elsewhere, but the board remains the default project record.

| Need | Read |
|---|---|
| decide whether HTML is the right medium and follow the board workflow | `html-medium-and-workflow.md` |
| define pages, evidence classes, project topology, ledgers, status, and history | `project-board-content-and-evidence.md` |
| build the visual system, diagrams, interaction, responsive behavior, and accessibility | `visual-interaction-and-accessibility.md` |
| validate content truth, links, HTML, browser behavior, and handoff | `validation-and-handoff.md` |

Start from `assets/document-system.css` only when its document-oriented system fits the repository. Existing project styles and explicit user references take precedence.

## Output contract

Return the board path under the project's conventional `docs/` location, pages or regions
updated, source facts and evidence checked, status/decision changes, deterministic and
browser validations actually run, remaining unknowns or conflicts, and the next action.
Keep the board as a current evidence surface; keep historical detail in its linked activity
record when applicable.
