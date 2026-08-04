---
name: indie-product-delivery-v2-draft
description: Draft router and source-preservation workspace for turning a product idea into an evidence-backed release across discovery, architecture, backend, frontend, QA, deployment, HTML documentation, and plain-language writing. This is a material-collection skeleton, not the finished production skill.
---

# Indie Product Delivery v2 — material skeleton

## Status

This directory is phase 1 only: preserve source material, define boundaries, and leave explicit synthesis work for the next iteration. Do not treat the node drafts as settled policy.

## Routing skeleton

Read only the node that owns the current decision:

| Need | Draft node |
|---|---|
| market pressure, target user, toy project vs product, MVP proof | `nodes/01-product-discovery/SKILL.md` |
| system boundary, contracts, data, permissions, evolution plan | `nodes/02-architecture/SKILL.md` |
| API, persistence, async jobs, providers, observability | `nodes/03-backend/SKILL.md` |
| user flow, visual direction, accessibility, browser behavior | `nodes/04-frontend/SKILL.md` |
| test strategy, review, security, reliability, ship judgment | `nodes/05-qa/SKILL.md` |
| CI/CD, environment configuration, migration, rollout, rollback | `nodes/06-release-operations/SKILL.md` |
| durable interactive HTML documentation and evidence boards | `nodes/07-html-documentation/SKILL.md` |
| direct, natural, non-promotional human-facing prose | `nodes/08-human-writing/SKILL.md` |

## Shared boundaries to retain

- Prefer current user instructions, repository rules, source, tests, and deployed evidence over stale prose.
- Keep local checks hermetic when the repository says not to install integration dependencies locally.
- Default to one primary agent. A major cross-module implementation receives one read-only QA review after the primary change; small isolated work does not.
- Separate verified, implemented-but-unverified, planned, and rejected claims.
- Require explicit authority for deployment, migrations, charges, destructive changes, external messages, or production data writes.
- Preserve source material verbatim under `references/originals/`; synthesize later instead of silently rewriting upstream guidance.

## Material map

Read `references/source-manifest.md` before synthesizing a node. Read `references/synthesis-map.md` for proposed joins, conflicts, and unresolved choices. The production/source/HTML audit is in `references/researchmate-html-source-production-audit.md`.

## Next iteration

The next iteration should deduplicate concepts, resolve conflicts with system/repository rules, define acceptance artifacts for each node, write cross-node handoff contracts, and only then create evals. Do not run the full skill-creator benchmark loop during this collection phase.
