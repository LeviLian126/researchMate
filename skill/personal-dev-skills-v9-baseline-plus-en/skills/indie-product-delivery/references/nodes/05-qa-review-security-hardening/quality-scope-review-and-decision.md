# Quality Scope and Diff Review

Use this guide to identify what must be proven, choose proportional evidence, and review a diff or implementation against intent and contracts before runtime, security, or release judgments.

## Sections

- [Quality Discovery and Evidence Plan](#quality-discovery-and-evidence-plan)
- [Diff, Intent, and Contract Review](#diff-intent-and-contract-review)

## Quality Discovery and Evidence Plan

#### 1. Recover quality truth

Restate the quality question in one sentence: review whether a named slice satisfies
the current requirements/contracts and is safe to test, merge, or hand to release.

Read in authority order: explicit user request; Node01 criteria; Node02 contracts/test
handoff; Node03/04 checkpoints; meaningful diff; current environment/build; previous
QA evidence; registered docs. Classify every material fact.

| Fact state | Meaning | QA treatment |
| --- | --- | --- |
| confirmed | current source, contract, environment, or direct command/observation supports it | use as claim |
| defaulted | reversible scope/detail inferred from established convention | record briefly |
| inferred | likely but not verified from code/diff/history | verify or mark a gap |
| unknown | missing, stale, conflicting, or inaccessible | stop or route owner |

Never default release target, user acceptance, security posture, data sensitivity,
authorization scope, migration safety, production behavior, or ship status.

#### 2. Recover environment and authority

Identify target revision/build, review base, environment, running services, safe test
accounts/data, available browser/API/test paths, provider/credential limits, and
prohibited actions. Safe quality work never requires recording passwords, session
cookies, tokens, secret values, or real PII.

| Concern | Required statement |
| --- | --- |
| target | branch/commit/build/environment under review |
| intent | requirement, plan, bug report, or acceptance source |
| change scope | read-only review, narrow fixes requested by the task, or planning only |
| data/auth | test account, mock, local/staging scope, and prohibited production actions |
| available proof | tests, browser, API, logs, dry run, static review, CI/build |
| sensitive trigger | auth, tenant, payment, PII, secret, upload, provider, migration, public API |
| stop condition | missing contract, unsafe target, unavailable role, blocked environment, or missing credential |

If the current request includes fixing findings, repair them directly when the repair is
narrow and contract-preserving. If the request asks only for a report, report findings.

#### 3. Choose the proportional gate

| Gate | Use when | Minimum evidence |
| --- | --- | --- |
| G0 | docs, copy, static isolated presentation | changed-file review and relevant links/assets |
| G1 | narrow low-blast implementation inside known contract | targeted proof, changed-path review, adjacent regression |
| G2 | vertical UI/API/data/provider/auth-adjacent slice | acceptance matrix, runtime/API/browser evidence, contract checks |
| G3 | release, public endpoint, payment, PII, admin, tenant, secret, upload, webhook, migration, auth, provider trust | full relevant proof, negative/sensitive checks, recovery/rollback facts, final status |

Escalate to G3 when a path can leak data, bill incorrectly, bypass access, corrupt
durable state, create irreversible external effects, or break a public contract.
Reduce scope rather than lowering a necessary gate.

#### 4. Build the evidence matrix

Convert every requirement, risk, regression, and release claim into one observable
question. Select the smallest evidence that can prove it.

| Claim/risk | Source | Evidence | Command/observation | Expected | Actual | Status | Owner/gap |
| --- | --- | --- | --- | --- | --- | --- | --- |

Use PASS, FAIL, GAP, NOT_APPLICABLE, or DEFERRED. A test passing is evidence for the
behavior it exercises, not for every nearby claim. Match proof to layer: unit for pure
rules, integration for writes/transactions, request/API for interface, browser for
visible flows, negative tests for access, dry-run/preflight for migration, and
   static/dynamic checks for security within the target scope.

#### 5. Select relevant specialist paths

| Trigger | Add workflow |
| --- | --- |
| branch/PR/patch/plan completion | diff-intent-contract review |
| user-visible journey, UI state, regression | runtime/browser QA |
| auth, tenant, PII, secret, payment, upload, callback, AI, admin | security/privacy/trust |
| API compatibility, provider/job, retry, migration, transaction, performance, flake | reliability/performance/evolution |
| all paths before final status | final quality decision |

Use existing test framework, fixtures, browser harness, and repo convention. Do not
install a framework, fabricate a performance test, or require a full-app crawl unless
the active risk demands it.

## Diff, Intent, and Contract Review

#### 1. Establish review mode and intent

Follow the requested outcome: report findings for an assessment, or fix them directly when
the request includes repair. Identify a meaningful base and include relevant committed and uncommitted
changes; stop cleanly if there is no diff to review.

Recover intent in authority order: approved Node01/02 output, explicit request,
accepted plan, issue/PR description, acceptance criteria, relevant commit messages, and
deferred work. A commit message is weaker evidence than an approved requirement.

#### 2. Audit scope and completion

When intent has actionable items, classify each item rather than assuming a changed file
means delivery.

| Status | Meaning |
| --- | --- |
| DONE | diff and proof clearly deliver the accepted behavior |
| PARTIAL | meaningful work exists but a required behavior/proof is incomplete |
| NOT_DONE | no evidence addresses the accepted item |
| CHANGED | different implementation achieves the same approved outcome |
| DRIFT | unrelated behavior/refactor entered the diff |
| MISSING | accepted requirement or required proof is absent |

Be conservative with DONE and generous with CHANGED when the goal and contract are
actually satisfied. Do not penalize an implementation merely because it differs from a
file-level plan; do flag a different public/security/data behavior.

#### 3. Read full diff and affected context

Read the complete diff before reporting. Then inspect callers, consumers, schema,
configuration, tests, docs, and direct dependents needed to understand changed shared
behavior. Do not review only hunk-local style.

| Context question | Check |
| --- | --- |
| input/output | caller assumptions, type/enum/status consumers, public fields |
| data | migration, constraints, ownership/tenant filters, existing records |
| access | route guards, service authorization, private fields, admin paths |
| external | provider adapters, callbacks, retries, secrets, mocks |
| frontend | visible state, error/recovery, contract mock drift |
| docs/tests | examples/current truth, changed branch/error coverage |
| config | feature flags, environment behavior, dependency/build impact |

#### 4. Review in risk order

Review highest impact first:

1. data/migration safety, concurrency/idempotency, authz/tenant scope, secrets,
   injection, provider/LLM trust;
2. API/data/UI contract fit, public compatibility, error/recovery behavior, enum/status
   completeness and access/privacy;
3. acceptance, regression coverage, negative paths, test isolation/flakiness;
4. maintainability, unnecessary complexity, performance, docs, and distribution only
   when the diff creates that risk.

A finding must state severity, confidence, file/line or concrete evidence, user/data
impact, smallest safe fix or owner, and proof required after repair.

| Confidence | Reporting treatment |
| --- | --- |
| high | verified source/evidence; report directly |
| medium | plausible pattern; label verification needed |
| low | omit unless potential impact is critical |

Do not report style preference, hypothetical future scale, or an unverifiable suspicion
as a blocker.

#### 5. Handle fixes and review feedback correctly

Before accepting, rejecting, or fixing a reported issue, verify it against source,
contract, and behavior. A narrow repair is permitted only when it preserves scope,
public behavior, security posture, and architecture. Rerun the original/narrow proof
afterward.

Route product promise/acceptance to Node01; contract/compatibility/lifecycle/trust to
Node02; backend/frontend implementation to Node03/04; release action to Node06. Do not
change a test merely to make a regression look accepted.

## Return findings that an implementer can act on

A review finding identifies the violated contract, the concrete evidence, the user or system consequence, and the narrow repair direction. Point to the relevant file, symbol, route, state, or behavior. Avoid style preferences presented as defects and avoid vague findings such as “needs more tests” without naming the uncovered risk.

When a major cross-module change receives an independent read-only review, keep the reviewer separate from implementation. The reviewer does not edit the branch or broaden scope. The primary agent verifies each finding, applies the valid ones, and reruns the relevant checks. Repeat review only when the fixes materially changed the risk surface; do not create an endless reviewer loop for minor wording or formatting changes.

## Final Quality Decision and Release Handoff

Use this guide after the required evidence paths complete to issue one quality judgment, record bounded concerns, and prepare a release handoff without authorizing or executing production effects.

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

#### 3. Apply a risk-tiered decision

| Status | Allowed only when |
| --- | --- |
| SHIP | required claims pass, no blocker/Critical/High issue remains, sensitive evidence is sufficient |
| SHIP_WITH_CONCERNS | acceptance and sensitive paths pass; each residual risk is non-critical, bounded, owned, mitigated, and has a trigger/follow-up |
| BLOCKED | acceptance fails, required evidence is missing, reliability/security issue blocks, or a required environment is unavailable |
| NEEDS_OWNER | product, contract, implementation, architecture, recovery, or environment truth must be corrected by its owner |
| NEEDS_CREDENTIALS_OR_ENVIRONMENT | required dynamic, security, or release evidence needs a missing credential or unavailable environment |

Never issue SHIP_WITH_CONCERNS for failed acceptance, Critical/High security, missing
auth/payment/tenant/PII/provider/migration proof, failed production build, or unknown
recovery behavior.

#### 4. Record durable quality state

Update the registered quality current-state page and affected module/API pages only
when evidence, risk, quality status, or a durable remediation fact needs future
retrieval. Follow `../08-agent-context-html/README.md`; exclude secrets, raw
PII, auth material, exploit details, and unstable worklog narration.

| Record | Include |
| --- | --- |
| target | revision/build/environment reviewed and scope |
| status | quality decision and gate rationale |
| evidence | commands/observations, result, limitations |
| findings | severity, confidence, owner, remediation/retest state |
| concerns | non-blocking owner, trigger, mitigation, follow-up node |
| blockers | exact missing/failed claim and prior attempts |
| release handoff | required Node06 inputs and credential/environment limits |

#### 5. Hand off to Node06 or previous owner

For SHIP or bounded SHIP_WITH_CONCERNS, hand Node06 the quality status, evidence
matrix, validated environment facts, migration/provider/recovery prerequisites,
unverified items, residual risks, rollback/forward-fix assumptions from Node02/03, and
missing credential or environment limitation. Node06 decides release readiness and executes
the planned actions with the configured repository access.

For a blocked result or one that needs another owner, name the smallest blocking claim and its owner:
Node01 for acceptance, Node02 for contract/trust/compatibility, Node03/04 for
implementation, Node05 for unfinished evidence, or Node06 for release/environment
truth. Do not make a release handoff look like a ship approval.
