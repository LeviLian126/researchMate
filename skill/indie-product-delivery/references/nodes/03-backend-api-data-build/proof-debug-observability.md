# Proof, Debug, and Observability

Use this guide to prove an implemented backend slice, debug failures from the real boundary,
add proportional observability, and prepare quality evidence without claiming release
readiness.

## Sections

- [Split Hermetic and Deployed Proof](#split-hermetic-and-deployed-proof)
- [Prove the Delivered Artifact](#prove-the-delivered-artifact)
- [Risk-Tiered Testing](#risk-tiered-testing)
- [Debug from Root Cause](#debug-from-root-cause)
- [Add Safe Observability](#add-safe-observability)
- [Verify Before Claiming Completion](#verify-before-claiming-completion)
- [Status Reporting](#status-reporting)

## Split Hermetic and Deployed Proof

Start from the Node02 contract and implementation spine. For each changed behavior, choose
the smallest proof that can demonstrate the actual boundary. Prefer the existing test
framework, fixtures, helpers, and commands.

A test is useful when it exercises production behavior through a meaningful boundary. Do
not test mocks, private implementation trivia, or test-only production seams instead of the
contract. A manual safe check is acceptable only when automation is absent or the proof
requires a real boundary; state its limit.

### Hermetic local proof: unit test through the real owner with an in-process fake

```typescript
describe('SubscriptionService.cancel', () => {
  let service: SubscriptionService;
  let fakeRepo: FakeSubscriptionRepo;
  let fakeEmail: FakeEmailQueue;
  let fakeBilling: FakeBillingAdapter;

  beforeEach(() => {
    fakeRepo = new FakeSubscriptionRepo([
      { id: 'sub_1', userId: 'user_1', state: 'active', periodEndDate: new Date('2025-12-31') },
    ]);
    fakeEmail = new FakeEmailQueue();
    fakeBilling = new FakeBillingAdapter();
    service = new SubscriptionService(fakeRepo, fakeEmail, fakeBilling);
  });

  it('cancels an active subscription', async () => {
    const result = await service.cancel('sub_1', 'user_1');

    expect(result.kind).toBe('ok');
    expect(result.cancelsAt.toISOString()).toBe('2025-12-31T00:00:00.000Z');
    expect(fakeRepo.saved.state).toBe('cancelling');
    expect(fakeEmail.enqueued).toHaveLength(1);
    expect(fakeBilling.scheduledCancellations).toContain('sub_1');
  });

  it('rejects cancel for another user subscription', async () => {
    const result = await service.cancel('sub_1', 'user_2');
    expect(result.kind).toBe('denied');
    expect(fakeRepo.saved).toBeNull();   // no state change
  });

  it('rejects cancel for already-cancelling subscription (idempotent)', async () => {
    fakeRepo.subscriptions[0].state = 'cancelling';
    const result = await service.cancel('sub_1', 'user_1');
    expect(result.kind).toBe('ok');         // returns current state
    expect(fakeEmail.enqueued).toHaveLength(0);   // no duplicate email
  });
});
```

This test exercises the real `SubscriptionService.cancel` method through its public
interface. Fakes stand in for external dependencies. No network, no database server, no
real provider. The test is fast, deterministic, and proves the domain logic.

### Deployed proof: integration check through the real boundary

When a behavior depends on a real database, provider, or queue, run an integration proof
against the authorized environment. Name the deployed commit, environment, safe data set,
protected dependencies, quota bound, and cleanup expectation.

```typescript
describe('Subscription cancellation integration', () => {
  // These tests require TEST_DATABASE_URL and STRIPE_TEST_KEY
  // Run: npm run test:integration

  it('persists cancellation state in the real database', async () => {
    const res = await request(app)
      .patch('/subscriptions/sub_test_1/cancel')
      .set('Authorization', `Bearer ${testToken}`)
      .expect(200);

    expect(res.body.status).toBe('cancelling');

    // verify durable state
    const row = await db.query('SELECT state FROM subscriptions WHERE id = $1', ['sub_test_1']);
    expect(row.rows[0].state).toBe('cancelling');

    // cleanup
    await db.query("UPDATE subscriptions SET state = 'active' WHERE id = $1", ['sub_test_1']);
  });
});
```

If the required environment is unavailable, keep the integration claim explicitly unverified
instead of inventing an equivalent environment. Do not weaken an explicit server-only rule
for convenience.

For repositories without a server-only integration policy, use the smallest authorized proof
environment and keep local infrastructure proportional.

## Prove the Delivered Artifact

For every deployable package, workspace member, executable, library, plugin, or service
artifact, reproduce the repository's locked restore/install and build path in a clean
environment. Then load the produced artifact through its real language/runtime mechanism.

- [ ] **Dependency resolution**: use the committed lock or immutable dependency mode. Reject
      an unrecorded re-resolution. (`npm ci` with `package-lock.json`, not `npm install`)
- [ ] **Package/build metadata**: confirm each intended deliverable is included by the build
      system, workspace, module, manifest, or package-discovery rules. (`ls dist/` or
      `npm pack --dry-run`)
- [ ] **Artifact creation**: run the same compile, bundle, package, or publish-dry-run path
      used by delivery when applicable. (`npm run build`, `tsc --noEmit`)
- [ ] **Loadability**: import, require, load, link, or execute every deployable artifact
      using the production runtime. (`node -e "require('./dist/index.js')"`)
- [ ] **Entrypoint**: invoke the declared command, module, handler, or service startup far
      enough to detect missing code or runtime dependencies. (`npm start` with a health
      check)
- [ ] **Platform/source selection**: keep architecture, registry/index/source, CPU/GPU,
      native-library, and toolchain choices explicit and reproducible.

A resolver or installer succeeding proves only the dependency operation it performed. It
does not prove that owned source entered the artifact, that the artifact can be loaded, or
that its entrypoint works. Keep local developer state, globally installed packages, prior
build output, and warm caches out of this proof.

When a clean proof is too expensive for every change, define a cheaper pull-request target
and retain the complete proof at the release or scheduled gate; label the cheaper result as
partial.

## Risk-Tiered Testing

For new or changed backend behavior, first express the expected behavior in the existing
test style. Run it and confirm that it fails for the expected missing behavior, then
implement the smallest change that passes.

### What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change
entirely; tests should not. A good test reads like a specification -- "user can cancel an
active subscription" tells you exactly what capability exists -- and survives refactors
because it does not care about internal structure.

### Three anti-patterns that produce useless tests

**Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies
through a side channel. The test breaks when you refactor but behavior has not changed.

```typescript
// bad: mocks the internal repository call, tests the mock not the behavior
it('cancels subscription', () => {
  const mockRepo = sinon.mock(subscriptionService['repo']);   // reaching into private field
  mockRepo.expects('save').once();
  // ... call cancel ...
  mockRepo.verify();
  // if you rename 'save' to 'update', this test breaks even though behavior is identical
});

// good: tests observable behavior through the public interface
it('cancels subscription', async () => {
  const result = await service.cancel('sub_1', 'user_1');
  expect(result.kind).toBe('ok');
  expect(result.cancelsAt).toBeDefined();
  // verifies the outcome, not the internal call sequence
});
```

**Tautological**: the assertion recomputes the expected value the same way the code does, so
it passes by construction and can never disagree.

```typescript
// bad: assertion uses the same logic as the implementation
it('calculates discount', () => {
  const cart = { items: [{ price: 10 }, { price: 20 }] };
  const result = calculateDiscount(cart);
  expect(result).toBe(cart.items.reduce((s, i) => s + i.price, 0) * 0.1);
  // if the implementation is wrong, the test is wrong the same way -- always passes
});

// good: expected value comes from an independent source (known-good literal)
it('calculates discount', () => {
  const cart = { items: [{ price: 10 }, { price: 20 }] };
  const result = calculateDiscount(cart);
  expect(result).toBe(3);   // 10% of 30 = 3, verified by hand
});
```

**Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify
imagined behavior -- the shape of things rather than user-facing behavior. Work in vertical
slices instead: one test, one implementation, repeat.

### Test at pre-agreed seams

A seam is the public boundary where you observe behavior without reaching inside. Tests live
at seams, never against internals. Before writing tests, identify the seams and confirm them.

For backend slices, the typical seams are:
- domain service public methods (unit tests with fakes)
- HTTP handler endpoints (integration tests with the real app)
- repository contracts (integration tests with a real or test database)

Do not test at a seam deeper than necessary. If the domain service has a clean interface,
test there -- do not also test the private helpers it calls.

### The red-green loop

- **Red**: write a failing test that describes the behavior you want. Run it. Confirm it
  fails for the right reason (missing behavior, not a syntax error).
- **Green**: write the smallest implementation that makes the test pass. Do not anticipate
  future tests or add speculative features.
- **Repeat**: one test, one implementation per cycle. Each test is a tracer bullet that
  responds to what the last cycle taught you.

Refactoring is not part of the loop. It belongs to a separate review step.

### Coverage guidance

Cover the core business behavior changed by the slice. The goal is confidence in the
decisions and state transitions that matter to users and data, not an aggregate number.

Prioritize: domain rules, authorization decisions, state transitions, failure handling,
idempotency, money/quota logic, and changed branches. Do not add tests for trivial glue,
generated code, styling, or simple pass-throughs merely to increase a percentage.

When an existing repository has a coverage baseline, a bounded change should not reduce it
and must cover the core behavior it changes. Raise a broader deficit only during a quality
or test-hardening task.

## Debug from Root Cause

When behavior, test, migration, provider, or performance evidence fails, do not stack fixes.
Follow this six-phase workflow. Skip phases only when explicitly justified.

### Phase 1: Build a tight feedback loop

This is the skill. Everything else is mechanical. If you have a tight pass/fail signal for
the bug -- one that goes red on this bug -- you will find the cause. If you do not, no amount
of staring at code will save you.

Build a feedback loop. Try these in roughly this order:

1. **Failing test** at whatever seam reaches the bug -- unit, integration, e2e.
2. **curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) -- drives the UI, asserts on
   DOM/console/network.
5. **Replay a captured trace** -- save a real network request, payload, or event log; replay
   it through the code path in isolation.
6. **Throwaway harness** -- spin up a minimal subset (one service, mocked deps) that
   exercises the bug code path with a single function call.
7. **Property / fuzz loop** -- if the bug is "sometimes wrong output", run 1000 random inputs
   and look for the failure mode.
8. **Bisection harness** -- if the bug appeared between two known states (commit, dataset,
   version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop** -- run the same input through old-version vs new-version and diff
   outputs.
10. **HITL bash script** -- last resort. If a human must click, drive them with a structured
    script so the loop is still controlled.

Phase 1 is done when you can name one command -- a script path, a test invocation, a curl --
that you have already run at least once, and that is:

- [ ] **Red-capable** -- it drives the actual bug code path and asserts the user's exact
      symptom. Not "runs without erroring" -- it must be able to catch this specific bug.
- [ ] **Deterministic** -- same verdict every run (flaky bugs: a pinned, high reproduction
      rate).
- [ ] **Fast** -- seconds, not minutes.
- [ ] **Agent-runnable** -- you can run it unattended.

If you catch yourself reading code to build a theory before this command exists, stop. No
red-capable command, no Phase 2.

### Phase 2: Reproduce and minimize

Run the loop. Watch it go red. Confirm:

- [ ] The loop produces the failure mode the user described -- not a different failure nearby.
- [ ] The failure is reproducible across multiple runs.
- [ ] You have captured the exact symptom (error message, wrong output, slow timing).

Then minimize: shrink the repro to the smallest scenario that still goes red. Cut inputs,
callers, config, data, and steps one at a time, re-running the loop after each cut. Keep
only what is load-bearing for the failure. Done when every remaining element is
load-bearing -- removing any one makes the loop go green.

### Phase 3: Hypothesize

Generate 3-5 ranked hypotheses before testing any of them. Single-hypothesis generation
anchors on the first plausible idea.

Each hypothesis must be falsifiable:

> "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will
> make it worse."

If you cannot state the prediction, the hypothesis is a vibe -- discard or sharpen it.

Show the ranked list to the user before testing. They often have domain knowledge that
re-ranks instantly. Do not block on it -- proceed with your ranking if the user is away.

### Phase 4: Instrument

Each probe must map to a specific prediction from Phase 3. Change one variable at a time.

Tool preference: debugger or REPL inspection if the environment supports it. One breakpoint
beats ten logs. If logs are necessary, use targeted logs at the boundaries that distinguish
hypotheses. Never "log everything and grep."

Tag every debug log with a unique prefix:

```typescript
console.log('[DEBUG-a4f2] subscription state before cancel:', sub.state);
console.log('[DEBUG-a4f2] billing result:', billingResult);
console.log('[DEBUG-a4f2] email queue length:', fakeEmail.enqueued.length);
```

Cleanup at the end becomes a single grep: `grep '[DEBUG-' src/`. Untagged logs survive;
tagged logs die.

For performance regressions, logs are usually wrong. Instead: establish a baseline
measurement (timing harness, `performance.now()`, profiler, query plan), then bisect.
Measure first, fix second.

### Phase 5: Fix and regression test

Write the regression test before the fix -- but only if there is a correct seam for it. A
correct seam is one where the test exercises the real bug pattern as it occurs at the call
site. If the only available seam is too shallow, a regression test there gives false
confidence. If no correct seam exists, that itself is the finding -- note it, the codebase
architecture is preventing the bug from being locked down.

If a correct seam exists:

1. Turn the minimized repro into a failing test at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimized) scenario.

### Phase 6: Cleanup and post-mortem

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] Regression test passes (or absence of seam is documented).
- [ ] All `[DEBUG-...]` instrumentation removed (`grep '[DEBUG-' src/`).
- [ ] Throwaway prototypes deleted or moved to a clearly-marked debug location.
- [ ] The hypothesis that turned out correct is stated in the commit or PR message.

Then ask: what would have prevented this bug? If the answer involves architectural change
(no good test seam, tangled callers, hidden coupling), flag it for Node02.

### Keep a hypothesis ledger during difficult debugging

```
Observation:       cancel returns 500 for subscription sub_1 but 200 for sub_2
Proposed cause:    sub_1 has state 'past_due', transition rule missing
Discriminating
  check:           add 'past_due' to ALLOWED_TRANSITIONS, re-run test
Result:            test passes -- hypothesis confirmed
Next conclusion:   add 'past_due' -> 'cancelling' transition, add test for past_due cancel
```

Run the cheapest check that can separate competing causes. Add temporary instrumentation
only where it changes the diagnosis, then remove it or convert it into intentional
observability before handoff.

### When to stop local patching

Stop when another attempt would add no new evidence. If the evidence reveals shared state,
cross-module coupling, incompatible runtime assumptions, or repeated new symptoms, return to
Node02 with that evidence rather than continuing speculative fixes.

## Add Safe Observability

Add only the diagnostics needed to understand the changed lifecycle in operation.
Observability must preserve the access and privacy contract; it is not a reason to log
payloads, secrets, tokens, raw provider responses, or private identifiers.

### Safe structured log

```typescript
// safe: correlation ID, outcome class, retryability, elapsed time -- no secrets
logger.info('subscription_cancelled', {
  correlation_id: requestId,
  subscription_id: sub.id,        // safe: internal ID, not customer data
  outcome: 'ok',
  previous_state: 'active',
  new_state: 'cancelling',
  retryable: false,
  elapsed_ms: Date.now() - startTime,
  billing_provider_ref: billingResult.providerRef,
});
```

### Unsafe log

```typescript
// unsafe: logs request body, auth token, raw provider response
logger.info('cancel_request', {
  body: req.body,                 // may contain PII or user content
  auth_token: req.headers.authorization,   // credential leak
  stripe_response: rawStripeResponse,      // may contain customer data
  user_email: sub.email,                   // PII
});
```

Add a correlation ID when a request, job, callback, provider, or multi-write path crosses
boundaries. Add a structured outcome when domain, provider, or migration behavior has
meaningful failure classes. Add a state transition log when async, migration, reconciliation,
or recovery changes durable status. Add performance measurement when a list, search, export,
fanout, or query path may grow.

Check changed data paths for N+1 query loops, unbounded collections, missing query bounds,
excessive provider fanout, blocking work in request paths, and repeated serialization
lookups. Fix a clear local implementation defect; return capacity, storage, queue, caching,
or architecture choices to Node02.

## Verify Before Claiming Completion

A completion claim requires fresh evidence from the current worktree. Identify the specific
command or safe observation that proves each claim, run it, read its full result and exit
code, then report only what the evidence establishes.

- [ ] **Targeted behavior works**: relevant test or reproduction command shows expected
      result. (`npm test -- --grep 'cancel'`)
- [ ] **No regression in scope**: affected existing test or characterization proof passes.
      (`npm test`)
- [ ] **Migration mechanism is ready**: hermetic file or preflight proof plus any required
      deployed migration evidence meets the stated condition. (`npm run migrate:up --dry-run`)
- [ ] **Provider contract is safe**: network-free fake or fixture proves signature, mapping,
      failure, or dedupe behavior. (provider-adapter unit test passes)
- [ ] **Refactor preserved behavior**: locked baseline evidence before and after, or focused
      characterization proof. (run characterization tests before and after the change)
- [ ] **Docs reflect current truth**: affected module, API, or backend state page was updated
      or consciously not needed.

Do not report DONE because code looks plausible, a partial command passed, or an agent
reported success. State unverified remote, production, load, browser, security, or release
facts as named gaps and route them to their owner.

## Status Reporting

Set one implementation status based on the evidence:

**`BUILT`** -- Requested implementation and required hermetic proof are complete. Named gaps
in deployed or environment evidence are listed but do not block the implementation claim.
Example: "cancel subscription implemented, unit tests pass, integration test pending TEST_DATABASE_URL."

**`BLOCKED`** -- A required implementation fact, safe proof, credential, or environment is
unavailable. State what is missing and what was attempted. Example: "BLOCKED: Stripe test
key unavailable, cannot verify webhook signature handling. Attempted: searched .env files,
no key found. Need: STRIPE_TEST_KEY or deployment to staging with webhook configured."

**`NEEDS_CONTRACT`** -- A contract, boundary, runtime, compatibility, or recovery design must
change before implementation can proceed correctly. State what must change and route to
Node02. Example: "NEEDS_CONTRACT: billing provider has no 'cancel at period end' API. Must
decide: cancel immediately and refund prorated amount, or keep subscription active until
period end without provider involvement. Route to Node02."

Do not issue a quality or ship verdict from Node03. Route quality or security judgment to
Node05, and release execution to Node06.