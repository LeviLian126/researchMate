# Provider, Async, and Reconciliation Build

Use this guide for provider adapters, queues, jobs, webhooks, cron tasks, callbacks, and
reconciliation. Read `slice-framing.md` first if you have not framed the slice.

Node02 defines the external boundary contract (trigger, adapter owner, retry, recovery,
cost, evolution). This file implements the mechanics. If a remote behavior, recovery
outcome, price/quota policy, or provider replacement decision is unknown, return to Node02.
Do not encode a guess in a retry loop.

## Sections

- [Recover the External Boundary](#recover-the-external-boundary)
- [Build Adapter-First](#build-adapter-first)
- [Async Lifecycle](#async-lifecycle)
- [Callbacks and Idempotency](#callbacks-and-idempotency)
- [Special-Risk Rules](#special-risk-rules)

## Recover the External Boundary

Before touching a provider SDK, queue, callback, or job, identify the approved capability,
local owner, normalized input/output, secret boundary, provider identity, timeout, cost/quota,
retry/idempotency, user-visible state, recovery owner, and evidence obligation.

A concrete adapter shows these decisions in code:

```typescript
// The port (interface) -- defines what the domain needs, not how the provider works
interface BillingAdapter {
  scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult>;
  requestRefund(subscriptionId: string, amount: number): Promise<BillingResult>;
}

type BillingResult =
  | { ok: true; providerRef: string }
  | { ok: false; retryable: boolean; code: string };

// The production adapter -- owns provider protocol, credentials, error mapping
class StripeBillingAdapter implements BillingAdapter {
  constructor(private client: StripeClient, private timeout: number = 5000) {}

  async scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult> {
    try {
      const result = await this.client.subscriptions.update(subscriptionId, {
        cancel_at_period_end: true,
      }, { timeout: this.timeout });

      return { ok: true, providerRef: result.id };
    } catch (e) {
      if (e instanceof StripeTimeoutError) {
        return { ok: false, retryable: true, code: 'timeout' };
      }
      if (e instanceof StripeRateLimitError) {
        return { ok: false, retryable: true, code: 'rate_limited' };
      }
      return { ok: false, retryable: false, code: 'provider_error' };
    }
  }

  async requestRefund(subscriptionId: string, amount: number): Promise<BillingResult> {
    // ... similar pattern
  }
}

// The test double -- satisfies the same port, no network, deterministic
class FakeBillingAdapter implements BillingAdapter {
  scheduledCancellations: string[] = [];

  async scheduleCancellation(subscriptionId: string, periodEndDate: Date): Promise<BillingResult> {
    this.scheduledCancellations.push(subscriptionId);
    return { ok: true, providerRef: `fake_${subscriptionId}` };
  }

  async requestRefund(subscriptionId: string, amount: number): Promise<BillingResult> {
    return { ok: true, providerRef: `fake_refund_${subscriptionId}` };
  }
}
```

The domain service depends on `BillingAdapter`, not `StripeBillingAdapter`. Tests inject
`FakeBillingAdapter`. Production injects `StripeBillingAdapter`. Two adapters means the seam
is real.

## Build Adapter-First

Extend the existing adapter or create one only when provider protocol, credentials, failure
mapping, or replacement boundary actually needs protection. Services receive normalized
values and domain outcomes, not SDK objects or raw callback payloads.

### Good: adapter normalizes, domain receives clean types

```typescript
// adapter converts SDK response to domain result
class StripeBillingAdapter implements BillingAdapter {
  async scheduleCancellation(id: string, date: Date): Promise<BillingResult> {
    const stripeResult = await this.client.subscriptions.update(id, { cancel_at_period_end: true });
    return { ok: true, providerRef: stripeResult.id };   // normalized, no SDK types leak
  }
}

// domain service uses the port, never sees Stripe types
class SubscriptionService {
  constructor(private billing: BillingAdapter) {}

  async cancel(id: string, userId: string): Promise<CancelResult> {
    // ... state transition ...
    const billingResult = await this.billing.scheduleCancellation(id, periodEndDate);
    if (!billingResult.ok && !billingResult.retryable) {
      return { kind: 'provider_error', retryable: false, correlationId: id };
    }
    return { kind: 'ok', cancelsAt: periodEndDate };
  }
}
```

### Bad: SDK objects leak into the domain

```typescript
// domain directly calls the Stripe SDK -- no adapter
class SubscriptionService {
  async cancel(id: string, userId: string): Promise<CancelResult> {
    const stripe = new Stripe(process.env.STRIPE_KEY);   // secret in domain layer
    const result = await stripe.subscriptions.update(id, { cancel_at_period_end: true });
    // domain now knows about Stripe types, response shape, and error codes
    // testing requires mocking the Stripe SDK or hitting the real API
    // switching providers means rewriting the domain service
  }
}
```

### Secrets at the edge

Keep credentials out of source, URLs, response bodies, and logs. The adapter reads
configuration from environment variables; the domain service never sees the secret.

```typescript
// adapter constructor reads config
class StripeBillingAdapter implements BillingAdapter {
  constructor(
    private client: StripeClient,   // already configured with the key
    private timeout: number = 5000,
  ) {}
}

// factory at the composition root -- the only place that reads the secret
function createBillingAdapter(): BillingAdapter {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error('STRIPE_SECRET_KEY not configured');
  return new StripeBillingAdapter(new StripeClient(key));
}
```

Do not create an abstract provider factory because a second provider is imaginable. Create
the smallest adapter that protects the actual external boundary.

## Async Lifecycle

For jobs, queues, webhooks, cron, realtime work, and provider callbacks, preserve this
lifecycle. Each stage has a specific implementation responsibility:

```
trigger -> durable acceptance -> execution -> callback/status
  -> visible completion/failure -> reconciliation -> manual recovery
```

### Trigger

Verify eligibility, identity, scope, and duplicate key before accepting work.

```typescript
async function enqueueEmailJob(payload: EmailPayload, requestId: string) {
  // dedupe by request ID
  const existing = await db.query(
    'SELECT id FROM email_jobs WHERE request_id = $1', [requestId]
  );
  if (existing.rows.length > 0) return existing.rows[0].id;

  const result = await db.query(
    'INSERT INTO email_jobs (request_id, payload, status, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id',
    [requestId, JSON.stringify(payload), 'pending']
  );
  await queue.publish('email', { jobId: result.rows[0].id });
  return result.rows[0].id;
}
```

### Durable acceptance

Store pending or intent state before work begins when the contract requires it. If the app
crashes after the trigger, the job record survives and can be retried.

### Execution

Use normalized input, timeout, bounded retry, and safe rate/cost controls.

```typescript
async function processEmailJob(jobId: string) {
  const job = await db.query('SELECT * FROM email_jobs WHERE id = $1 FOR UPDATE', [jobId]);
  if (job.rows[0].status !== 'pending') return;   // already processed or in progress

  await db.query('UPDATE email_jobs SET status = $1, started_at = NOW() WHERE id = $2', ['processing', jobId]);

  try {
    await emailProvider.send(JSON.parse(job.rows[0].payload));
    await db.query('UPDATE email_jobs SET status = $1, completed_at = NOW() WHERE id = $2', ['completed', jobId]);
  } catch (e) {
    await db.query(
      'UPDATE email_jobs SET status = $1, error = $2, attempts = attempts + 1 WHERE id = $3',
      ['failed', e.message, jobId
    );
    if (isRetryable(e) && job.rows[0].attempts < 3) {
      await queue.publish('email', { jobId }, { delay: backoff(job.rows[0].attempts) });
    }
  }
}
```

### Callback

Verify signature/source, correlate safely, tolerate replay and out-of-order delivery. See
[Callbacks and Idempotency](#callbacks-and-idempotency) below.

### Status

Persist only valid state transitions. Expose the approved user-visible result.

### Retry

Name the retry owner, attempt limit, backoff, terminal condition, and replay safety. Do not
retry non-idempotent remote actions unless the provider and local durable key make replay
safe.

### Reconciliation

Compare local and remote authority. Record mismatch. Invoke the designed repair path. Do
not invent reconciliation logic during implementation -- if the mismatch handling is not
defined by Node02, return with the evidence.

### Manual recovery

Expose minimal operator evidence without a hidden bypass path. An operator should be able
to see the current state, the last attempt, and the safe next action -- without a secret
backdoor that skips the contract.

## Callbacks and Idempotency

A callback that cannot be verified, correlated, deduplicated, or mapped to a permitted state
must fail safely. Do not retry non-idempotent remote actions unless the provider and local
durable key make replay safe.

### Callback verification

```typescript
async function handleStripeWebhook(req: Request, res: Response) {
  // 1. verify signature -- reject unverified callbacks
  const sig = req.headers['stripe-signature'];
  let event: StripeEvent;
  try {
    event = stripe.webhooks.constructEvent(req.rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (e) {
    return res.status(400).json({ error: 'invalid_signature' });
  }

  // 2. correlate to local record
  const localPayment = await paymentRepo.findByExternalId(event.data.object.id);
  if (!localPayment) {
    return res.status(404).json({ error: 'unmatched_event' });
  }

  // 3. dedupe -- check if this event was already processed
  const alreadyProcessed = await webhookEventRepo.exists(event.id);
  if (alreadyProcessed) {
    return res.status(200).json({ received: true });   // idempotent acknowledgment
  }

  // 4. record the event
  await webhookEventRepo.insert({ eventId: event.id, type: event.type, status: 'processing' });

  // 5. check current state before applying (see persistence-build.md)
  if (localPayment.status === 'completed') {
    await webhookEventRepo.update(event.id, { status: 'completed', note: 'already_completed' });
    return res.status(200).json({ received: true });
  }

  // 6. apply the change
  await db.transaction(async (tx) => {
    await tx.payments.update(localPayment.id, { status: 'completed', completedAt: new Date() });
    await tx.webhookEvents.update(event.id, { status: 'completed' });
  });

  res.status(200).json({ received: true });
}
```

Key points: signature verification happens before any database lookup that could leak
information. Event ID dedupe prevents double-processing. Current-state check prevents
re-applying a completed payment.

### Replay handling

When the same callback arrives twice (Stripe retries webhooks), the second arrival must be
safe. The combination of event ID dedupe (step 3) and current-state check (step 5) handles
this. The callback returns 200 both times, but the payment is only updated once.

## Special-Risk Rules

These surfaces have additional implementation constraints because their failure modes are
irreversible or trust-affecting.

### Payment

- Look up the plan and price server-side; never trust client-provided price or amount
- Use hosted flows (Stripe Checkout, PayPal) when possible -- do not handle raw card data
- Verify webhook signatures before processing payment events
- Dedupe events by provider event ID
- Verify amount, recipient, and provider state match the local record before marking
  completed
- Entitlement state must be sufficiently final before granting access

```typescript
// payment verification: amount must match local record
if (callback.amount !== localPayment.amount) {
  throw new ConflictError('amount_mismatch');
  // do not mark completed -- the payment is for a different amount
}
```

### Upload

- Validate file type, size, content, and ownership before storing
- Generate the storage key server-side; do not trust client-provided filenames or paths
- Preserve the visibility and lifecycle contract (who can access, how long it persists)

```typescript
async function handleUpload(req: AuthedRequest, res: Response) {
  const userId = req.auth.userId;
  const file = req.file;
  if (!ALLOWED_MIME_TYPES.has(file.mimetype)) throw new ValidationError('invalid_file_type');
  if (file.size > MAX_UPLOAD_SIZE) throw new ValidationError('file_too_large');
  const key = `uploads/${userId}/${uuid()}-${sanitizedFilename}`;   // server-generated key
  await storage.put(key, file.buffer, { contentType: file.mimetype });
  await fileRepo.insert({ key, userId, size: file.size, expiresAt: expiryDate });
}
```

### Webhook

- Verify signature, timestamp, and origin before processing
- Dedupe by event identity
- Avoid caller-controlled resource lookup -- do not use a webhook payload field to look up
  a resource without verifying the correlation

### Scheduled job

- Make schedule eligibility explicit (what conditions must hold to run)
- Handle overlap: prevent two instances of the same job from running simultaneously (use a
  lock or dedupe key)
- Set an explicit timeout
- Handle stale runs: if a job was scheduled but the state has changed since scheduling, check
  current state before executing

### Realtime

- Authenticate the connection
- Scope subscriptions to the authenticated user's tenant/owner
- Bound fanout: limit how many connections receive a broadcast
- Preserve ordered and duplicate semantics as designed by Node02

These are implementation safeguards. Keep secrets and API keys out of code and logs, and
verify money-related effects before treating them as successful.