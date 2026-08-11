---
name: robust-software-testing
description: Systematically design, implement, run, and review software tests for correctness, robustness, security boundaries, business-logic abuse, workflow bypass, resource exhaustion, concurrency, resilience, fuzzing, property-based testing, performance, and mutation testing. Use when ChatGPT is asked to test or audit a codebase, API, service, library, feature, parser, workflow, or pull request; improve an existing test suite; create a test plan; find missing edge/adversarial cases; reproduce a bug as a regression test; or assess whether software fails safely under malformed, hostile, expensive, concurrent, or dependency-failure conditions.
---

# Robust Software Testing

Treat testing as risk reduction, not as a coverage-maximization exercise. Test observable behavior and system invariants. Use the cheapest test layer that can faithfully expose each risk, and escalate to larger tests when unit tests cannot provide sufficient fidelity.

## Core principles

1. Model risk before generating tests. Identify externally controllable inputs, trust boundaries, state transitions, side effects, shared resources, concurrency points, and dependencies.
2. Test behaviors and contracts rather than mirroring implementation methods one-for-one.
3. Cover both positive and negative space. For every important rule, test that permitted behavior succeeds and forbidden behavior fails safely.
4. Assert side effects, not only return values. Check persistence, emitted events, external calls, authorization decisions, resource usage, retries, and cleanup where relevant.
5. Treat business logic, authorization, state transitions, and resource budgets as security properties.
6. Prefer deterministic, hermetic, fast tests for frequent execution. Use larger integration, performance, fuzz, or fault-injection tests only where their fidelity is necessary.
7. Convert every discovered bug, crash, bypass, race, or pathological input into a minimized regression test or retained fuzz corpus entry.
8. Do not equate line coverage with test quality. Use coverage to find blind spots and mutation testing to assess whether assertions detect meaningful behavior changes.
9. Never perform disruptive stress, fuzz, chaos, or denial-of-service experiments against third-party systems or production systems without explicit authorization, bounded blast radius, abort conditions, and observability.

## Workflow

Follow these phases in order. Skip a phase only when it is clearly irrelevant to the target.

### Phase 1: Understand the system under test

Inspect the repository, existing tests, build files, API/schema definitions, configuration, persistence boundaries, authorization code, queues, caches, external integrations, and operational limits before writing tests.

Determine:

- Public entrypoints: functions, methods, HTTP/RPC endpoints, consumers, CLI commands, file/protocol parsers, scheduled jobs.
- Trust boundaries: unauthenticated input, authenticated users, cross-tenant identifiers, external services, files, messages, database rows, environment/configuration.
- Critical invariants: properties that must remain true regardless of input or execution path.
- State machines: lifecycle states and allowed transitions.
- Side effects: writes, charges, messages, emails, callbacks, jobs, filesystem effects, downstream calls.
- Resource multipliers: loops, recursion, decompression, regex, sorting, joins, fan-out, pagination, batch operations, retries, queue production, third-party billing.
- Concurrency points: read-modify-write flows, locks, uniqueness constraints, idempotency keys, inventory/balance changes, distributed coordination.
- Failure boundaries: databases, caches, queues, DNS, network, filesystem, clock, external APIs, credentials, quotas.

Do not start by generating dozens of tests. First write a compact risk map.

### Phase 2: Build a risk-driven test matrix

For every important public behavior, consider the following dimensions. Mark each as applicable, not applicable, already covered, or missing.

| Dimension | Questions to answer |
|---|---|
| Happy path | Does valid normal input produce the required result? |
| Boundary | What happens at min, max, empty, one, max-1, max, max+1, and numeric/size limits? |
| Type/schema | Are wrong types, missing fields, nulls, malformed encodings, duplicates, unknown fields, and incompatible versions rejected safely? |
| Logical validity | Can individually valid fields form an invalid combination? Are cross-field and server-side business rules enforced? |
| Invariant/property | What must always remain true across many inputs or operation sequences? |
| Authorization | Can changing user, tenant, object ID, role, method, hidden field, or endpoint bypass access control? |
| Workflow/state | Can steps be skipped, reordered, repeated, replayed, raced, or directly invoked? |
| Idempotency/replay | Can duplicate delivery or retry create duplicate effects? |
| Concurrency | Can simultaneous valid operations violate uniqueness, balance, quota, inventory, or state assumptions? |
| Resource cost | Can one valid-looking request consume disproportionate CPU, memory, DB work, threads, connections, storage, network, queue capacity, or paid downstream calls? |
| Failure/resilience | What happens on timeout, partial failure, slow dependency, malformed dependency response, disconnect, quota exhaustion, or restart? |
| Observability/error handling | Are errors classified, bounded, non-sensitive, measurable, and actionable without exposing internals? |

Prioritize by expected impact multiplied by plausible exploit/failure likelihood. Prefer tests around money, permissions, irreversible side effects, tenant isolation, availability, data integrity, and high-amplification paths.

### Phase 3: Write contract and negative tests

For each external or public input boundary, construct cases from these classes where applicable:

- normal valid input;
- boundary-valid input;
- wrong type;
- missing required value;
- explicit null/none;
- empty string/list/map;
- malformed syntax or encoding;
- out-of-range numeric value;
- oversized string, collection, file, or request body;
- duplicate fields or duplicate identifiers;
- unexpected/unknown fields;
- inconsistent cross-field combinations;
- Unicode normalization, unusual whitespace, control characters, or locale-sensitive values where relevant;
- stale, future, expired, replayed, or version-mismatched tokens/messages;
- syntactically valid but semantically hostile values.

For rejection tests, assert more than an error code. Verify as applicable that:

- protected business logic was not reached;
- persistent state did not change;
- no external side effect occurred;
- no unauthorized information leaked;
- retries were not accidentally triggered;
- the failure remained within time and resource budgets;
- the error was stable and classifiable.

Prefer table-driven or parameterized tests when many cases share one behavioral contract. Keep individual failures easy to diagnose.

### Phase 4: Model authorization and business-logic abuse

Treat the client/UI as untrusted. Test the server/API directly.

For authorization-sensitive operations, vary:

- unauthenticated versus authenticated;
- owner versus non-owner;
- same tenant versus different tenant;
- low privilege versus elevated privilege;
- active versus disabled/expired accounts;
- object identifiers belonging to another actor;
- HTTP/RPC method, alternate route, bulk endpoint, export/import path, background job path, and internal-looking endpoints;
- client-controlled fields that should be server-derived, including price, role, tenant, ownership, status, discount, approval, quota, or completion flags;
- mass assignment / extra writable properties when the framework permits them.

Assert default-deny behavior. A request rejected by the UI but accepted by a direct backend request is a failed security boundary.

### Phase 5: Test workflows as state machines

Represent important multi-step workflows explicitly as states and transitions.

For a workflow such as `CREATED -> VERIFIED -> APPROVED -> EXECUTED`, test:

- every allowed transition;
- every security-relevant forbidden transition;
- direct invocation of later steps;
- skipping prerequisites;
- reordering requests;
- replaying previous requests or state identifiers;
- repeating a one-time action;
- cancellation/rollback after intermediate side effects;
- modification after approval/validation;
- concurrent execution of dependent steps;
- stale state or version values;
- retry after partial success.

Enforce state validation server-side. Do not trust client-provided status/phase fields as proof that prerequisites were completed.

### Phase 6: Define and test invariants with property-based testing

Use example tests for known cases and property-based tests for broad input/state spaces.

Look for:

- round trips: `decode(encode(x)) == x`;
- idempotence: applying an operation twice has the same effect where required;
- conservation: money, inventory, counts, or ownership do not appear/disappear unexpectedly;
- ordering/set properties: sorted output is ordered and preserves members;
- equivalence: optimized implementation matches a simple reference implementation;
- monotonicity: increasing an allowed limit/input changes output only in the expected direction;
- metamorphic relations: transforming input in a semantics-preserving way preserves the relevant output;
- authorization invariants: unauthorized actors never change protected state;
- crash freedom: valid-shaped inputs never crash the parser/compiler/service;
- sequence invariants: arbitrary valid operation sequences never violate state constraints.

Use shrinking/minimization so failures produce small, reproducible counterexamples. Persist valuable counterexamples as regression cases.

### Phase 7: Add fuzzing where structured unknown inputs matter

Prioritize fuzzing for parsers, codecs, serializers, protocol handlers, file processing, image/media processing, compression/decompression, regex engines, query languages, compilers, interpreters, network message handling, and complex API bodies.

A useful fuzz target should:

- accept arbitrary inputs without relying on the fuzzer to pre-validate them;
- be deterministic enough for reproducibility;
- execute quickly;
- avoid unnecessary global state;
- define clear bug oracles such as crash, sanitizer failure, assertion violation, timeout, excessive allocation, invariant violation, or differential mismatch;
- start from a small corpus containing representative valid and invalid inputs when structured input benefits from seeding;
- retain minimized crash/timeout/slow inputs in the regression corpus.

When native-code tooling supports it, combine coverage-guided fuzzing with memory/undefined-behavior sanitizers.

### Phase 8: Test single-request resource exhaustion

Do not treat denial of service only as "many requests." Test whether one or a few valid-looking requests can cause asymmetric resource consumption.

For each public entrypoint, identify attacker/user-controlled dimensions that scale work:

- request/payload/file size;
- string length;
- collection element count;
- nesting or recursion depth;
- pagination/page size;
- batch size;
- query/filter/sort/group complexity;
- regex/pathological text length;
- decompression or expansion ratio;
- graph/query depth and fan-out;
- database rows scanned, queries issued, joins, locks, or transactions held;
- number of downstream calls, emails, SMS, webhooks, model/API calls, or billable operations;
- number/duration of open connections, streams, sessions, workers, or file descriptors;
- retry count and retry amplification;
- queue messages or background jobs produced from one request.

Define explicit budgets where the architecture permits measurement, for example:

- maximum accepted input size;
- maximum collection/depth/page/batch limit;
- maximum execution time/timeout;
- maximum DB queries or scanned rows for a request class;
- maximum fan-out/downstream operations;
- maximum memory delta or allocation class;
- maximum concurrent resource occupancy;
- maximum retry count and total retry deadline.

Test values below, at, and above each enforced limit. Verify rejection is cheap and happens before expensive work when possible.

### Phase 9: Test concurrency, replay, and races

Create deterministic or repeatable concurrency tests for shared mutable state and security-sensitive time-of-check/time-of-use flows.

Target:

- double spending / duplicate charge;
- overselling inventory or quota;
- uniqueness races;
- duplicate job/message processing;
- idempotency-key races;
- optimistic-lock/version conflicts;
- lost updates;
- check-then-act authorization or filesystem races;
- concurrent workflow transitions;
- retry racing with original completion.

Assert invariants after all workers complete. Prefer barriers/latches/fakes/test clocks over arbitrary sleeps.

### Phase 10: Test dependency failures and resilience

Inject realistic failures at dependency boundaries:

- timeout and high latency;
- connection refusal/reset;
- malformed or incomplete response;
- 4xx/5xx or protocol error;
- partial success;
- stale/cache-miss behavior;
- quota/rate-limit response;
- dependency restart;
- queue duplication, delay, reordering, or redelivery;
- database deadlock or transient conflict;
- storage full / resource unavailable where safely testable.

Verify:

- bounded timeout/deadline propagation;
- retry only for appropriate failures;
- capped retries with jitter/backoff where expected;
- no retry storm or multiplicative fan-out;
- idempotent side effects;
- rollback/compensation or safe partial-state handling;
- circuit breaking/backpressure/load shedding where designed;
- graceful degradation rather than silent corruption;
- recovery after the dependency returns.

### Phase 11: Run performance tests at the correct layer

Separate performance workload types by purpose instead of using one generic load test.

- Smoke: validate the scenario/test script with minimal load.
- Average/load: establish normal baseline behavior.
- Stress: exercise above-normal/high expected load and observe degradation.
- Spike: apply sudden surges and test recovery.
- Soak: run sustained load long enough to expose leaks or cumulative degradation.
- Breakpoint/capacity: determine where the system stops meeting objectives; run only in a safe isolated environment.

Define pass/fail or analysis thresholds before execution where possible, such as latency percentiles, error rate, throughput, saturation, queue depth, connection-pool waiting, memory growth, restart count, and business-success rate.

Correlate client-side performance with server-side observability. A slow request without CPU/DB/queue traces is an incomplete diagnosis.

For risky load tests, define abort conditions before starting. Stop when continuing no longer yields useful information or risks collateral damage.

### Phase 12: Use mutation testing to evaluate assertion strength

Use mutation testing on important business, validation, authorization, and branching logic when tooling is available.

Pay special attention to surviving mutations that:

- invert or remove conditions;
- alter boundary comparisons;
- remove validation;
- change return values;
- bypass authorization branches;
- remove state checks;
- alter arithmetic affecting money/quota/counts;
- remove side-effect calls or exception handling.

Treat surviving meaningful mutations as evidence that the suite does not pin down the intended behavior strongly enough. Do not chase mutation score blindly when mutations are equivalent or irrelevant.

### Phase 13: Allocate tests to execution cadence

Use a default cadence like this, adapting to repository cost and risk:

| Cadence | Typical tests |
|---|---|
| Every local/PR run | unit, contract, negative, authorization regression, small property tests, deterministic concurrency regressions |
| PR or post-submit | integration/component, larger property suites, targeted mutation tests, schema/compatibility tests |
| Nightly/scheduled | longer fuzzing, broader mutation analysis, larger integration suites, baseline performance |
| Pre-release/staging | stress/spike, security abuse workflows, migration/upgrade, failure injection, recovery |
| Controlled production only | low-risk synthetic checks and explicitly authorized bounded experiments |

Keep expensive tests out of the fastest feedback loop unless their risk warrants the cost.

## Test implementation rules

When asked to modify a repository rather than only produce a plan:

1. Run or inspect the existing test suite first.
2. Follow the repository's existing framework, naming, fixtures, factories, and conventions unless they are clearly harmful.
3. Add the smallest test that exposes each missing behavior.
4. Prefer public APIs to private implementation details.
5. Avoid test logic that duplicates production algorithms; use simple oracles and invariants.
6. Prefer state/result assertions over brittle interaction assertions unless interaction is the actual contract.
7. Avoid arbitrary sleeps. Use controllable clocks, barriers, events, polling with deadlines, or deterministic scheduling.
8. Isolate external dependencies with realistic fakes for unit/component tests, then retain selected integration tests against real implementations for fidelity.
9. Make failure messages diagnostic. A failing adversarial test should identify the violated contract or invariant.
10. Re-run the relevant tests after changes. Report commands, failures, and remaining untested risk honestly.

## Tool selection guidance

Choose tools that match the existing language/ecosystem. Do not introduce a large testing framework solely because it appears here.

- Property-based testing: use a mature QuickCheck-family tool such as Hypothesis for Python when compatible.
- Native fuzzing: use coverage-guided tooling such as libFuzzer/compatible engines for suitable C/C++ targets; use ecosystem-native fuzzers elsewhere.
- Mutation testing: use ecosystem-appropriate tools such as PIT for JVM projects.
- Performance: use an existing project tool; k6 is a strong general option for HTTP/API workloads when no tool exists.
- Security verification: use OWASP ASVS as a requirements/checklist source and OWASP WSTG as a testing-technique source for web/API systems.
- Security corpora/tool validation: consult NIST SARD/Juliet when known-bad/known-good weakness examples are useful; do not mistake those corpora for application-specific regression suites.

Read `references/source-basis.md` when standards, rationale, or source material is needed.

## Required output when reviewing or testing a target

Unless the user requests another format, finish with a concise report containing:

### Test strategy
State the highest-risk behaviors, trust boundaries, invariants, and test layers selected.

### Coverage matrix
Summarize which risk dimensions are covered, missing, or not applicable. Do not report only line coverage.

### Tests added or proposed
For each important test, state the behavior/invariant, test layer, and why that layer is appropriate.

### Findings
For each defect or weakness, include:

- severity based on concrete impact;
- reproduction condition/input/sequence;
- observed versus expected behavior;
- affected invariant or security boundary;
- regression test status;
- recommended remediation direction without overclaiming.

### Resource and resilience assessment
Explicitly state whether resource budgets, concurrency, timeout/retry, and dependency-failure behavior were tested. If not, identify the gap.

### Commands and evidence
List relevant test commands, fuzz seeds/reproducers, performance scenarios, or mutation results actually executed. Distinguish executed evidence from recommendations.

### Remaining uncertainty
State what could not be verified because of missing environment, credentials, dependencies, production-like scale, nondeterminism, or unsafe execution conditions.

## Definition of done for critical functionality

Use this as a demanding default, not a universal checkbox. A critical feature is well tested when applicable items are supported by evidence:

- normal behavior is verified;
- boundary behavior is verified;
- malformed, wrong-type, missing, null, inconsistent, and oversized inputs fail safely;
- authorization cannot be bypassed by changing actor, tenant, identifier, route, method, or client-controlled protected fields;
- illegal state transitions, skipped steps, replay, and repeated one-time actions are rejected;
- concurrency does not violate core invariants;
- retry and duplicate delivery do not duplicate committed effects;
- property tests exercise broad input/sequence space for important invariants;
- fuzz targets cover high-risk parsers or structured-input surfaces where appropriate;
- single-request resource amplification has explicit limits or tests;
- normal and high-load behavior have measurable performance objectives where relevant;
- dependency failures are bounded and recover safely;
- errors do not disclose sensitive internals;
- meaningful mutations in critical logic are killed or consciously justified;
- discovered adversarial cases are retained as regression tests/corpus entries.

Do not claim comprehensive robustness when important applicable dimensions remain untested.
