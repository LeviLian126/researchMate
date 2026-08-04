---
name: backend-delivery-draft
description: Draft node for implementing and verifying APIs, domain services, repositories, SQL, async jobs, provider adapters, reconciliation, and observability.
---

# Backend — draft skeleton

## Questions this node must settle

- Does parameter and identity context survive router → service → adapter/repository → SQL?
- Are transactions, idempotency, leases, retries, and terminal states explicit?
- Do external provider failures degrade honestly and observably?
- Are tenant filters enforced at every storage and projection boundary?
- Which proof is hermetic and which requires managed infrastructure?

## Source material to synthesize

- `../../references/originals/indie-product-delivery/references/nodes/03-backend-api-data-build/`
- `../../references/originals/indie-product-delivery/references/nodes/02-architecture-contracts-plan/system-boundaries-data-and-trust-contracts.md`
- `../../references/originals/gstack-main/plan-eng-review/SKILL.md`
- `../../references/originals/gstack-main/investigate/SKILL.md`
- `../../references/originals/gstack-main/review/SKILL.md`

## Later synthesis work

Turn the current API-order inspection idea into a repeatable checklist covering schemas, adapters, services, repositories, SQL, migrations, queues, and cleanup. Preserve the rule that missing local integration dependencies move proof to CI/cloud instead of creating an unrequested local environment.
