---
name: product-qa-draft
description: Draft node for risk-based code review, functional QA, security and privacy checks, reliability exercises, performance evidence, and release judgment.
---

# QA — draft skeleton

## Questions this node must settle

- What can break the user's core journey, data, permissions, money, or recovery?
- Which checks are unit, contract, static, browser, integration, fault, or production smoke?
- Are failures recorded before batch repair so patterns remain visible?
- Does evidence prove the changed boundary rather than only adjacent helpers?
- Is the final judgment ship, ship with bounded risk, or stop?

## Source material to synthesize

- `../../references/originals/indie-product-delivery/references/nodes/05-qa-review-security-hardening/`
- `../../references/originals/gstack-main/qa-only/SKILL.md`
- `../../references/originals/gstack-main/qa/SKILL.md`
- `../../references/originals/gstack-main/review/SKILL.md`
- `../../references/originals/gstack-main/cso/SKILL.md`
- `../../references/originals/gstack-main/benchmark/SKILL.md`
- `../../references/originals/html-effectiveness/03-code-review-pr.html`
- `../../references/originals/html-effectiveness/12-incident-report.html`

## Read-only reviewer policy to retain

After a major change spanning several requirements or modules, one read-only reviewer receives the request, review base, raw diff, tests, and relevant source. The reviewer reports risk-ordered findings with file/line evidence and never edits. The primary agent decides: accept and repair, reject with evidence, or discuss because the finding changes product intent or authority. Do not invoke this path for a button move, copy change, isolated bug, or small single-module feature.

## Later synthesis work

Define a severity model, evidence ledger, ordinary-user journey matrix, and release-decision template. Remove gstack-specific browser daemon assumptions where the active environment provides a different browser/control surface.
