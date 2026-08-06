# Domain Build

Use this guide to place business behavior in the correct owner and implement domain logic:
use-case ownership, state transitions, policy enforcement, and side-effect coordination.
Read `slice-framing.md` first if you have not framed the slice.

Node02 defines the contracts (state machine, invariants, failure behavior). This file
implements them. If a new state, fee rule, public error, recovery action, or compatibility
behavior is needed that Node02 did not define, stop -- that is a system decision, not an
implementation default.

## Sections

- [Locate the Use-Case Owner](#locate-the-use-case-owner)
- [Write the Executable Use-Case Path](#write-the-executable-use-case-path)
- [Keep Policy, State, and Side Effects Coherent](#keep-policy-state-and-side-effects-coherent)
- [Anti-Pattern: Over-Abstraction](#anti-pattern-over-abstraction)
- [Anti-Pattern: Transport Logic in Domain](#anti-pattern-transport-logic-in-domain)
- [Refactor with a Locked Baseline](#refactor-with-a-locked-baseline)

## Locate the Use-Case Owner

Start from the implementation spine and identify the module that already owns the business
outcome. Prefer extending an existing service or domain module over creating a new one. A
controller, CLI command, or webhook handler may translate transport into intent, but it must
not become the home for a reusable business rule.

### Good: domain service owns the rule, controller translates transport

```typescript
// controller -- thin: parse, authenticate, call domain, map result
async function cancelSubscription(req: Request, res: Response) {
  const userId = req.auth.userId;           // trusted, from middleware
  const subId = req.params.id;
  const result = await subscriptionService.cancel(subId, userId);
  res.status(200).json(mapToResponse(result));
}

// domain service -- owns the business rule
class SubscriptionService {
  async cancel(subscriptionId: string, userId: string): Promise<CancelResult> {
    const sub = await this.repo.findById(subscriptionId);
    if (!sub) return { kind: 'not_found' };
    if (sub.userId !== userId) return { kind: 'denied' };
    if (sub.state !== 'active') return { kind: 'conflict', currentState: sub.state };

    sub.state = 'cancelling';
    sub.cancelsAt = sub.periodEndDate;
    await this.repo.save(sub);
    await this.emailQueue.enqueue({ to: sub.email, template: 'cancel-confirm' });

    return { kind: 'ok', cancelsAt: sub.cancelsAt };
  }
}
```

The controller does not know what "active" means or that email is sent. The domain service
does not know about HTTP. Each has one reason to change.

### Bad: business logic in the controller

```typescript
// controller -- has become the domain owner (bad)
async function cancelSubscription(req: Request, res: Response) {
  const sub = await db.subscriptions.findById(req.params.id);
  if (!sub) { res.status(404).json({ error: 'not found' }); return; }
  if (sub.userId !== req.auth.userId) { res.status(403).json({ error: 'forbidden' }); return; }
  if (sub.state !== 'active') { res.status(409).json({ error: 'conflict' }); return; }

  sub.state = 'cancelling';
  sub.cancelsAt = sub.periodEndDate;
  await db.subscriptions.save(sub);
  await sendEmail(sub.email, 'cancel-confirm');   // direct provider call

  res.status(200).json({ status: sub.state, cancelsAt: sub.cancelsAt });
}
```

Problems: the business rule (state transition, idempotency, email trigger) is buried in
transport code. It cannot be tested without HTTP. A second entry point (CLI, webhook) would
duplicate the entire rule. The provider call (`sendEmail`) is not behind an adapter.

### When to create a new service vs extend an existing one

A new service is justified when it owns a distinct invariant that no existing module covers.
Do not create a service to hide a one-line policy already owned by a nearby module. The
signal is ownership, not architecture aesthetics.

## Write the Executable Use-Case Path

Write the intended path in outcome language before changing implementation. This is the
implementation map for the state and failure behavior Node02 has already chosen:

```
validated intent -> policy and invariant -> state decision -> durable change
  or external request -> domain result -> boundary-specific response
```

Name every branch whose behavior is meaningful. When a result could be success, accepted/
pending, no-op duplicate, conflict, validation failure, denied, temporary failure, or
recovery-required, preserve the distinction. Collapsing all exceptions into a generic
failure erases the contract.

```typescript
type CancelResult =
  | { kind: 'ok'; cancelsAt: Date }
  | { kind: 'not_found' }
  | { kind: 'denied' }
  | { kind: 'conflict'; currentState: string }
  | { kind: 'provider_error'; retryable: boolean; correlationId: string };
```

Every caller of `cancel()` must handle each variant. This forces the interface layer to
map each outcome to a distinct, stable response rather than returning 500 for everything.

## Keep Policy, State, and Side Effects Coherent

Implement policy in the owner that can see the relevant trusted facts. Use existing
repositories and adapters through their contracts; do not reach around them.

### Authorization: consume the server-side decision

The domain layer receives already-authenticated identity from the interface layer. It
enforces ownership by comparing trusted state, never by trusting caller-provided values.

```typescript
// good: ownership checked from trusted state
const sub = await this.repo.findById(subscriptionId);
if (sub.userId !== userId) return { kind: 'denied' };   // userId from auth, not request body

// bad: trusts caller-provided owner
const sub = await this.repo.findById(req.body.subscriptionId);
if (sub.orgId === req.body.orgId) proceed();             // req.body.orgId is untrusted
```

### State transition: verify before write

Allow only contracted source-to-target transitions. A pre-check in application memory is not
durable concurrency control -- see `persistence-build.md` for the durable mechanism. But the
domain layer must express the rule:

```typescript
const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  active: ['cancelling', 'past_due'],
  cancelling: ['cancelled'],
  past_due: ['cancelling', 'cancelled'],
  cancelled: [],   // terminal
};

function canTransition(from: string, to: string): boolean {
  return ALLOWED_TRANSITIONS[from]?.includes(to) ?? false;
}
```

### Idempotency: coordinate duplicate identity

If the same cancel request arrives twice, the second call must not send a second email or
schedule a second billing stop. Use a durable idempotency key (see `persistence-build.md`).
In the domain layer, check current state first:

```typescript
// if already cancelling, return current state -- do not re-process
if (sub.state === 'cancelling') {
  return { kind: 'ok', cancelsAt: sub.cancelsAt };   // idempotent success
}
```

### Transaction: be explicit about what is atomic

Group domain changes that must succeed or fail together. Delegate mechanics to the
persistence layer, but be explicit in the domain method about what is atomic and what is
eventually reconciled.

```typescript
async cancel(subscriptionId: string, userId: string): Promise<CancelResult> {
  return await this.tx.run(async (tx) => {
    // atomic: state update + idempotency record must succeed together
    const sub = await tx.subscriptions.findById(subscriptionId);
    // ... checks ...
    sub.state = 'cancelling';
    await tx.subscriptions.save(sub, sub.version);   // optimistic lock
    await tx.idempotency.mark(requestId, 'cancel', sub.id);

    // eventually consistent: email is queued, not sent inline
    await this.emailQueue.enqueue({ to: sub.email, template: 'cancel-confirm' });

    return { kind: 'ok', cancelsAt: sub.cancelsAt };
  });
}
```

If the system cannot explain what is atomic and what is eventually reconciled, return to
Node02 rather than approximating consistency.

### External request: durable intent before the call

Create the approved durable intent or status before making the external request. If the
provider call fails, the system has a record of what should have happened and can retry or
reconcile.

```typescript
// good: record intent, then call provider
await tx.refunds.insert({ subscriptionId, amount, status: 'pending' });
const result = await this.billingAdapter.requestRefund(subscriptionId, amount);
await tx.refunds.update(subscriptionId, { status: result.ok ? 'completed' : 'failed' });

// bad: call provider first, hope the write succeeds
const result = await this.billingAdapter.requestRefund(subscriptionId, amount);
await tx.refunds.insert({ subscriptionId, amount, status: result.ok ? 'completed' : 'failed' });
// if the insert fails, the refund happened but no local record exists
```

## Anti-Pattern: Over-Abstraction

LLMs frequently create abstractions that have only one implementation: an
`AbstractRepository<T>` never subclassed, a `ProviderFactory` with one provider, a generic
`Manager` wrapping a single service. These add indirection without leverage.

### The deletion test

Apply this before adding an abstraction: imagine deleting it. If complexity vanishes, it was
a pass-through. If complexity reappears across N callers, it was earning its keep.

### One adapter means a hypothetical seam. Two adapters means a real one.

Do not introduce a port or interface unless at least two adapters are justified (typically
production + test). A single-adapter seam is just indirection.

```typescript
// over-abstracted: one implementation, no second adapter in sight
interface ISubscriptionRepository {
  findById(id: string): Promise<Subscription | null>;
  save(sub: Subscription): Promise<void>;
}
class SubscriptionRepositoryImpl implements ISubscriptionRepository { /* ... */ }
// The interface adds a layer of indirection with zero leverage.
// Tests can mock the concrete class directly.

// direct: same behavior, less ceremony
class SubscriptionRepository {
  findById(id: string): Promise<Subscription | null> { /* ... */ }
  save(sub: Subscription): Promise<void> { /* ... */ }
}
// When a second implementation appears (e.g., a test double or a different storage),
// extract the interface then. Not before.
```

When you do need a seam (two real adapters), define the interface at the boundary and inject
it. See `provider-async-build.md` for the adapter pattern.

## Anti-Pattern: Transport Logic in Domain

Domain services must not return HTTP status codes, know about JSON, or import framework
types. Transport concerns belong in the interface layer.

```typescript
// bad: domain returns HTTP status
class SubscriptionService {
  async cancel(id: string, userId: string) {
    const sub = await this.repo.findById(id);
    if (!sub) throw new HttpError(404, 'not found');         // HTTP leak
    if (sub.userId !== userId) throw new HttpError(403);     // HTTP leak
    // ...
  }
}

// good: domain returns domain result, interface maps to HTTP
class SubscriptionService {
  async cancel(id: string, userId: string): Promise<CancelResult> {
    const sub = await this.repo.findById(id);
    if (!sub) return { kind: 'not_found' };                  // domain language
    if (sub.userId !== userId) return { kind: 'denied' };    // domain language
    // ...
  }
}
// The interface layer (see interface-build.md) maps CancelResult to HTTP:
//   not_found -> 404, denied -> 403, conflict -> 409, ok -> 200
```

This separation lets the same domain logic serve HTTP, CLI, webhook, and test callers
without duplication.

## Refactor with a Locked Baseline

Before a backend refactor, list the behaviors that must remain unchanged. Run existing tests
before and after the focused change. If no suitable test exists, create a minimal
characterization test first.

Behaviors to preserve across a refactor:

- public entry path (route, CLI command, event handler)
- field and response shape (public API contract)
- authentication and authorization behavior
- state transition outcomes
- schema semantics
- provider request and error behavior
- job trigger behavior
- observability and recovery signals

If a refactor makes it impossible to preserve one of these, that is a contract change, not
a refactor. Return to Node02 with evidence.

Unrelated debt discovered during the refactor should be left named but untouched unless it
blocks the slice. Do not turn a focused change into a repository-wide cleanup.