---
name: product-architecture-draft
description: Draft node for choosing system boundaries, contracts, data ownership, permissions, providers, migration paths, and reversible technology decisions.
---

# Architecture — draft skeleton

## Questions this node must settle

- What is authoritative state, derived state, and disposable projection?
- Where are tenant, permission, provider, retry, and failure boundaries enforced?
- Which public API/data contracts are expensive to undo?
- What can be reused, extended, replaced, or deferred?
- How will the design expand and contract without a flag-day migration?

## Source material to synthesize

- `../../references/originals/indie-product-delivery/references/nodes/02-architecture-contracts-plan/`
- `../../references/originals/gstack-main/plan-eng-review/SKILL.md`
- `../../references/originals/gstack-main/spec/SKILL.md`
- `../../references/originals/gstack-main/investigate/SKILL.md`
- `../../references/originals/html-effectiveness/04-code-understanding.html`
- `../../references/originals/html-effectiveness/16-implementation-plan.html`

## Later synthesis work

Create a compact architecture decision template, interface inventory, trust-boundary table, and migration/rollback section. Keep diagrams as explanatory artifacts, not substitutes for contracts.
