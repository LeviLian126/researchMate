# Persistence Build

Use this guide for repository and data access mechanics: safe queries, transactions,
concurrency, schema evolution, and durable invariants. Read `slice-framing.md` first if you
have not framed the slice.

Node02 defines the data lifecycle, integrity rules, and evolution classification. This file
implements the mechanics. If a query shape, index, storage strategy, or consistency model
is not decided, return to Node02 with the specific question.

## Sections

- [Recover the Durable Contract](#recover-the-durable-contract)
- [Build Safe Queries](#build-safe-queries)
- [Anti-Pattern: N+1 and Over-Fetching](#anti-pattern-n1-and-over-fetching)
- [Make Invariants Durable](#make-invariants-durable)
- [Anti-Pattern: Missing Transaction Boundary](#anti-pattern-missing-transaction-boundary)
- [Schema and Data Evolution](#schema-and-data-evolution)

## Recover the Durable Contract

Node02 defines the data lifecycle and integrity rules. Before writing repository code,
confirm these five facts against the current contract and repo evidence:

1. **Owner**: which repository or store boundary already owns this data? Use the established
   boundary; do not create a parallel data access path.
2. **Identity**: what is the primary key, external ID, uniqueness rule, and duplicate
   behavior? Is there an idempotency key?
3. **Scope**: what tenant, owner, or account filter must appear in every query and mutation?
4. **Visibility**: which fields is the caller allowed to see? Return only those fields.
5. **Lifecycle**: what states, transitions, retention, and delete behavior are approved?

Do not make a repository return an unrestricted row because a current caller filters it
later. Data scope and field visibility must survive future callers.

## Build Safe Queries

Separate query mechanics from business policy, but ensure the repository receives the trusted
scope and authorized filter set. Bind values safely. Never interpolate raw input into a
query string.

### Owner/tenant bypass

```typescript
// safe: scope enforced in the query
const subs = await db.query(
  'SELECT id, state, period_end_date FROM subscriptions WHERE user_id = $1 AND tenant_id = $2',
  [userId, tenantId]
);

// unsafe: no scope filter, any caller can read any subscription
const subs = await db.query(
  'SELECT * FROM subscriptions WHERE id = $1',
  [req.params.id]
);
```

### Mass disclosure

```typescript
// safe: select only allowed fields, map through a response allowlist
const rows = await db.query(
  'SELECT id, state, period_end_date FROM subscriptions WHERE user_id = $1 LIMIT $2',
  [userId, limit]
);
return rows.map(toSubscriptionSummary);   // drops internal columns

// unsafe: SELECT * exposes internal columns (created_by, deleted_at, provider_internal_id)
const rows = await db.query('SELECT * FROM subscriptions WHERE user_id = $1', [userId]);
return rows;   // raw entities leak to the caller
```

### Unbounded collection

```typescript
// safe: pagination with a maximum limit
const limit = Math.min(requestedLimit ?? 20, 100);   // cap at 100
const rows = await db.query(
  'SELECT id, state FROM subscriptions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3',
  [userId, limit, (page - 1) * limit]
);

// unsafe: no limit, returns the entire table
const rows = await db.query('SELECT * FROM subscriptions WHERE user_id = $1', [userId]);
```

### Unsafe sort/filter

```typescript
// safe: map public token to a known column, use parameterized query
const SORT_COLUMNS = { created: 'created_at', name: 'name', updated: 'updated_at' };
const col = SORT_COLUMNS[sortToken] ?? 'created_at';
const rows = await db.query(
  `SELECT id, name FROM items WHERE tenant_id = $1 ORDER BY ${col} DESC LIMIT $2`,
  [tenantId, limit]
);   // col is from a fixed allowlist, not user input

// unsafe: interpolate raw user input
const rows = await db.query(
  `SELECT * FROM items WHERE tenant_id = $1 ORDER BY ${req.query.sort} DESC`,
  [tenantId]
);   // SQL injection via sort parameter
```

### Query in loop

```typescript
// safe: batch fetch
const orders = await orderRepo.findManyByUserIds(userIds);   // one query
// SELECT * FROM orders WHERE user_id = ANY($1)

// unsafe: N+1 -- one query per user
for (const user of users) {
  user.orders = await orderRepo.findByUserId(user.id);   // N queries
}
```

## Anti-Pattern: N+1 and Over-Fetching

LLMs frequently write N+1 queries when building related data. The query count grows
linearly with the collection size, turning a fast page into a slow one as users and data
grow.

```typescript
// N+1: fetches users, then one query per user for their orders
const users = await userRepo.findMany({ tenantId });
for (const user of users) {
  user.orders = await orderRepo.findByUserId(user.id);   // 1 + N queries
}

// batch: one query for users, one query for all their orders
const users = await userRepo.findMany({ tenantId });
const userIds = users.map(u => u.id);
const allOrders = await orderRepo.findManyByUserIds(userIds);   // 2 queries total
const ordersByUser = groupBy(allOrders, o => o.userId);
for (const user of users) {
  user.orders = ordersByUser[user.id] ?? [];
}
```

The batch version is 2 queries regardless of user count. The N+1 version is N+1 queries. At
100 users, that is 2 queries vs 101.

Over-fetching is the read-side equivalent: selecting all columns when only 3 are needed, or
returning full entities when the caller only needs a summary. Both waste bandwidth and
increase the surface for accidental data leaks.

## Make Invariants Durable

Use database or store mechanisms to make the approved invariant real. A pre-check in
application memory is not durable duplicate prevention or concurrency control.

### Multi-write invariant: transaction with rollback boundary

```typescript
async function transferCredits(fromId: string, toId: string, amount: number) {
  return await db.transaction(async (tx) => {
    const from = await tx.query('SELECT credits FROM accounts WHERE id = $1 FOR UPDATE', [fromId]);
    if (from.rows[0].credits < amount) throw new ConflictError('insufficient_credits');

    await tx.query('UPDATE accounts SET credits = credits - $1 WHERE id = $2', [amount, fromId]);
    await tx.query('UPDATE accounts SET credits = credits + $1 WHERE id = $2', [amount, toId]);
    await tx.query(
      'INSERT INTO transfers (from_id, to_id, amount, created_at) VALUES ($1, $2, $3, NOW())',
      [fromId, toId, amount]
    );
    // if any statement fails, the entire transaction rolls back
    // no partial state: credits are not deducted without being credited
  });
}
```

### Duplicate request: unique key or idempotency record

```typescript
async function cancelSubscription(id: string, requestId: string) {
  return await db.transaction(async (tx) => {
    // insert idempotency record first; if requestId exists, return prior result
    try {
      await tx.query(
        'INSERT INTO idempotency_keys (key, entity_type, entity_id) VALUES ($1, $2, $3)',
        [requestId, 'subscription_cancel', id]
      );
    } catch (e) {
      if (e.code === '23505') {   // unique constraint violation
        return await getIdempotentResult(tx, requestId);
      }
      throw e;
    }

    // proceed with the actual cancel
    const result = await doCancel(tx, id);
    await saveIdempotentResult(tx, requestId, result);
    return result;
  });
}
```

### Stale update: optimistic concurrency control

```typescript
// good: conditional update checks version, fails if stale
const result = await db.query(
  'UPDATE subscriptions SET state = $1, version = version + 1 WHERE id = $2 AND version = $3',
  ['cancelling', id, currentVersion]
);
if (result.rowCount === 0) {
  throw new ConflictError('stale_update');   // someone else modified it
}

// bad: blind overwrite, loses concurrent changes
await db.query('UPDATE subscriptions SET state = $1 WHERE id = $2', ['cancelling', id]);
```

### Job/webhook status: durable transition with dedupe

```typescript
async function handleWebhookEvent(event: WebhookEvent) {
  return await db.transaction(async (tx) => {
    // dedupe by event ID
    const existing = await tx.query(
      'SELECT status FROM webhook_events WHERE event_id = $1', [event.id]
    );
    if (existing.rows.length > 0) {
      return { status: existing.rows[0].status };   // already processed
    }

    // record the event with pending status
    await tx.query(
      'INSERT INTO webhook_events (event_id, type, status, received_at) VALUES ($1, $2, $3, NOW())',
      [event.id, event.type, 'processing']
    );

    // process the event...
    await tx.query(
      'UPDATE webhook_events SET status = $1, processed_at = NOW() WHERE event_id = $2',
      ['completed', event.id]
    );
    return { status: 'completed' };
  });
}
```

## Anti-Pattern: Missing Transaction Boundary

LLMs often write multi-step operations without a transaction, leaving the system in an
inconsistent state if one step fails.

```typescript
// bad: no transaction -- if the email enqueue fails, the subscription is half-cancelled
async function cancel(id: string, userId: string) {
  const sub = await repo.findById(id);
  sub.state = 'cancelling';
  await repo.save(sub);                        // step 1: state updated
  await emailQueue.enqueue({ ... });            // step 2: email queued (may fail)
  await billingAdapter.scheduleStop(id);        // step 3: billing stop (may fail)
  // if step 2 or 3 fails: state is 'cancelling' but no email sent, no billing stop
}

// good: transaction wraps the atomic parts; async work is queued inside the transaction
async function cancel(id: string, userId: string) {
  return await db.transaction(async (tx) => {
    const sub = await tx.subscriptions.findById(id);
    // ... checks ...
    sub.state = 'cancelling';
    sub.cancelsAt = sub.periodEndDate;
    await tx.subscriptions.save(sub, sub.version);    // atomic with idempotency record
    await tx.idempotency.mark(requestId, 'cancel', id);
    await tx.outbox.enqueue({ type: 'cancel_email', payload: { ... } });
    // all succeed or all roll back
    // the outbox pattern ensures the email is sent after commit, not lost if the app crashes
  });
}
```

### Callback arriving twice: check current state before applying

When a webhook or callback arrives, do not blindly apply it. Check the current durable
state first:

```typescript
async function handlePaymentCallback(callback: PaymentCallback) {
  return await db.transaction(async (tx) => {
    const payment = await tx.payments.findByExternalId(callback.payment_id);
    if (!payment) throw new NotFoundError('payment');

    // already processed? return current state
    if (payment.status === 'completed') {
      return { status: 'completed' };   // idempotent: do not re-process
    }

    // verify the callback is for this payment and is valid
    if (payment.amount !== callback.amount) {
      throw new ConflictError('amount_mismatch');   // do not process wrong amount
    }

    // transition to completed
    await tx.payments.update(payment.id, {
      status: 'completed',
      completed_at: new Date(),
      version: payment.version + 1,
    });

    return { status: 'completed' };
  });
}
```

## Schema and Data Evolution

Node02 classifies the evolution (additive, transforming, destructive, provider-state). This
file implements the mechanics. Follow the Node02 evolution record; do not replace it with a
generic migration script.

A typical additive migration: add a nullable column, backfill existing rows in batches, then
add the constraint. Each step is safe to run independently and resumable.

```sql
-- Step 1: add nullable column (additive, no downtime)
ALTER TABLE subscriptions ADD COLUMN cancellation_reason TEXT;

-- Step 2: backfill in batches (resumable, idempotent)
-- Each batch is small enough to not lock the table for long
-- Track progress so a failed batch can resume
UPDATE subscriptions
SET cancellation_reason = 'unknown'
WHERE id IN (
  SELECT id FROM subscriptions
  WHERE cancellation_reason IS NULL
  LIMIT 1000
);
-- repeat until no rows have NULL

-- Step 3: add constraint (only after all rows have a value)
ALTER TABLE subscriptions ALTER COLUMN cancellation_reason SET NOT NULL;
```

For each evolution step, state:
- **preflight**: existing rows, consumers, feature/config state, and required app permissions
- **compatibility**: old/new read/write behavior and mixed-version assumptions
- **backfill**: batch identity/order, bounded work, resumability, idempotency, progress evidence
- **validation**: dry-run, sample/count check, and expected success condition
- **repair**: safe rerun, forward-fix, manual owner, and evidence retained
- **removal**: condition that permits dropping the old field; Node06 executes it

For a new required field, decide how existing rows reach a valid value before adding the
enforcement constraint (steps 1-3 above). For a rename or type transform, preserve the
approved compatibility window. For large or unknown data, avoid a single unbounded write and
record the concrete lock/downtime/throughput risk for the release workflow.

Node03 may add migrations, safe preflight checks, dry-run modes, backfill code, repair
commands, fixtures, and local verification. Keep production migration execution, destructive
cleanup, and remote reconciliation in the Node06 release workflow.