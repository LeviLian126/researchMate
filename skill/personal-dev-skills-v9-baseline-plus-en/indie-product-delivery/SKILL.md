---
name: indie-product-delivery
description: "Use for outcome-first, evidence-backed delivery and review of bootstrapped software products. Apply for product decisions, architecture, backend or frontend implementation, quality, release, maintenance, or code/document review. By default, create or update the project's HTML project board under docs/ so current product, architecture, implementation, evidence, and release truth remains inspectable."
---

# Indie Product Delivery

## Context

Inspect the smallest set of current facts that can change the result:

- the repository, product surface, environment, and relevant existing behavior;
- confirmed requirements, non-goals, acceptance, and unresolved decisions;
- current source, configuration, tests, maintained documentation, and applicable repository instructions;
- available tools, credentials, runtime, accounts, data, and evidence.

Do not ask the user to restate facts that can be discovered safely. Prefer current user instructions, repository instructions, source and configuration, tests, and maintained local documentation. For version-sensitive provider or framework behavior, use the installed version and its official documentation. Surface conflicts instead of silently choosing the convenient source.

Identify the node that owns the present request, read that node's README, then read only the workflow files that README routes to. This keeps the working context small enough for the agent to reason about the actual request instead of performing a ritual survey of the whole delivery system. Stay inside that node unless the node's output explicitly routes the work elsewhere.

## Boundaries

Preserve the user's stated constraints and distinguish local work from external effects.

- Confirm an unresolved product direction, public contract, or low-reversibility architecture choice before landing it when the request has not decided the outcome and impact.
- Operate with the repository access and external-action authority available to the agent by default. Stop only when the next action would expose or require a secret, API key, token, or undisclosed credential. Keep secrets out of files, logs, commits, and reports; never guess them. Application-level authentication, authorization, payment, and security remain product behavior to preserve and test, not permission limits on the agent.

Use the relevant workflow for the product boundary involved. When production behavior may be harming users, data, money, privacy, security, or availability, contain the harm and gather direct evidence before pursuing growth or polish.

When a dependency or environment is missing, use this simple decision:

1. On the first occurrence, tell the user what is missing and report the file/package size
   or estimated download size. Install it after the user agrees.
2. If the user declines, do not install it locally. Run the available local checks and move
   the remaining proof to the cloud/deployed environment.

You may investigate, implement, test, or improve quality beyond the listed steps when that work helps complete the request. Do not silently expand product meaning or collaboration-system scope.

## Output

Produce a result the user can use, supported by the narrowest meaningful evidence.

- Without a required runtime, account, data set, browser, or environment, make only the claims the available evidence supports.
- Do not describe an action as executed unless the command or external observation actually proves it.
- Label time-sensitive market or provider conclusions as assumptions when current research is unavailable.

When a path fails, try another path or collect new evidence. Do not repeat the same attempt without learning something new. The goal is progress through changed hypotheses, routes, or evidence—not persistence in a dead loop.

Return the result naturally. Make clear what was delivered or decided, what evidence supports it, what external effects were performed, and what concern or blocker remains. Do not expose internal routing notes unless they help the user understand a decision.

## Choose the current node

Choose the node that owns the present decision or action. Node numbers identify domains, not a mandatory lifecycle. Obey that node's README and output contract; do not import another node's checklist unless the current node routes there.

| Present need | Read |
|---|---|
| target user, problem, promise, pricing, positioning, MVP/MAP, validation, acceptance | `references/nodes/01-market-mvp-scope/README.md` |
| system boundary, API/data/permission/provider contract, architecture, compatibility, migration or build plan | `references/nodes/02-architecture-contracts-plan/README.md` |
| backend, API, data, auth, job, provider, async, reconciliation or observability implementation | `references/nodes/03-backend-api-data-build/README.md` |
| frontend flow, content, visual direction, components, responsive/accessibility behavior or browser proof | `references/nodes/04-frontend-ux-ui-build/README.md` |
| review, test strategy, runtime QA, reliability, security/privacy, evidence or ship judgment | `references/nodes/05-qa-review-security-hardening/README.md` |
| CI/CD, release preparation, deploy, rollout, migration execution, recovery or production verification | `references/nodes/06-ci-cd-launch/README.md` |
| production health, customer evidence, experiments, learning or the next operating decision | `references/nodes/07-ops-growth-iteration/README.md` |
| spatial comparison, module or architecture map, interactive prototype, project status board, or maintained HTML evidence surface | `references/nodes/08-agent-context-html/README.md` |


Create or update the complete HTML project board under `docs/` for every product task or
review, whether the work is implementation, maintenance, or inspection. The board is a
direct, evidence-backed starting point for a new human or agent: it should make the product,
architecture, current implementation, core database tables and business fields, contracts,
status, risks, and next action understandable without reconstructing the project from chat.
Use Node08 for the board's content, evidence, visual, accessibility, and validation workflow.
Run the `humanizer` skill by default after technical facts, evidence, and artifact structure
are stable; apply it to Markdown/HTML and other user-facing prose, including the conversation,
while preserving technical meaning, caveats, and repository terminology. Before every commit
or push, inspect the latest source and configuration against the board and update the board
whenever its important facts are stale. Keep meaningful product and data facts; omit trivial
implementation trivia such as button dimensions unless it is part of a real design contract.

## Apply the minimum delivery standard

The applicable requirements in the selected workflow are the minimum delivery standard because they protect the node's intended result; they are not a ritual checklist or a required final-response format.

- Complete every requirement that applies to the current task and facts.
- Skip checks that are genuinely inapplicable; do not perform them merely to complete a ritual.
- Do not use a task's small size to skip applicable security, permission, state, error, accessibility, compatibility, recovery, or verification requirements.
- Cover core business code with meaningful unit tests. The goal is confidence in decisions that can corrupt state, grant access, charge money, or change the user's outcome—not a coverage number. Prioritize business rules, authorization decisions, state transitions, failure handling, idempotency, money/quota logic, and changed branches. Do not add tests for trivial glue, generated code, styling, or simple pass-throughs merely to increase a percentage; use contract, integration, browser, or runtime proof when a unit test would misrepresent the boundary. Follow any higher repository threshold when one exists.
- Go beyond the workflow when additional work materially improves the requested result and remains within the product goal.
- Do not recite the workflow checklist to the user; satisfy it and report the result and evidence.

For a complex change that spans multiple product modules and is release-bearing, use this
order unless a concrete dependency requires otherwise: design, source implementation,
maintained HTML/OpenAPI when applicable, local hermetic checks, cloud CI and module
verification, commit and push to the repository's intended branch, migration, deployment,
production smoke, and rollback judgment. This order makes a broad change traceable from
intent to live evidence and leaves a clear recovery decision if reality diverges. For a
small local change, use only the steps that can affect correctness before source control.
Regardless of size, inspect the final diff, commit the change, and push it before finishing.
Push ordinary work to `main`; push exploratory work to its exploratory branch and merge it
into `main` only under the branch rule below. If the push needs a missing credential or API
key, report that concrete blocker instead of fabricating access.
Choose a deployment platform from repository configuration, runtime requirements, and
existing ownership. The project-board HTML under `docs/` records the chosen platform and
the evidence behind it.

## Keep modules cohesive and review size as a signal

Keep modules cohesive so that each file has a clear reason to change and so that business
rules do not become a long, tangled flow. Use size only as a prompt to inspect cohesion,
not as a mechanical split threshold.

| Artifact | Review signal | Required response |
|---|---|---|
| substantive Markdown reference | becoming hard to scan or answering several unrelated reader questions | keep one coherent reader question; split only at a real conceptual boundary |
| authored product code | growing hard to reason about or changing for unrelated reasons | inspect ownership, state flow, and dependency direction before splitting |
| authored non-generated product code | accumulating branching, duplicated policy, or cross-layer knowledge | extract a cohesive boundary only when it reduces coupling rather than creating fragments |

Do not create tiny files merely to satisfy a count, and do not combine unrelated behavior to avoid one. Prefer high-cohesion modules, narrow contracts, explicit ownership, composition, and provider adapters. Treat generic `utils`, `common`, or `helpers` growth, repeated cross-layer conditionals, and large if/else dispatch trees as evidence that policy or ownership may be misplaced. The desired result is a smaller number of understandable boundaries, not maximal file granularity.

## Write code for understanding and change

The code-quality goal is to leave the next change obvious and local. Apply these principles
as judgment guides, not as a reason to introduce ceremony or abstractions:

- Keep each module, class, and function responsible for one coherent outcome. Separate
  business rules from infrastructure and presentation so a rule has one clear owner.
- Prefer readable names, small focused functions, simple control flow, and explicit
  dependencies over cleverness, deep nesting, global state, hidden side effects, or
  premature patterns. Comments explain why, constraints, or invariants—not what the code
  already says.
- Remove duplicated policy when that improves consistency, but do not create abstractions
  before a real seam or repeated behavior exists. Keep interfaces stable and mechanisms
  replaceable where the boundary actually matters.
- Handle errors explicitly: preserve useful context, fail fast on invalid states, and never
  silently discard exceptions or unexpected provider results.
- Make core business logic easy to test through clear inputs and outputs. Test the changed
  business rules, failure paths, state transitions, and compatibility behavior; use a
  fitting boundary test when unit isolation would lie about the real system.

Before handoff, ask: does each component have one clear responsibility, is dependency
direction understandable, can the core behavior be tested without brittle coupling, and
would the next feature require a local extension rather than a rewrite of unrelated code?

## Choose branches and worktrees deliberately

Use `main` for ordinary specified work by default. Confirm the requested outcome and
material requirements before changing files; do not create a branch for ordinary work or
because branching is available.

Create an exploratory branch only when the task is genuinely exploratory or the user
explicitly asks for one. Define the success condition before implementation, push the branch
for review, and merge it into `main` only after the evidence shows that the improvement
meets the user's expected outcome. Otherwise preserve useful findings and abandon the
implementation without forcing it into `main`.

For exceptional parallel implementation explicitly requested by the user, give each writing
agent a non-overlapping responsibility and its own branch or worktree, and assign one
integration owner. Serialize work that changes shared contracts, schemas, core types, or
the same files.

## Maintain useful source commentary

Follow the repository's established documentation style for every authored source or configuration file touched or created. The purpose of the opening comment and focused business tests is to make ownership and important behavior discoverable to the next agent, not to decorate files or test implementation trivia:

- Start every newly authored or modified source-code/configuration file with a concise English comment stating its primary responsibility or boundary, when the format supports comments. Do not add comments to Markdown, strict JSON, lockfiles, generated files, or vendor artifacts.
- For core business logic, cover the main functions with meaningful tests. Add docstrings or documentation comments where they explain a public contract, invariant, non-obvious constraint, or ownership boundary; do not comment every trivial function or component.
- Keep comments and documentation accurate for public contracts, invariants, and non-obvious constraints, and update stale commentary when behavior changes.
