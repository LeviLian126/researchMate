# Backend Proof, Debug, and Observability

Use this guide to prove an implemented backend slice, debug failures from the real boundary, add proportional observability, and prepare quality evidence without claiming release readiness.

## Sections

- [Backend Proof, Debug, Observability, and Handoff](#backend-proof-debug-observability-and-handoff)

## Backend Proof, Debug, Observability, and Handoff

#### 1. Build a local proof matrix

Start from the Node02 contract and implementation spine. For each changed behavior,
choose the smallest proof that can demonstrate the actual boundary. Prefer existing
test framework, fixtures, helpers, and commands; do not install a framework or invent
a cross-system QA plan just to make Node03 look complete.

| Case | Required when | Typical local proof |
| --- | --- | --- |
| success | every changed capability | unit/service/API behavior through real owner |
| validation | untrusted input or field mapping | rejected/normalized input behavior |
| authentication/access | protected/owned/tenant data | denied, wrong owner, private omission behavior |
| conflict/duplicate | stateful write, retry, webhook, job, or payment | durable duplicate/conflict outcome |
| provider failure | remote dependency or async work | fake/sandbox timeout, malformed response, error mapping |
| transaction rollback | multi-write invariant | failure leaves durable state consistent |
| migration/recovery | schema/data evolution | dry-run/backfill/preflight/repair evidence |
| performance trigger | new list/search/export/fanout/query shape | bounded query/limit/index or measured signal |
| regression | previously working behavior broke | minimal reproduction that fails before the fix |

A test is useful when it exercises production behavior through a meaningful boundary.
Do not test mocks, private implementation trivia, or test-only production seams instead
of the contract. A manual safe check is acceptable only when automation is absent or
the proof requires a real boundary; state its limit.

#### 2. Apply risk-tiered contract-first testing

For new or changed backend behavior, first express the expected behavior in the
existing test style when a test harness is present. Run it and confirm that it fails
for the expected missing/incorrect behavior, then implement the smallest change that
passes and run the narrow proof again.

For a regression, create the smallest reproducible test or script before fixing unless
a safe reproduction is genuinely impossible. The reproduction must distinguish the
reported symptom from a guess and become the guard against recurrence.

| Change type | Node03 testing expectation |
| --- | --- |
| new endpoint/domain behavior | behavior test before or alongside minimal implementation, then targeted pass |
| changed access/data/error contract | negative/edge proof for the changed boundary |
| bug/regression | reproduce first, then prove the fix |
| migration/provider/async | local/sandbox behavior plus failure/retry/recovery proof appropriate to risk |
| local helper with no new behavior | follow nearby convention; do not force ceremonial red-green work |
| no existing test framework | use the smallest executable contract proof and name the coverage limitation |
| new test framework/dependency | return to Node02/05 for approval and test-strategy ownership |

This is not a promise of exhaustive coverage for every function. It prevents
implementation-shaped tests from being the only definition of a new backend contract.

#### 3. Debug from root cause

When behavior, test, migration, provider, or performance evidence fails, do not stack
fixes. Work in this order:

1. Read the complete error, response, trace, command output, and relevant warning.
2. Reproduce the behavior consistently, or collect the missing observation without guessing.
3. Compare recent changes and the nearest working repo pattern.
4. Trace the relevant data from entry through access, domain, persistence, and provider boundaries.
5. State one hypothesis: the suspected root cause and evidence supporting it.
6. Make the smallest diagnostic or code change that can confirm or reject that hypothesis.
7. Add or preserve a behavior proof, implement one focused fix, and rerun the relevant evidence.

For multi-component paths, add safe temporary diagnostics at the boundary that can
distinguish input, configuration, state, and output. Redact secrets and private values;
remove or convert temporary instrumentation into useful bounded observability.

| Observation | Route |
| --- | --- |
| product outcome or acceptance is wrong | Node01 |
| data/access/interface/provider/recovery contract is missing or contradictory | Node02 |
| local implementation root cause is known | focused Node03 fix |
| browser/full-system/security/ship evidence is needed | Node05 |
| production rollout, environment, migration execution, or rollback is implicated | Node06 |

After three focused attempts on one blocker, stop local patching. If the attempts reveal
shared state, cross-module coupling, incompatible runtime assumptions, or repeated new
symptoms, return to Node02 with evidence rather than attempting a fourth fix.

#### 4. Add safe observability and performance signals

Add only the diagnostics needed to understand the changed lifecycle in operation.
Observability must preserve the access and privacy contract; it is not a reason to log
payloads, secrets, tokens, raw provider responses, or private identifiers.

| Signal | Add when | Safe content |
| --- | --- | --- |
| correlation ID | request, job, callback, provider, or multi-write path crosses boundaries | generated/request/job/provider reference without secret payload |
| structured outcome | domain/provider/migration behavior has meaningful failure classes | result class, retryability, safe scope/reference, elapsed time |
| state transition | async, migration, reconciliation, or recovery changes durable status | old/new approved state and authorized actor/process |
| performance measurement | list/search/export/fanout/query path may grow | count/limit/duration/query class without sensitive values |
| recovery hint | operator/manual-repair path exists | safe next action and trace reference |
| alert/monitor need | Node02/06 designed an operational trigger | implementation hook and ownership, not a release decision |

Check changed data paths for N+1/query loops, unbounded collections, missing query
bounds, excessive provider fanout, blocking work in request paths, and repeated
serialization lookups. Fix a clear local implementation defect; return capacity,
storage, queue, caching, or architecture choices to Node02.

#### 5. Verify before claiming completion

A completion claim requires fresh evidence from the current worktree. Identify the
specific command or safe observation that proves each claim, run it, read its full
result and exit code, then report only what the evidence establishes.

| Claim | Fresh evidence |
| --- | --- |
| targeted behavior works | relevant test/reproduction/command shows expected result |
| no regression in scope | affected existing test or characterization proof passes |
| migration mechanism is ready | preflight/dry-run/local verification meets the stated condition |
| provider path is safe locally | fake/sandbox/fixture proves signature, mapping, failure, or dedupe behavior |
| refactor preserved behavior | locked baseline evidence before/after or focused characterization proof |
| docs reflect current truth | affected module/API/backend state page was updated or consciously not needed |

Do not report DONE because code looks plausible, a partial command passed, or an agent
reported success. State unverified remote, production, load, browser, security, or
release facts as named gaps and route them to their owner.

#### 6. Update docs and hand off

Update durable project truth only when the changed backend behavior is discoverable
later: affected module page, API page, or backend-slice partial according to the output
registry. Preserve Node02 architecture facts and Node06 release facts. A code-only
implementation detail with no durable operational or interface value may remain in the
checkpoint rather than creating documentation churn.

Set one implementation status:

| Status | Meaning |
| --- | --- |
| BUILT | requested implementation and required local proof are complete |
| BUILT_WITH_NAMED_GAPS | local behavior is built; bounded remote/QA/release facts remain named |
| BLOCKED | a required implementation fact or safe proof is unavailable |
| NEEDS_NODE02 | contract, boundary, runtime, compatibility, or recovery design must change |
| NEEDS_AUTHORIZATION | a needed side effect requires explicit user/environment authorization |

Hand Node05 the changed contracts/boundaries, proof matrix, commands/results, risk
triggers, unverified facts, logs/correlation conventions, and recommended quality
questions. Do not turn this handoff into a ship verdict.
