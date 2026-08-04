---
name: release-operations-draft
description: Draft node for CI/CD, environment configuration, commit identity, migrations, deployment, smoke verification, monitoring, rollback, and post-release records.
---

# Release and operations — draft skeleton

## Questions this node must settle

- Which exact SHA, artifacts, migrations, and environment values form the release?
- Which checks run locally, in CI, and only against managed services?
- Are secrets, paid providers, and destructive migrations gated explicitly?
- What are the readiness, smoke, rollback, and stop conditions?
- Does the durable documentation describe the same deployed ref and evidence?

## Source material to synthesize

- `../../references/originals/indie-product-delivery/references/nodes/06-ci-cd-launch/`
- `../../references/originals/indie-product-delivery/references/nodes/07-ops-growth-iteration/`
- `../../references/originals/gstack-main/setup-deploy/SKILL.md`
- `../../references/originals/gstack-main/ship/SKILL.md`
- `../../references/originals/gstack-main/land-and-deploy/SKILL.md`
- `../../references/originals/gstack-main/canary/SKILL.md`
- `../../references/originals/gstack-main/document-release/SKILL.md`
- `../../references/originals/html-effectiveness/11-status-report.html`
- `../../references/originals/html-effectiveness/13-flowchart-diagram.html`
- `../../references/originals/html-effectiveness/17-pr-writeup.html`

## Workflow to retain

Design → source → HTML/OpenAPI → local already-supported hermetic checks → cloud CI/integration → intentional main commit/push when authorized → migration → Vercel/Render → smoke/rollback evidence. Do not install missing local modules merely to imitate managed integration.

## Later synthesis work

Make deployment-provider details pluggable while preserving commit identity, expand/contract migration discipline, paid-resource gates, and rollback proof.
