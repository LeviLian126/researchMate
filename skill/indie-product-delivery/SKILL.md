---
name: indie-product-delivery
description: "Use for outcome-first, evidence-backed delivery of bootstrapped software products when work spans product scope, system design, backend or frontend implementation, quality, release, or substantive Markdown or HTML project documentation. Apply when ownership or boundaries are unclear, when several product-delivery concerns interact, or when a maintained README, PRD, design document, release note, or HTML project board must remain aligned with repository truth. Do not auto-trigger for isolated specified local edits, mechanical documentation fixes, small UI copy changes, general questions, or work fully covered by a specialized skill."
---

# Indie Product Delivery

## Context

Inspect the smallest set of current facts that can change the result:

- the repository, product surface, environment, and relevant existing behavior;
- confirmed requirements, non-goals, acceptance, and unresolved decisions;
- current source, configuration, tests, maintained documentation, and applicable repository instructions;
- available tools, credentials, runtime, accounts, data, and evidence.

Do not ask the user to restate facts that can be discovered safely. Prefer current user instructions, repository instructions, source and configuration, tests, and maintained local documentation. For version-sensitive provider or framework behavior, use the installed version and its official documentation. Surface conflicts instead of silently choosing the convenient source.

Load only the current owner's README and the workflow guide needed for the present task. Read another node only when a real product, contract, implementation, quality, release, operations, or documentation boundary requires it.

## Boundaries

Preserve the user's stated constraints and distinguish local work from external effects.

- Confirm an unresolved product direction, public contract, or low-reversibility architecture choice before landing it when the request has not decided the outcome and impact.
- Require exact authorization before deployment, production migration, real charges or messages, customer or shared-data writes, destructive operations, credential rotation, history rewrite, DNS or traffic changes, rollback, or another external effect.
- Dynamic security testing requires an owned target, allowed methods, account and data scope, and meaningful exclusions. Static review and local analysis do not require that additional authority.

Use the relevant workflow for authentication, authorization, tenancy, private data, money, secrets, destructive data evolution, public compatibility, and low-reversibility choices. When production behavior may be harming users, data, money, privacy, security, or availability, contain the harm and gather direct evidence before pursuing growth or polish.

Respect the repository's execution-environment policy. When the repository or user reserves integration testing for deployed/server environments, limit local evidence to the smallest hermetic unit, domain, contract, schema, import, static, and build checks. Do not start local applications, databases, brokers, vector stores, object stores, provider simulators, or containers to approximate integration. Route modular and cross-service proof to the authorized deployed/server environment with protected configuration and safe test data.

You may investigate, implement, test, or improve quality beyond the listed steps when that work helps complete the request. Do not silently expand product meaning, external effects, or collaboration-system scope.

## Output

Produce a result the user can use, supported by the narrowest meaningful evidence.

- Without a required runtime, account, data set, browser, or environment, make only the claims the available evidence supports.
- Without deploy access and exact authorization, do not describe release preparation as an executed release.
- Label time-sensitive market or provider conclusions as assumptions when current research is unavailable.

Do not repeat a failed command, repair, or route without new evidence and a falsifiable reason. When no authorized evidence-producing action remains, stop and state the concrete missing decision, authority, environment, or evidence.

Return the result naturally. Make clear what was delivered or decided, what evidence supports it, what external effects were performed, and what concern or blocker remains. Do not expose internal routing notes unless they help the user understand a decision.

## Choose the current owner

Choose the owner of the present decision or action. Node numbers identify domains, not a mandatory lifecycle.

| Present need | Read |
|---|---|
| target user, problem, promise, pricing, positioning, MVP/MAP, validation, acceptance | `references/nodes/01-market-mvp-scope/README.md` |
| system boundary, API/data/permission/provider contract, architecture, compatibility, migration or build plan | `references/nodes/02-architecture-contracts-plan/README.md` |
| backend, API, data, auth, job, provider, async, reconciliation or observability implementation | `references/nodes/03-backend-api-data-build/README.md` |
| frontend flow, content, visual direction, components, responsive/accessibility behavior or browser proof | `references/nodes/04-frontend-ux-ui-build/README.md` |
| review, test strategy, runtime QA, reliability, security/privacy, evidence or ship judgment | `references/nodes/05-qa-review-security-hardening/README.md` |
| CI/CD, release preparation, deploy, rollout, migration execution, recovery or production verification | `references/nodes/06-ci-cd-launch/README.md` |
| production health, customer evidence, experiments, learning or the next operating decision | `references/nodes/07-ops-growth-iteration/README.md` |


For any Markdown or HTML document created or materially edited, read `references/human-readable-document-writing.md`. A spelling fix, link repair, or request to preserve the original wording does not authorize a broader rewrite.

For a maintained README, PRD, design document, release note, change note, HTML project board, or similar project source of truth, also read `references/durable-document-quality.md`. When the deliverable is an HTML project board, or an established board owns facts changed by the work, additionally read `references/agent-context-html/instructions.md`.

## Apply the minimum delivery standard

The applicable requirements in the selected workflow are the minimum delivery standard, not optional suggestions and not a required final-response format.

- Complete every requirement that applies to the current task, facts, and authorization limits.
- Skip checks that are genuinely inapplicable; do not perform them merely to complete a ritual.
- Do not use a task's small size to skip applicable security, permission, state, error, accessibility, compatibility, recovery, or verification requirements.
- Go beyond the workflow when additional work materially improves the requested result and remains authorized.
- Do not recite the workflow checklist to the user; satisfy it and report the result and evidence.

## Maintain useful source commentary

Follow the repository's established documentation style for every authored source or configuration file touched or created:

- Start the file with a concise comment that states its primary responsibility or boundary.
- Add a concise docstring or documentation comment before every major class and function, including frontend components and handlers, explaining its purpose rather than narrating its implementation.
- Keep comments and documentation accurate for public contracts, invariants, and non-obvious constraints, and update stale commentary when behavior changes.
- Do not inject comments into strict JSON, lockfiles, generated files, or vendor artifacts. Use schema-supported descriptive metadata when available instead.
