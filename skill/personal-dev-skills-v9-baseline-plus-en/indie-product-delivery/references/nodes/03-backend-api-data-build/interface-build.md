# Interface Build

Use this guide to implement HTTP, CLI, event, or webhook entry boundaries: input validation,
identity enforcement, stable result and error mapping. Read `slice-framing.md` first if you
have not framed the slice.

Node02 defines the interface contract (fields, auth, errors, evolution). This file
implements it. Do not alter status codes, public field names, error shape, pagination
behavior, authentication requirement, timing, or idempotency semantics because an
implementation shortcut is convenient -- those are contract changes requiring Node02.

## Sections

- [Recover the Interface Contract](#recover-the-interface-contract)
- [Normalize and Validate at the Untrusted Boundary](#normalize-and-validate-at-the-untrusted-boundary)
- [Enforce Identity and Access at the Server](#enforce-identity-and-access-at-the-server)
- [Map Stable Results and Failures](#map-stable-results-and-failures)
- [Anti-Pattern: Silent Error Swallowing](#anti-pattern-silent-error-swallowing)
- [Query-Facing Interface Behavior](#query-facing-interface-behavior)

## Recover the Interface Contract

For every changed entry, capture the contract fields and implement them in the handler. Use
the existing route or action pattern unless Node02 explicitly approved a new surface.

A complete handler shows every contract field in code:

```typescript
// PATCH /subscriptions/:id/cancel
// Contract:
//   caller:     authenticated user (auth middleware sets req.auth)
//   input:      path param :id, optional body { reason?: string }
//   identity:   session token verified by auth middleware -> req.auth.userId
//   scope:      user must own the subscription (checked in domain layer)
//   success:    200 { status: 'cancelling', cancelsAt: string }
//   errors:     400 validation, 401 unauthenticated, 403 denied, 404 not_found,
//               409 conflict, 502 provider_error, 500 internal
//   compat:     additive (new endpoint, no existing consumers)
//   proof:      behavior test through SubscriptionService with in-process fake

async function cancelSubscription(req: AuthedRequest, res: Response) {
  // 1. validate input shape
  const id = req.params.id;
  if (!id || typeof id !== 'string') {
    return res.status(400).json({ error: 'invalid_id' });
  }
  const reason = req.body?.reason;
  if (reason !== undefined && typeof reason !== 'string') {
    return res.status(400).json({ error: 'invalid_reason' });
  }

  // 2. trusted identity (from middleware, not request body)
  const userId = req.auth.userId;

  // 3. call domain (ownership checked inside)
  const result = await subscriptionService.cancel(id, userId, { reason });

  // 4. map domain result to stable HTTP response
  mapCancelResult(res, result);
}

function mapCancelResult(res: Response, result: CancelResult) {
  switch (result.kind) {
    case 'ok':
      res.status(200).json({ status: 'cancelling', cancelsAt: result.cancelsAt.toISOString() });
      break;
    case 'not_found':
      res.status(404).json({ error: 'not_found' });
      break;
    case 'denied':
      res.status(403).json({ error: 'denied' });
      break;
    case 'conflict':
      res.status(409).json({ error: 'conflict', current_state: result.currentState });
      break;
    case 'provider_error':
      res.status(502).json({
        error: 'provider_error',
        retryable: result.retryable,
        correlation_id: result.correlationId,
      });
      break;
  }
}
```

The handler does not contain business rules. It parses, validates shape, invokes the domain
use case, and maps the result.

## Normalize and Validate at the Untrusted Boundary

Treat request bodies, query/path values, cookies, headers, CLI args, webhook payloads,
uploads, model output, and imported files as untrusted until a boundary validates them.
Validation prevents malformed intent; it does not decide whether the actor is allowed.

### Shape validation

Validate type, required/optional fields, nested shape, and size before the value reaches
domain logic.

```typescript
function parseCancelBody(body: unknown): { reason?: string } | { error: string } {
  if (body === undefined || body === null) return {};
  if (typeof body !== 'object') return { error: 'body_must_be_object' };
  const b = body as Record<string, unknown>;
  if (b.reason !== undefined && typeof b.reason !== 'string') {
    return { error: 'reason_must_be_string' };
  }
  if (typeof b.reason === 'string' && b.reason.length > 500) {
    return { error: 'reason_too_long' };
  }
  return { reason: b.reason };
}
```

### Allowlist: accept only client-settable fields

Reject or ignore unknown fields as contracted. Never pass the raw request body directly to
a domain method or repository.

```typescript
// good: explicit allowlist
const ALLOWED_FIELDS = ['reason'] as const;
function sanitizeCancelBody(body: Record<string, unknown>) {
  const picked: Record<string, unknown> = {};
  for (const key of ALLOWED_FIELDS) {
    if (key in body) picked[key] = body[key];
  }
  return picked;
}

// bad: spreads entire body, lets caller set server-owned fields
const subscription = { ...req.body, userId: req.auth.userId };
await repo.save(subscription);
// caller can override userId, price, state, or any column by including it in the body
```

### Server-owned values: derive from trusted state

Owner, tenant, role, price, quota, entitlement, provider ID, timestamp, and controlled state
must be derived from server-side trusted state, never from request input.

```typescript
// good: price and plan come from server-side lookup
const plan = await planRepo.findById(subscription.planId);
const amount = plan.price;   // server-side, trusted

// bad: price comes from request body
const amount = req.body.price;   // untrusted, caller can set any price
```

### Dynamic query: allowlist sort and filter tokens

When the client controls sort or filter expressions, map public tokens to known columns and
operators. Never interpolate raw input into a query string.

```typescript
const SORT_COLUMNS: Record<string, string> = {
  created: 'created_at',
  updated: 'updated_at',
  name: 'name',
};

function resolveSort(sortParam: string | undefined): { column: string; dir: 'asc' | 'desc' } {
  if (!sortParam) return { column: 'created_at', dir: 'desc' };   // safe default
  const [token, dir] = sortParam.split(':');
  const column = SORT_COLUMNS[token];
  if (!column) throw new ValidationError('invalid_sort_field');
  if (dir !== 'asc' && dir !== 'desc') throw new ValidationError('invalid_sort_dir');
  return { column, dir };
}
// Use parameterized queries with the resolved column -- see persistence-build.md
```

### Normalization

Trim or canonicalize only when the contract allows and when it preserves meaningful
distinctions. Do not silently normalize away differences that carry meaning.

```typescript
// safe: email is case-insensitive by convention
const email = req.body.email.trim().toLowerCase();

// unsafe: trimming a code that may have leading zeros or significant whitespace
const code = req.body.code.trim();   // '  007' becomes '007' -- may break validation
```

## Enforce Identity and Access at the Server

Implement the Node02 trust chain at the actual enforcement point:

```
subject -> resource -> action -> scope -> enforcement -> safe failure -> evidence
```

Authenticate before protected access. Resolve resource scope from trusted identity and
server-side lookup, then authorize before read, mutation, export, provider action, or
private-field disclosure. A UI guard, caller-provided owner ID, or hidden route is not an
enforcement point.

### Tenant-scoped query: safe vs unsafe

```typescript
// safe: tenant scope comes from authenticated session, applied in the query
async function listSubscriptions(userId: string, tenantId: string) {
  return await db.subscriptions.findMany({
    where: { userId, tenantId },   // scope enforced in the data query
    limit: 50,
  });
}

// unsafe: trusts caller-provided tenant_id, no server-side verification
async function listSubscriptions(req: Request) {
  return await db.subscriptions.findMany({
    where: { tenant_id: req.query.tenant_id },   // untrusted, bypasses scope
  });
}
```

### Absent vs denied: preserve privacy

When a user requests a resource they do not own, return the same response as if the resource
did not exist. Do not leak existence.

```typescript
// good: 404 for both "not found" and "found but not yours"
case 'not_found':
case 'denied':
  res.status(404).json({ error: 'not_found' });   // same response for both
  break;

// bad: 403 reveals the resource exists
case 'denied':
  res.status(403).json({ error: 'forbidden' });   // caller learns the resource exists
  break;
```

Exception: when the contract explicitly requires a 403 (e.g., admin operations), follow the
contract. This is a Node02 decision, not an implementation default.

## Map Stable Results and Failures

Convert domain results into the current public representation in one established place. Keep
transport formatting out of domain services and provider adapters.

```typescript
// central error mapper -- one place for the entire module
function mapDomainError(res: Response, error: DomainError) {
  const MAPPINGS: Record<string, { status: number; body: (e: DomainError) => object }> = {
    validation:   { status: 400, body: e => ({ error: 'validation', field: e.field, message: e.message }) },
    unauthenticated: { status: 401, body: () => ({ error: 'unauthenticated' }) },
    denied:       { status: 403, body: () => ({ error: 'denied' }) },
    not_found:    { status: 404, body: () => ({ error: 'not_found' }) },
    conflict:     { status: 409, body: e => ({ error: 'conflict', current_state: e.currentState }) },
    provider_error: { status: 502, body: e => ({ error: 'provider_error', retryable: e.retryable, correlation_id: e.correlationId }) },
    internal:     { status: 500, body: () => ({ error: 'internal' }) },   // no stack, no SQL, no internals
  };

  const mapping = MAPPINGS[error.kind] ?? MAPPINGS.internal;
  res.status(mapping.status).json(mapping.body(error));
}
```

Every error response communicates what happened, why, and how to fix or safely recover --
without exposing internal details. The internal error case returns a generic message; the
real diagnostic goes to logs, not to the caller.

## Anti-Pattern: Silent Error Swallowing

LLMs frequently collapse distinct failure modes into a single catch-all, hiding the actual
problem from the caller and from debugging.

```typescript
// bad: swallows everything, caller gets 500 for all failure types
async function cancelSubscription(req: Request, res: Response) {
  try {
    const result = await subscriptionService.cancel(req.params.id, req.auth.userId);
    res.status(200).json(result);
  } catch (e) {
    res.status(500).json({ error: 'something went wrong' });
    // validation error, auth failure, conflict, provider timeout -- all become 500
    // caller cannot distinguish "bad input" from "server is broken"
    // logs may not capture the real error type
  }
}

// worse: returns null, caller has no idea what happened
async function cancelSubscription(req: Request, res: Response) {
  try {
    const result = await subscriptionService.cancel(req.params.id, req.auth.userId);
    res.status(200).json(result);
  } catch (e) {
    res.status(200).json({ error: null });   // looks like success, hides failure
  }
}
```

The fix: domain methods return typed results (not throws for expected outcomes), and the
handler maps each variant through the central error mapper. Unexpected exceptions still go to
a 500 handler, but they are the exception, not the default.

```typescript
// good: domain returns typed results, handler maps each variant
const result = await subscriptionService.cancel(id, userId, { reason });
mapCancelResult(res, result);   // handles ok, not_found, denied, conflict, provider_error
```

## Query-Facing Interface Behavior

When a public entry reads collections, implement the agreed filter, sort, pagination,
permission filter, empty state, and rate/cost boundary.

- Apply the permission filter in the data query, not after fetching all rows. See the
  tenant-scoped query example above.
- Do not promise a total count, cursor, page size, or filtering capability the persistence
  layer cannot support safely.
- Check for unbounded responses, user-controlled sort expressions, query-per-item
  serialization, and nested private fields.
- Route storage, index, or consistency decisions back to Node02; implement the chosen query
  shape in `persistence-build.md`.

```typescript
// good: bounded, scoped, parameterized
async function listOrders(req: AuthedRequest, res: Response) {
  const userId = req.auth.userId;
  const page = clamp(parseInt(req.query.page) || 1, 1, 1000);
  const limit = clamp(parseInt(req.query.limit) || 20, 1, 100);
  const sort = resolveSort(req.query.sort);   // allowlist-mapped

  const orders = await orderRepo.findMany({ userId, page, limit, sort });
  res.status(200).json({
    items: orders.map(mapOrderSummary),
    page,
    limit,
    has_more: orders.length === limit,
  });
}
```

`has_more` is a safe signal. Do not return `total_count` unless the contract requires it and
the persistence layer can compute it efficiently.