# Quality Scope and Diff Review

Use this guide to identify what must be proven, choose proportional evidence, and review a diff or implementation against intent and contracts before runtime, security, or release judgments.

## Sections

- [Quality Discovery and Evidence Plan](#quality-discovery-and-evidence-plan)
- [Diff, Intent, and Contract Review](#diff-intent-and-contract-review)

## Quality Discovery and Evidence Plan

#### 1. Recover quality truth

Restate the quality question in one sentence: review whether a named slice satisfies
approved requirements/contracts and is safe to test, merge, or hand to release.

Read in authority order: explicit user request; Node01 criteria; Node02 contracts/test
handoff; Node03/04 checkpoints; meaningful diff; current environment/build; previous
QA evidence; registered docs. Classify every material fact.

| Fact state | Meaning | QA treatment |
| --- | --- | --- |
| confirmed | current source, contract, environment, or explicit authorization supports it | use as claim |
| defaulted | reversible scope/detail inferred from established convention | record briefly |
| inferred | likely but not verified from code/diff/history | verify or mark a gap |
| unknown | missing, stale, conflicting, or inaccessible | stop or route owner |

Never default release target, user acceptance, security posture, data sensitivity,
authorization scope, migration safety, production behavior, or ship status.

#### 2. Recover environment and authority

Identify target revision/build, review base, environment, running services, authorized
accounts/data, available browser/API/test paths, provider/credential limits, and
prohibited actions. Safe quality work never requires recording passwords, session
cookies, tokens, secret values, or real PII.

| Concern | Required statement |
| --- | --- |
| target | branch/commit/build/environment under review |
| intent | requirement, plan, bug report, or acceptance source |
| mutation mode | REVIEW_ONLY, CHANGE_AND_VERIFY, or PLAN_ONLY |
| data/auth | test account, mock, local/staging scope, and prohibited production actions |
| available proof | tests, browser, API, logs, dry run, static review, CI/build |
| sensitive trigger | auth, tenant, payment, PII, secret, upload, provider, migration, public API |
| stop condition | missing contract, unsafe target, unavailable role, blocked environment, authorization gap |

A review request is REVIEW_ONLY by default. Quality may repair only when the user
explicitly authorizes fixes and the repair remains narrow and contract-preserving.

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
authorized static/dynamic checks for security.

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

Use REVIEW_ONLY for review/check/assessment requests. Use CHANGE_AND_VERIFY only when the
user asks to fix findings. Identify a meaningful base and include relevant committed and
uncommitted changes; stop cleanly if there is no diff to review.

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
