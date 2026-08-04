# v2 synthesis map

This is a backlog for the next phase, not finished skill policy.

| Topic | Strong source | Useful supplement | Conflict or decision to resolve |
|---|---|---|---|
| Product pressure test | indie node 01 | gstack office-hours / CEO review / spec | Avoid performative founder theater; require falsifiable evidence and an explicit toy-vs-product classification. |
| Architecture | indie node 02 | gstack engineering review; HTML module/plan examples | Preserve contracts and reversible evolution; do not make a diagram the architecture. |
| Backend | indie node 03 | gstack investigate/review | Keep router→service→adapter/repository→SQL identity flow and managed-boundary proof. |
| Frontend | indie node 04 | frontend-design; gstack design skills | Balance distinctiveness with existing brand, accessibility, latency, and task fit. |
| QA | indie node 05 | gstack QA, review, CSO, benchmark | Map browser/tool assumptions to the active environment; keep read-only reviewer exceptional. |
| Release | indie nodes 06–07 | gstack ship/deploy/canary/docs | Repository/user authority wins over upstream branch, PR, or auto-deploy defaults. |
| HTML docs | indie HTML references | HTML Effectiveness Apache-2.0 corpus | Use HTML when spatial/interactive form improves a decision, not as decoration. |
| Human prose | humanizer; Gemini docs guidance | indie writing guidance; OpenAI prompting notes | Preserve facts and voice; adapt English anti-patterns carefully for Chinese. |
| Skill construction | local skill-creator | OpenAI prompting notes | Keep metadata precise, body lean, references progressive, and evals for a later phase. |

## Cross-node contracts still missing

1. Discovery → architecture: accepted problem, audience, non-goals, success evidence, risk budget.
2. Architecture → implementation: interfaces, ownership, permission rules, migration order, failure behavior.
3. Implementation → QA: raw diff, changed contracts, fixtures, expected states, known gaps.
4. QA → release: risk-ordered findings, accepted residual risk, exact required gates.
5. Release → durable docs: deployed SHA, migration state, smoke evidence, rollback handle, open boundaries.

## Deliberately deferred

- Final trigger descriptions and naming.
- Node output templates and acceptance schemas.
- Deduplication of repeated evidence/status taxonomies.
- Test prompts, assertions, benchmarks, and description optimization.
- Packaging or installation as a production Codex skill.
