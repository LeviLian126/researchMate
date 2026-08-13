---
name: indie-product-delivery
description: "Use for outcome-first, evidence-backed delivery and review of bootstrapped software products. Apply for product decisions, architecture, backend or frontend implementation, quality, release, maintenance, or code/document review. Update the project's HTML project board under docs/ when a task leaves its product, architecture, implementation, evidence, or release facts stale."
---

# Indie Product Delivery

## Context

Before inspecting facts, read `../human/SKILL.md` and follow its output style and delivery discipline rules. These rules apply to all responses in this session.

Inspect the smallest set of current facts that can change the result:

- the repository, product surface, environment, and relevant existing behavior;
- confirmed requirements, non-goals, acceptance, and unresolved decisions;
- current source, configuration, tests, maintained documentation, and applicable repository instructions;
- available tools, credentials, runtime, accounts, data, and evidence.

Do not ask the user to restate facts that can be discovered safely. Prefer current user instructions, repository instructions, source and configuration, tests, and maintained local documentation. For version-sensitive provider or framework behavior, use the installed version and its official documentation. Surface conflicts instead of silently choosing the convenient source.

Identify the node that owns the present request, read that node's README, then read only the workflow files that README routes to. This keeps the working context small enough for the agent to reason about the actual request instead of performing a ritual survey of the whole delivery system. Stay inside that node unless the node's output explicitly routes the work elsewhere.

## Boundaries

Preserve the user's stated constraints and distinguish local work from external effects.

- Operate with the repository access and external-action authority available to the agent by default. Ask before proceeding when the user explicitly requests a plan, a grilling/review, or approval-first work. Otherwise complete the goal autonomously, including commit, push, and real server or production verification when the environment supports it, and report the defaults chosen at the end.
- Do not expose or guess secrets, API keys, tokens, or undisclosed credentials. If repeated evidence-based attempts cannot reach the requested outcome, do not bypass the constraint with jailbreaks, cheats, or fabricated evidence: state the blocker and offer the closest safe alternative.

Use the relevant workflow for the product boundary involved. When production behavior may be harming users, data, money, privacy, security, or availability, contain the harm and gather direct evidence before pursuing growth or polish.

Test runnable work locally and in the applicable server environment. When testing locally,
install required dependencies but do not start local services for middleware like databases
or message queues; instead, use mocks in test classes to verify behavior. For frontend
improvements, render the changes in a browser to confirm visual and interactive correctness.

For a small change, verify only the changed behavior and its affected server path; for a
large refactor, `HIGH_RISK` change, or release, verify the relevant core flows and release
evidence. Label the evidence by environment and do not treat local success as server
success. If a target environment is genuinely unavailable after reasonable setup attempts,
record the exact proof gap and continue with every safe alternative.

Use an independent subagent or fresh session for large refactors, `HIGH_RISK` changes, and
pre-release verification by default. Use the same subagent across both phases to preserve
context and save tokens. In Phase 1, give it the goal, interface signatures, schema,
acceptance criteria, and risk classification, and forbid it from reading the implementation
source so it must design contract-first tests from the public contract alone. In Phase 2,
lift the source restriction: give it the implementation diff, Phase 1 tests, and runtime
evidence so it can review the source and confirm coverage gaps. For small local changes,
do not open an independent session by default; complete the applicable local checks and
affected server checks instead.

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


Before every commit or push, compare the latest source and configuration against the HTML
project board under `docs/`. Enter Node08 and update the board only when this task leaves its
important product, architecture, implementation, evidence, release, risk, or next-action facts
stale; otherwise do not modify it. When the board is updated, run the `human` skill after
its technical facts and structure are stable. Keep meaningful product and data facts; omit
trivial implementation trivia such as button dimensions unless it is part of a real design
contract.

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
Regardless of size, inspect the final diff, commit the change, and push it before finishing;
the push is part of completion, not an optional release step.
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

## Edit in place and reuse existing code

Prefer reusing existing functions, abstractions, and patterns over introducing new ones. Before
writing new code, search the repository for an existing function or module that already solves
the problem or can be extended with a small, cohesive change. Reuse keeps the codebase
understandable and avoids the drift that comes from parallel implementations of the same policy.

When modifying an existing file—whether documentation or source—do not append new content at
the end merely because it is convenient. Treat the file as a logical article: interleave new
content into the section where it belongs, and renumber or restructure subsequent sections so
the whole file stays coherent. For example, when adding a new concern that logically belongs
between section 2 and section 3, insert it as the new section 3 and shift every later section
back by one. The goal is to preserve the file's narrative flow and maintainability, not to
minimize the size of the diff.

## Choose branches and worktrees deliberately

Use `main` for ordinary specified work by default. Confirm the requested outcome and
material requirements before changing files; do not create a branch for ordinary work or
because branching is available.

Create an exploratory branch only when the task is genuinely exploratory or the user
explicitly asks for one. Define the success condition before implementation, push the branch
for review, and merge it into `main` only after the evidence shows that the improvement
meets the user's expected outcome. Keep exploratory code and findings on that pushed branch
when it does not meet the condition; do not force it into `main`.

Within a thread, open one worktree before modifying files. All subsequent subagents and the
main agent work in that same worktree — subagents must not open their own. After all
implementation and verification are complete inside the worktree, merge back to `main`,
confirm no conflicts, then commit and push. Remove the worktree after successful merge.

## Maintain useful source commentary

Follow the repository's established documentation style for every authored source or configuration file touched or created. The purpose of the opening comment and focused business tests is to make ownership and important behavior discoverable to the next agent, not to decorate files or test implementation trivia:

- Start every newly authored or modified source-code/configuration file with a concise English comment stating its primary responsibility or boundary, when the format supports comments. Do not add comments to Markdown, strict JSON, lockfiles, generated files, or vendor artifacts.
- For core business logic, cover the main functions with meaningful tests. Add docstrings or documentation comments where they explain a public contract, invariant, non-obvious constraint, or ownership boundary; do not comment every trivial function or component.
- Keep comments and documentation accurate for public contracts, invariants, and non-obvious constraints, and update stale commentary when behavior changes.
