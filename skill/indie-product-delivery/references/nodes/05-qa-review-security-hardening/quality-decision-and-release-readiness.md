# Quality Decision and Release Readiness

Use this guide after the required evidence paths complete to issue one quality judgment, record bounded concerns, and prepare a release handoff without authorizing or executing production effects.

## Sections

- [Final Quality Decision and Release Handoff](#final-quality-decision-and-release-handoff)

## Final Quality Decision and Release Handoff

#### 1. Reconcile evidence before status

Return to the quality matrix and update every claim with current evidence. Compare
planned acceptance, actual implementation, runtime result, review findings, security
scope, reliability/migration assessment, and repair/retest evidence.

| Evidence state | Meaning |
| --- | --- |
| PASS | observed result meets the claim at the relevant layer |
| FAIL | observed result contradicts acceptance, contract, safety, or reliability requirement |
| GAP | required proof is missing, stale, unavailable, or insufficient |
| NOT_APPLICABLE | risk was considered and is genuinely absent |
| DEFERRED | non-blocking work deliberately postponed with owner and trigger |

Do not infer PASS from nearby tests, a clean diff, an agent report, a screenshot, or
confidence alone. A final status is only as strong as the weakest required claim.

#### 2. Require fresh verification evidence

Before stating a completion or quality claim, identify the command/observation that
proves it, run or inspect it in the current state, read the full result, and record
actual output/limit.

| Claim | Fresh evidence |
| --- | --- |
| tests pass | exact relevant command and current zero-failure result |
| build/lint/type check | full applicable command and exit/result |
| user flow works | browser/API observation through the relevant state |
| bug is fixed | original reproduction now passes plus adjacent regression when relevant |
| access/security holds | authorized negative proof at enforcement boundary |
| migration is ready | preflight/dry-run/validation/repair evidence, not production execution |
| release is ready | valid Node05 matrix and Node06 prerequisites, not a deploy assertion |
| requirement is complete | acceptance-to-evidence matrix, not tests alone |

State unverified remote, production, load, browser, security, or release facts as gaps
with owner. Never disguise absence of evidence as a concern-free result.

#### 3. Apply the risk-tiered decision

| Status | Allowed only when |
| --- | --- |
| SHIP | required claims pass, no blocker/Critical/High issue remains, sensitive evidence is sufficient |
| SHIP_WITH_CONCERNS | acceptance and sensitive paths pass; each residual risk is non-critical, bounded, owned, mitigated, and has a trigger/follow-up |
| BLOCKED | acceptance fails, required evidence is missing, reliability/security issue blocks, or a required environment is unavailable |
| NEEDS_PREVIOUS_NODE | product, contract, implementation, architecture, or recovery truth must be corrected upstream |
| NEEDS_AUTHORIZATION | required dynamic/security/release evidence exceeds granted scope |

Never issue SHIP_WITH_CONCERNS for failed acceptance, Critical/High security, missing
auth/payment/tenant/PII/provider/migration proof, failed production build, or unknown
recovery behavior.

#### 4. Record durable quality state

Update the registered quality current-state page and affected module/API pages only
when evidence, risk, quality status, or a durable remediation fact needs future
retrieval. Follow `references/agent-context-html/instructions.md`; exclude secrets, raw
PII, auth material, exploit details, and unstable worklog narration.

| Record | Include |
| --- | --- |
| target | revision/build/environment reviewed and scope |
| status | quality decision and gate rationale |
| evidence | commands/observations, result, limitations |
| findings | severity, confidence, owner, remediation/retest state |
| concerns | non-blocking owner, trigger, mitigation, follow-up node |
| blockers | exact missing/failed claim and prior attempts |
| release handoff | required Node06 inputs and authorization limits |

#### 5. Hand off to Node06 or previous owner

For SHIP or bounded SHIP_WITH_CONCERNS, hand Node06 the quality status, evidence
matrix, validated environment facts, migration/provider/recovery prerequisites,
unverified items, residual risks, rollback/forward-fix assumptions from Node02/03, and
exact authorization still required. Node06 decides release readiness and executes only
authorized actions.

For BLOCKED or NEEDS_PREVIOUS_NODE, name the smallest blocking claim and its owner:
Node01 for acceptance, Node02 for contract/trust/compatibility, Node03/04 for
implementation, Node05 for unfinished evidence, or Node06 for release/environment
truth. Do not make a release handoff look like a ship approval.
