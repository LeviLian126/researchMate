# Persistence, Provider, and Async Build

Use this guide for repository and schema mechanics, concurrency, migrations, provider adapters, jobs, callbacks, idempotency, reconciliation, and recoverable delayed work selected by Node02.

## Sections

- [Persistence, Concurrency, and Data Evolution Build](#persistence-concurrency-and-data-evolution-build)
- [Provider, Async, and Reconciliation Build](#provider-async-and-reconciliation-build)

## Persistence, Concurrency, and Data Evolution Build

#### 1. Recover the durable contract and existing data pattern

Read the Node02 entity/lifecycle/evolution contract and inspect the nearest repository,
schema, migration, test fixture, and query pattern. Name the durable source of truth,
its owner, tenant/account scope, identity/uniqueness rule, visibility boundary, and
current compatibility state before writing queries or schema changes.

| Data concern | Implement at Node03 |
| --- | --- |
| ownership | use the established repository/store boundary |
| identity | enforce approved key, external ID, uniqueness, and duplicate outcome |
| scope | apply tenant/owner/account filter in the query/mutation boundary |
| visibility | return only fields allowed by caller contract |
| lifecycle | persist approved state transitions and retention/delete behavior |
| integrity | use constraints/transactions/idempotency mechanics selected by design |
| evolution | encode approved old/new compatibility and recovery mechanism |
| proof | demonstrate changed query/mutation/migration behavior locally or safely |

Do not make a repository return an unrestricted row because a current caller happens to
filter it later. Data scope and field visibility must survive future callers.

#### 2. Build safe queries and collection behavior

Separate query mechanics from business policy, while ensuring the repository receives
the trusted scope and authorized filter set. Bind values safely and whitelist any
dynamic column, direction, include, or filter behavior.

| Query risk | Required implementation |
| --- | --- |
| owner/tenant bypass | include trusted scope in the data query for reads and writes |
| mass disclosure | use selected fields/mapper; do not expose internal columns by default |
| unbounded collection | apply approved page/limit/cursor and defend maximum size |
| unsafe sort/filter | map public tokens to known columns/operators; never interpolate raw input |
| query in loop | batch/eager-load/precompute where evidence shows repeated access |
| missing index pressure | compare new filter/order/join with existing schema; flag a concrete trigger |
| stale/empty behavior | preserve Node02 consistency and result semantics |
| write by guessed key | resolve canonical identity and verify affected-row/constraint outcome |

A performance concern becomes actionable when the changed query grows with users,
records, nested relations, exports, or provider fanout. Do not add speculative indexes
or caching without an observed query shape and a clear ownership/exit path.

#### 3. Make invariants, transactions, and concurrency durable

Use database/store mechanisms to make the approved invariant real. A pre-check in
application memory is not durable duplicate prevention or concurrency control.

| Concern | Durable mechanism |
| --- | --- |
| multi-write invariant | transaction/unit of work with known rollback boundary |
| duplicate request | unique key/constraint or durable idempotency record |
| stale update | version/conditional update/conflict detection as designed |
| quota/entitlement | canonical state update guarded by constraint/transaction |
| job/webhook status | durable transition plus dedupe identity |
| provider request intent | stored correlation/idempotency state before reconciliation |
| concurrent list/write | defined isolation/consistency expectation and safe outcome |
| audit/repair record | persist only the designed evidence needed for recovery |

State what happens when the transaction fails after an external action has begun, or
when a callback arrives twice. If the answer requires a new compensation, sequence, or
provider model, return to Node02/provider workflow rather than inventing it in SQL.

#### 4. Implement schema and data evolution safely

Classify the actual change as additive, constraint/index, transforming, destructive, or
provider-state linked. Follow the Node02 evolution record; do not replace it with a
generic migration script.

| Evolution step | Required implementation statement |
| --- | --- |
| preflight | existing rows, consumers, feature/config state, and required authorization |
| compatibility | old/new read/write behavior and mixed-version assumptions |
| schema change | additive field/index/constraint or explicit destructive rationale |
| backfill | batch identity/order, bounded work, resumability, idempotency, progress evidence |
| validation | dry-run/sample/count/constraint check and expected success condition |
| repair | safe rerun, forward-fix, manual owner, and evidence retained |
| removal | condition that permits dropping old field/path; Node06 executes it |
| provider state | reconciliation source and local/remote mismatch treatment |

For a new required field, decide how existing rows reach a valid value before adding
the enforcement constraint. For a rename or type transform, preserve the approved
compatibility window. For large/unknown data, avoid a single unbounded write and
record the concrete lock/downtime/throughput risk for Node05/06.

#### 5. Keep execution boundaries honest

Node03 may add migrations, safe preflight checks, dry-run modes, backfill code, repair
commands, fixtures, and local verification. Node03 may not run an unapproved
production migration, backup, destructive cleanup, or remote reconciliation.

Update affected module/API/backend implementation current-state docs when durable facts
changed. Architecture pages remain Node02 truth; release state remains Node06 truth.

## Provider, Async, and Reconciliation Build

#### 1. Recover the external boundary

Before touching a provider SDK, queue, callback, or job, identify the approved
capability, local owner, normalized input/output, secret boundary, provider identity,
timeout, cost/quota, retry/idempotency, user-visible state, recovery owner, and
evidence obligation.

| Boundary fact | Required implementation decision |
| --- | --- |
| trigger | request, event, schedule, operator action, or callback eligibility |
| durable identity | local record, correlation ID, idempotency key, or dedupe key |
| adapter | owner of provider protocol, mapping, credentials, and error normalization |
| external request | normalized payload, timeout, safe retry policy, cost/rate guard |
| completion | response, callback, polling, job status, or reconciliation source |
| failure | temporary, terminal, duplicate, partial, or recovery-required treatment |
| evidence | local fake, provider sandbox, signed fixture, or authorized live confirmation |

If a remote behavior, recovery outcome, price/quota policy, or provider replacement
decision is unknown, return to Node02. Do not encode a guess in a retry loop.

#### 2. Build adapter-first and keep secrets at the edge

Extend the existing adapter or create one only when provider protocol, credentials,
failure mapping, or replacement boundary actually needs protection. Services receive
normalized values and domain outcomes, not SDK objects or raw callback payloads.

| Adapter concern | Required behavior |
| --- | --- |
| configuration | document environment variable names and safe missing-config behavior; never values |
| secrets | keep credentials out of source, URLs, response bodies, and logs |
| input | construct provider request from trusted, validated, redacted domain data |
| output | validate/map remote result to normalized local result before domain use |
| timeout | use explicit bounded timeout and report a recoverable class |
| error | normalize provider/network/limit errors without leaking internals |
| observability | attach safe correlation/provider/job IDs and redacted structured context |
| test seam | use existing mock/fake/sandbox convention rather than live side effects |

Do not create an abstract provider factory because a second provider is imaginable.
Create the smallest adapter that protects the actual external boundary.

#### 3. Implement the reliable async lifecycle

For jobs, queues, webhooks, cron, realtime work, and provider callbacks, preserve this
lifecycle:

    trigger -> durable acceptance or rejection -> execution -> callback/status
    -> visible completion/failure -> reconciliation or manual repair

| Stage | Implementation responsibility |
| --- | --- |
| trigger | verify eligibility, identity, scope, and duplicate key |
| acceptance | store durable pending/intent state before work when contract requires |
| execution | use normalized input, timeout, bounded retry, and safe rate/cost controls |
| callback | verify signature/source, correlate safely, tolerate replay and out-of-order delivery |
| status | persist only valid state transition; expose approved user-visible result |
| retry | name retry owner, attempt limit/backoff, terminal condition, and replay safety |
| reconciliation | compare local/remote authority, record mismatch, invoke designed repair path |
| manual recovery | expose minimal operator evidence without a hidden bypass path |

A callback that cannot be verified, correlated, deduplicated, or mapped to a permitted
state must fail safely. Do not retry non-idempotent remote actions unless the provider
and local durable key make replay safe.

#### 4. Apply special-risk rules only when triggered

| Surface | Additional implementation constraints |
| --- | --- |
| payment | server plan lookup, hosted flow where approved, signature verification, event dedupe, sufficiently final entitlement state, no real charge without authorization |
| AI | redact/minimize input, enforce token/rate/cost cap, validate structured output, never let raw output cause irreversible state |
| upload | validate type/size/content/ownership, generate server-side key, preserve visibility/lifecycle contract |
| import/export | validate schema/size, bound processing, isolate tenant scope, report partial outcome and repair path |
| webhook | verify signature/timestamp/origin, dedupe event identity, avoid caller-controlled resource lookup |
| scheduled job | make schedule eligibility, overlap/dedupe, timeout, and stale-run recovery explicit |
| realtime | authenticate connection, scope subscriptions, bound fanout, preserve ordered/duplicate semantics as designed |

These are implementation safeguards. They do not authorize live credentials, charges,
mass messages, remote deletion, or uncontrolled cost.

#### 5. Prove behavior without unauthorized effects

Prefer the smallest appropriate evidence: adapter fake, signed callback fixture, local
job execution, dry-run import, sandbox, or explicitly authorized live confirmation.
Test malformed response, timeout, denied quota, duplicate delivery, replay, partial
completion, and recovery signal when the changed contract makes them relevant.

Update module/API/backend implementation current-state docs for durable adapter, event,
job, callback, or recovery behavior. Node05 assesses final security/QA depth; Node06
executes production reconciliation, rollout, monitoring, or rollback.
