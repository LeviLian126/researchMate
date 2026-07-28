# Backend Build

Frame an approved backend slice, place business behavior in the correct owner, and implement boundaries without changing their contracts by accident.

## Sections
- [Recover implementation truth](#recover-implementation-truth)
- [Implementation spine](#implementation-spine)
- [Choose a build mode](#choose-a-build-mode)
- [Domain and state change](#domain-and-state-change)
- [Interface, access, and contract](#interface-access-and-contract)
- [Persistence, concurrency, and data evolution](#persistence-concurrency-and-data-evolution)
- [Provider, async, and reconciliation](#provider-async-and-reconciliation)

## Recover implementation truth

Read the architecture contract and restate the slice as one observable backend outcome: actor, entry, approved action, expected result, non-goals, acceptance, trust constraints, failure/recovery behavior, and proof obligation. Classify every input fact by state (see `references/methods.md`) so a convenient assumption can't become an implementation contract — public fields, schema semantics, tenancy, authorization, entitlement, provider behavior, lifecycle, compatibility, cost, and recovery are contracts, not defaults; local naming, fixture values, helper placement, and log wording are defaults you can pick and move on.

Read the nearest working path before creating a new one, and keep the audit bounded to what touches the slice. Don't broaden a focused backend build into a whole-repository archaeology project.

## Implementation spine

Trace the approved behavior before choosing files or classes; name the existing owner on each arrow, or mark it new:

```
capability -> entry -> interface/access -> domain policy -> data/provider -> observable result or recoverable failure -> local proof
```

A missing owner on an arrow is a design signal, not permission to put all behavior in a controller or handler.

## Choose a build mode

Use the narrowest mode that covers the implementation risk. Modes combine only when one vertical slice genuinely crosses both boundaries.

| Mode | Use when | Follow-up |
|---|---|---|
| local extension | an existing module implements an approved adjacent behavior | preserve convention; focused proof |
| interface/access | entry, input, output, auth, tenant, or public behavior changes | see Interface, access, and contract |
| domain state | use-case, invariant, conflict, or state transition changes | see Domain and state change |
| persistence evolution | query, schema, transaction, backfill, constraint, or durable dedupe changes | see Persistence |
| provider/async | provider, job, callback, remote state, or delayed work changes | see Provider, async, and reconciliation |
| regression fix | observed behavior is wrong or a test fails | reproduce before changing code |
| hardened slice | payment, admin, PII, tenant, auth, or destructive behavior changes | attach QA-ready proof obligations |

For each sub-problem, pick the strongest existing path before a new one — reuse / extend / replace / new (see `references/methods.md`). Reach for `new` only with evidence that existing paths can't cover it.

## Domain and state change

Put approved invariants, state transitions, and policy in the domain owner, free of transport and provider details. When a transition fails, surface an error the caller can act on rather than an implementation trace. A multi-write invariant needs a transaction boundary and a defined recovery outcome. A retryable action needs an idempotency key and a deterministic answer to "what happens if this runs twice."

## Interface, access, and contract

Validate at the entry; enforce authorization server-side at the boundary, not only in the client or a shared helper; return the public result and its limits; map domain and provider failures to stable contract errors. A public API change is a compatibility decision — keep what callers depend on unless the change is approved.

## Persistence, concurrency, and data evolution

Recover the durable contract and the existing data pattern before writing storage code: entities and their fields, indexes and constraints, ownership and tenant rules, the migration convention, and any query-shape that already works.

- Build queries bounded — paginate lists, filter at the source, don't load a table to filter in memory.
- Make invariants and concurrency durable — unique constraints, optimistic locks or version fields, transaction boundaries that match the invariant, and cleanup for abandoned rows or pending state.
- Evolve schema safely — additive and backfillable migrations first; run a dry-run or a pure backfill transform before touching live data; record the rollback or down-migration; never block a read/write path during a long migration without an approved plan.

## Provider, async, and reconciliation

Recover the external boundary first: adapter, credentials, timeout/retry/callback convention, and the provider-specific failure modes that differ from your own code's.

- Build adapter-first and keep secrets at the edge — the domain talks to a port, the adapter owns the provider SDK and credentials.
- Make the async lifecycle reliable — durable status, idempotent retries, bounded concurrency, timeouts, dead-letter or surfacing for stuck work, and reconciliation that can detect and heal drift without replaying side effects.
- Apply special-risk rules only when they are triggered: payment or charge paths, PII flows, tenant/admin cross-data access, and destructive operations each carry extra proof obligations (authorization scope, idempotency, reversibility) — don't soften them because the path looks short.
