---
name: indie-product-delivery
description: "Use for evidence-backed delivery of bootstrapped software products, including durable project documentation that must stay aligned with repository truth. Apply when work spans product scope, architecture, implementation, quality, release, or operations; when ownership is unclear; or when creating or materially revising an HTML project board, README, PRD, design document, or release note with verified facts, contracts, risks, and reader-ready wording. Do not auto-trigger for isolated specified local edits, mechanical doc fixes, small UI copy, general questions, or work fully covered by a specialized skill."
---

# Indie Product Delivery

Drive the user's requested product outcome to an evidence-backed terminal result. Support web apps, APIs, CLIs, SDKs, packages, and related software-product surfaces without assuming that every task should continue to release.

## Establish the working contract

Recover from the request and current evidence:

- the original goal and the result that would satisfy it;
- the repository, product surface, environment, and relevant existing behavior;
- confirmed requirements, non-goals, acceptance, and unresolved decisions;
- authority for local changes and any external effects;
- available tools, credentials, runtime, and evidence.

Do not require the user to restate facts available in the repository. Ask only for a decision, authority, or evidence that cannot be discovered safely.

## Operate through the kernel

1. Read `references/nodes/00-product-delivery-kernel/README.md`.
2. Initialize its compact delivery state and select one current owner.
3. Read the owner's README and only the workflow guide needed for the present decision or slice.
4. Execute toward the terminal target set by the original request. Load another node only when a named precondition, failed gate, or newly discovered boundary requires a handoff.
5. Verify the narrowest evidence that directly supports the claimed result. Do not infer browser, runtime, security, persistence, or release proof from weaker substitutes.
6. Finish with a global terminal status. An internal route or next node is not task completion.

A request to plan may finish with an actionable plan. A request to implement may finish with a verified local change. Review-only work must not edit. Release preparation and verified release are distinct targets.

## Use references progressively

- Node01: product, market, pricing, MVP, positioning, and acceptance.
- Node02: system boundaries, data, trust, interfaces, architecture, evolution, and build plans.
- Node03: backend, API, data, provider, async, and observability implementation.
- Node04: frontend experience, visual direction, responsive/accessibility implementation, and browser proof.
- Node05: review, runtime evidence, reliability, security, and ship judgment.
- Node06: release readiness, CI/CD, rollout, recovery, and release verification.
- Node07: production health, customer evidence, experiments, and the next operating decision.
- Durable documentation: read `references/durable-document-quality.md` when creating or substantially updating a README, PRD, design document, release/change note, HTML project board, or another maintained project source of truth. It is a quality gate inside the current owner, never a routing owner or replacement for product, architecture, authority, or evidence decisions. Do not require its full workflow for a mechanical correction, isolated UI copy, or ordinary chat response.
- Project documentation: additionally read `references/agent-context-html/instructions.md` when the durable document is an HTML project board or an established board owns facts changed by the work.

## Return the result naturally

Do not force a checkpoint or fixed heading template. Make the final response clear about the actual deliverable or decision, acceptance evidence, external effects performed, and any residual concern, missing authority, missing evidence, or user decision. For durable documentation, also identify the document type, fact sources, completed style audit, reader-test status, and any remaining reader-comprehension risk. Use the user's language for chat while preserving durable project language and source literals.
