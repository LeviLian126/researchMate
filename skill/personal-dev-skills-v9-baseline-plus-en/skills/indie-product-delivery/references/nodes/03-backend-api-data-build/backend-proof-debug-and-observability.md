# Backend Proof, Debug, and Observability

Use this guide to prove an implemented backend slice, debug failures from the real boundary, add proportional observability, and prepare quality evidence without claiming release readiness.

## Sections

- [Backend Proof, Debug, Observability, and Handoff](#backend-proof-debug-observability-and-handoff)

## Backend Proof, Debug, Observability, and Handoff

#### 1. Split hermetic and deployed proof before testing

Start from the Node02 contract and implementation spine. For each changed behavior,
choose the smallest proof that can demonstrate the actual boundary. Prefer the existing
test framework, fixtures, helpers, and commands. If a required dependency or environment
is missing, follow the two-branch decision in the root SKILL.md.

Read and obey the repository's execution-environment policy before running anything.
Use the available local or cloud environment that best proves the implementation boundary;
do not create a substitute environment merely to make Node03 look complete.

| Case | Required when | Hermetic local proof | Deployed/server proof |
| --- | --- | --- | --- |
| success | every changed capability | unit/domain/contract behavior through the real owner with in-process fakes | accepted request or job crosses the deployed modules that own the outcome |
| validation | untrusted input or field mapping | rejected/normalized input and schema behavior | deployed boundary rejects the same unsafe input without state leakage |
| authentication/access | protected/owned/tenant data | permission policy and concealed-resource contract | real identity, session, RLS, and cross-user denial in the authorized environment |
| conflict/duplicate | stateful write, retry, webhook, job, or payment | deterministic idempotency and transition rules | durable duplicate/conflict outcome across deployed state and work executors |
| provider failure | remote dependency or async work | fixture-driven timeout, malformed response, and error mapping | bounded provider or managed-sandbox failure through deployed protected configuration |
| transaction rollback | multi-write invariant | repository/transaction contract with isolated in-process state | managed database failure leaves durable deployed state consistent |
| migration/recovery | schema/data evolution | migration-file validation, dry-run, or pure backfill transform | deployed migration, restart, repair, and recovery evidence |
| performance trigger | new list/search/export/fanout/query shape | bounds, limits, query-shape contract, or deterministic benchmark | measured deployed latency, resource, quota, or queue signal |
| regression | previously working behavior broke | smallest network-free reproduction that fails before the fix | repeat only when the regression depends on a real deployed boundary |

Name the deployed commit, environment, safe data set, protected dependencies, quota bound,
and cleanup/recovery expectation in integration evidence. If the required environment is
unavailable, keep the integration claim explicitly unverified instead of inventing an
equivalent environment.

For repositories without a server-only integration policy, use the smallest authorized
proof environment and keep local infrastructure proportional. Do not weaken an explicit
server-only rule for convenience.

A test is useful when it exercises production behavior through a meaningful boundary.
Do not test mocks, private implementation trivia, or test-only production seams instead
of the contract. A manual safe check is acceptable only when automation is absent or
the proof requires a real boundary; state its limit.

#### 2. Prove the delivered artifact in a clean environment

For every deployable package, workspace member, executable, library, plugin, or service
artifact, reproduce the repository's locked restore/install and build path in a
clean environment. Then load the produced artifact through its real language/runtime
mechanism and invoke its declared entrypoint or smallest safe smoke command.

| Proof | Required check |
| --- | --- |
| dependency resolution | use the committed lock or immutable dependency mode; reject an unrecorded re-resolution |
| package/build metadata | confirm each intended deliverable is included by the build system, workspace, module, manifest, or package-discovery rules |
| artifact creation | run the same compile, bundle, package, or publish-dry-run path used by delivery when applicable |
| loadability | import, require, load, link, execute, or otherwise open every deployable artifact using the production runtime |
| entrypoint | invoke the declared command, module, handler, or service startup far enough to detect missing code or runtime dependencies |
| platform/source selection | keep architecture, registry/index/source, CPU/GPU, native-library, and toolchain choices explicit and reproducible |

A resolver or installer succeeding proves only the dependency operation it performed. It
does not prove that owned source entered the artifact, that the artifact can be loaded, or
that its entrypoint works. Keep local developer state, globally installed packages, prior
build output, and warm caches out of this proof. When a clean proof is too expensive for
every change, define a cheaper pull-request target and retain the complete proof at the
release or scheduled gate; label the cheaper result as partial.

#### 3. Apply risk-tiered contract-first testing

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
| migration/provider/async | contract behavior plus deployed/server failure, retry, and recovery proof appropriate to the implementation |
| local helper with no new behavior | follow nearby convention; do not force ceremonial red-green work |
| no existing test framework | use the smallest executable contract proof and name the coverage limitation |
| new test framework/dependency | record the dependency reason and route architecture/test-strategy impact to Node02/05 |

This is not a promise of exhaustive coverage for every function. It prevents
implementation-shaped tests from being the only definition of a new backend contract.

Cover the core business behavior changed by the slice. The goal is confidence in the
decisions and state transitions that matter to users and data, not an aggregate number.
Measure and report coverage when the repository already supports it, but do not narrow the
scope or create low-value tests to improve a percentage. Give the most important code
stronger proof:

| Code or boundary | Testing expectation |
| --- | --- |
| domain rules, authorization, money/quota, state transitions, idempotency, retry, reconciliation, and recovery decisions | cover meaningful success, denial/failure, boundary, and state-change paths as far as practical |
| deterministic validation, mapping, calculation, and transformation | prefer focused unit tests with representative edge cases |
| database, queue, provider, filesystem, framework, or process behavior | unit-test owned decisions around the seam; use contract or authorized integration proof for behavior that depends on the real system |
| generated/vendor code, declarative schema, framework bootstrap, or configuration-only wiring | exclude from unit-coverage scope only when the reason is explicit and another fitting validation layer covers it |
| trivial accessors, constants, or private implementation details | do not add tests solely to increase the percentage |

When an existing repository has a coverage baseline, a bounded change should not reduce
it and must cover the core behavior it changes. Raise a broader deficit only during a
quality or test-hardening task and report the remaining gap; do not silently turn an
unrelated small fix into a repository-wide test rewrite.

#### 4. Debug from root cause

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

Stop local patching when another attempt would add no new evidence. If the evidence reveals
shared state, cross-module coupling, incompatible runtime assumptions, or repeated new
symptoms, return to Node02 with that evidence rather than continuing speculative fixes.

#### 5. Add safe observability and performance signals

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

#### 6. Verify before claiming completion

A completion claim requires fresh evidence from the current worktree. Identify the
specific command or safe observation that proves each claim, run it, read its full
result and exit code, then report only what the evidence establishes.

| Claim | Fresh evidence |
| --- | --- |
| targeted behavior works | relevant test/reproduction/command shows expected result |
| no regression in scope | affected existing test or characterization proof passes |
| migration mechanism is ready | hermetic file/preflight proof plus any required deployed migration evidence meets the stated condition |
| provider contract is safe | network-free fake/fixture proves signature, mapping, failure, or dedupe behavior; deployed proof remains separate |
| refactor preserved behavior | locked baseline evidence before/after or focused characterization proof |
| docs reflect current truth | affected module/API/backend state page was updated or consciously not needed |

Do not report DONE because code looks plausible, a partial command passed, or an agent
reported success. State unverified remote, production, load, browser, security, or
release facts as named gaps and route them to their owner.

#### 7. Update docs and hand off

Update durable project truth only when the changed backend behavior is discoverable
later: affected module page, API page, or backend-slice partial according to the output
registry. Preserve Node02 architecture facts and Node06 release facts. A code-only
implementation detail with no durable operational or interface value may remain in the
checkpoint rather than creating documentation churn.

Set one implementation status:

| Status | Meaning |
| --- | --- |
| BUILT | requested implementation and required hermetic proof are complete |
| BUILT_WITH_NAMED_GAPS | implementation behavior is built; bounded environment or release facts remain named |
| BLOCKED | a required implementation fact or safe proof is unavailable |
| NEEDS_NODE02 | contract, boundary, runtime, compatibility, or recovery design must change |
| NEEDS_CREDENTIALS_OR_ENVIRONMENT | required proof depends on a missing secret, API credential, or unavailable environment |

## Re-evaluate the model before repeating a repair

When a repair path stops producing new information, re-read the requested behavior, restate
the observed evidence, expose the assumptions shared by the failed path, and try another
hypothesis, route, boundary, or evidence source. The goal is to escape a dead loop, not to
count attempts.

Keep a short hypothesis ledger during difficult debugging: observation, proposed cause, discriminating check, result, and next conclusion. Run the cheapest check that can separate competing causes. Add temporary instrumentation only where it changes the diagnosis, then remove it or convert it into intentional observability before handoff.

Tests should lock behavior at the narrowest stable seam. Mock external effects or slow infrastructure at an owned boundary, not private calls inside the implementation. A test that mirrors the current code shape can pass while the contract is broken and will obstruct safe refactoring later.
