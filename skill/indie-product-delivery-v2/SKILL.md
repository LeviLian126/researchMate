---
name: indie-product-delivery
description: "Use for outcome-first, evidence-backed delivery of bootstrapped software products when work spans product scope, system design, backend or frontend implementation, quality, release, or substantive Markdown or HTML project documentation. Apply when ownership or boundaries are unclear, when several product-delivery concerns interact, or when a maintained README, PRD, design document, release note, or HTML project board must remain aligned with repository truth. Use this skill whenever the user mentions building or shipping a product, scoping an MVP, designing a system or API, implementing a backend/frontend slice, reviewing or hardening a change, preparing a release, investigating production health, or producing durable project documentation — even when they don't name a full delivery cycle. Do not auto-trigger for isolated specified local edits, mechanical documentation fixes, small UI copy changes, general questions, or work fully covered by a specialized skill."
---

# Indie Product Delivery

## Context

Inspect the smallest set of current facts that can change the result: the repository, product surface, environment, and relevant existing behavior; confirmed requirements, non-goals, acceptance, and unresolved decisions; current source, config, tests, maintained docs, and repo instructions; available tools, credentials, runtime, accounts, and evidence.

Prefer current user instructions, repo instructions, source/config, tests, and maintained local docs over asking the user to restate facts you can discover safely. For version-sensitive provider or framework behavior, use the installed version and its official docs. Surface conflicts instead of silently choosing the convenient source.

Load only the workflow guide needed for the present task. Read another node only when a real product, contract, implementation, quality, release, operations, or documentation boundary requires it.

## Boundaries

Preserve the user's stated constraints and distinguish local work from external effects.

A few choices are expensive to undo — an unresolved product direction, a public contract, a low-reversibility architecture decision. Confirm these before landing them, because the cost of being wrong lands on the user, not on the task. Everything else is cheap to revise; bias toward action.

Require exact authorization before deployment, production migration, real charges or messages, customer or shared-data writes, destructive operations, credential rotation, history rewrite, DNS or traffic changes, or rollback. These act on the world outside the task; the model can't know the human means "go" without being told.

Dynamic security testing needs an owned target, allowed methods, and account/data scope. Static review and local analysis need no extra authority — they touch nothing external.

When production behavior may be harming users, data, money, privacy, security, or availability, contain the harm and gather direct evidence before pursuing growth or polish.

## Execution environment

Follow the repository's execution-environment policy. Where it's silent: default to local, hermetic unit, domain, contract, schema, import, static, and build checks — proof you can run without external services. Defer cross-module and integration proof to the authorized deployed/server environment, because standing up databases, brokers, providers, or containers locally usually doesn't reproduce the real boundary anyway and adds cost. Install a new environment or dependency only when the user explicitly allows it. Node03 expands the hermetic-vs-deployed split.

## Output

Produce a result the user can use, supported by the narrowest meaningful evidence.

- Without a required runtime, account, data set, browser, or environment, make only the claims the available evidence supports.
- Without deploy access and exact authorization, don't describe release preparation as an executed release.
- Label time-sensitive market or provider conclusions as assumptions when current research is unavailable.

Don't repeat a failed command, repair, or route without new evidence and a falsifiable reason. When no authorized evidence-producing action remains, stop and state the concrete missing decision, authority, environment, or evidence.

Return the result naturally. Make clear what was delivered or decided, what evidence supports it, what external effects were performed, and what concern or blocker remains. Don't expose internal routing notes unless they help the user understand a decision.

## Choose the current topic

Node numbers are domains — a menu of topics, not a required sequence. Read only the node for the present decision; jump between them as the work demands.

| Present need | Read |
|---|---|
| target user, problem, promise, pricing, positioning, MVP/MAP, validation, acceptance | `references/nodes/01-market-mvp-scope/README.md` |
| system boundary, API/data/permission/provider contract, architecture, compatibility, migration or build plan | `references/nodes/02-architecture-contracts-plan/README.md` |
| backend, API, data, auth, job, provider, async, reconciliation or observability implementation | `references/nodes/03-backend-api-data-build/README.md` |
| frontend flow, content, visual direction, components, responsive/accessibility behavior or browser proof | `references/nodes/04-frontend-ux-ui-build/README.md` |
| review, test strategy, runtime QA, reliability, security/privacy, evidence or ship judgment | `references/nodes/05-qa-review-security-hardening/README.md` |
| CI/CD, release preparation, deploy, rollout, migration execution, recovery or production verification | `references/nodes/06-ci-cd-launch/README.md` |
| production health, customer evidence, experiments, learning or the next operating decision | `references/nodes/07-ops-growth-iteration/README.md` |

Several shared decision mechanisms — fact states, confidence thresholds, reuse/extend/replace/new, evidence inventory, status and release codes, severity routing — live once in `references/methods.md`; nodes refer to them by name rather than restating.

## Minimum delivery standard

The applicable requirements in the chosen node are the minimum standard, not a required response format. The "minimum" exists so a small task doesn't skip a genuinely applicable security, permission, state, error, accessibility, compatibility, recovery, or verification requirement. It isn't a ritual: skip checks that are genuinely inapplicable, and don't use a task's small size as a reason to skip applicable ones.

For test coverage, follow the repository's threshold when one exists. Without one, prioritize core business rules, authorization, state transitions, failure handling, and changed branches over raising a percentage — use contract, integration, browser, or runtime proof where a unit test would misrepresent the real boundary. Don't write low-value tests to inflate the number.

Go beyond the node's checklist when additional work materially improves the requested result and stays authorized. Don't recite the checklist to the user; satisfy it and report the result and evidence.

## DocumentationDocumentation is split across sibling skills so each can fire on its own trigger:

- **Prose style, removing AI flavor** — the `plain-writing` skill carries the anti-AI-prose rules for any Markdown or HTML writing; apply it whenever you draft or revise prose. If it isn't loaded, `references/docs.md` keeps a short fallback so delivery stays self-sufficient.
- **Durable Markdown docs** — `references/docs.md` covers the document contract, the reader-model test, and the handoff record for maintained READMEs, PRDs, design docs, and release notes.
- **Durable HTML project boards** — the `project-board` skill owns the board-specific topology, coverage manifest, evidence record, reading order, reference-driven look, and browser validation.

A spelling fix, link repair, or a request to preserve original wording doesn't authorize a broader rewrite. Node04 covers documentation that lives inside a frontend surface; Node06 and Node07 cover release notes and ops records as part of their delivery work.

## Maintain useful source commentary

Follow the repo's established documentation style for every source or config file you touch:

- Start the file with a concise comment stating its primary responsibility or boundary.
- Add a concise doc/comment before major classes and functions (including frontend components and handlers) explaining purpose, not narrating implementation.
- Keep comments accurate for public contracts, invariants, and non-obvious constraints; update stale commentary when behavior changes.
- Don't inject comments into strict JSON, lockfiles, generated files, or vendor artifacts; use schema-supported descriptive metadata when available.
