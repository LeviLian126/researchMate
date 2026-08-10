# Slice Framing

Use this guide before writing code. It frames an approved backend slice into a compact
implementation plan so the later workflow files (domain, interface, persistence, provider,
proof) have everything they need.

For a trivial fix (one-line change, no contract impact), skip this file and go directly to
the relevant build file. For anything that touches a contract, state, data, or external
boundary, frame first.

## Sections

- [Recover Implementation Truth](#recover-implementation-truth)
- [Build the Implementation Spine](#build-the-implementation-spine)
- [Select a Build Mode](#select-a-build-mode)
- [Challenge Scope](#challenge-scope)
- [Frame the Build](#frame-the-build)

## Recover Implementation Truth

Read the Node01/02 handoff and restate the slice as one observable outcome. Then inspect
the repo to verify every material fact before implementing on it. Do not turn this into a
whole-repository archaeology project -- audit only the entry point, direct callers, domain
owner, repository, access enforcement, error mapper, and test harness for the relevant path.

Walk through a concrete example to make this real. Suppose the slice is "user cancels
subscription."

**Restate the outcome**: An authenticated user cancels their own subscription. The
subscription moves to `cancelling` state. Billing stops at period end. The user sees a
confirmation. A cancellation confirmation email is sent.

**Verify in the repo** (read the actual code, do not assume):

1. **Entry**: Find the existing subscriptions route. Does it have a `PATCH /subscriptions/:id`
   or a `POST /subscriptions/:id/cancel`? Read the route file and its handler. Note the
   transport convention (REST, RPC, event-driven).

2. **Domain owner**: Which module owns subscription state? Look for a `SubscriptionService`,
   `SubscriptionDomain`, or similar. If no owner exists, that is a design signal -- the
   slice may need a new owner, which means returning to Node02.

3. **Repository**: How is subscription data accessed? Find the repository or data access
   module. What query patterns exist? Is there tenant/owner scoping already?

4. **Access enforcement**: Where is authorization checked? Look for middleware, decorators,
   or in-handler checks. Is there a pattern like `requireOwnership(subscriptionId, userId)`?

5. **Error mapper**: How are errors returned? Find the error handling pattern. Is there a
   central mapper or do handlers ad-hoc construct error responses?

6. **Tests**: What test framework is used? Find the nearest behavior test for subscriptions.
   What fixtures and helpers exist?

Classify each fact: **verified from code** (you read it), **verified from contract** (Node02
documented it), or **assumption** (you inferred it). Assumptions about public fields, schema
semantics, tenancy, authorization, provider behavior, or recovery must be confirmed against
an approved source before implementing. Local naming, fixture values, and log wording may use
a reversible default.

## Build the Implementation Spine

Trace the approved behavior before choosing files or classes. The spine connects capability
to proof through every owner:

```
capability -> entry -> interface/access -> domain policy -> data/provider
           -> observable result or recoverable failure -> local proof
```

For each arrow, name the existing owner or explicitly mark it `[NEW]`. A missing owner is a
design signal, not permission to put all behavior in a controller.

Example spine for "user cancels subscription":

```
[Cancel subscription]
    |
    v
PATCH /subscriptions/:id/cancel          <-- entry (existing route)
    |
    v
validate input + authenticate user       <-- interface (existing auth middleware)
    |
    v
resolve subscription + check ownership   <-- access (existing requireOwnership)
    |
    v
SubscriptionService.cancel()             <-- domain [NEW method on existing owner]
  - verify current state is 'active'
  - transition to 'cancelling'
  - schedule billing stop at period end
  - enqueue cancellation email
    |
    v
SubscriptionRepository.update()          <-- data (existing repo)
    |
    v
return { status: 'cancelling',           <-- result (stable response)
          cancelsAt: periodEndDate }
    |
    v
test: cancel active subscription         <-- proof
      -> state becomes 'cancelling'
      -> billing stop scheduled
      -> email enqueued
      -> cancel already-cancelled -> conflict
```

This spine is not a file-by-file code plan. It keeps the implementer from discovering the
contract only after changes have spread across the repository.

## Select a Build Mode

Use the narrowest mode that covers the implementation risk.

**Extend existing module** -- the most common mode. An existing module already owns a
related behavior; you add a method or branch to it. Example: adding `cancel()` to an
existing `SubscriptionService` that already has `create()` and `renew()`. Read
`domain-build.md` for owner placement and `interface-build.md` if the entry changes.

**New boundary** -- a genuinely new capability that no existing module owns. Example: adding
export functionality when no export module exists. This requires evidence that no suitable
path exists and a Node02-approved module boundary. Read `domain-build.md` for owner design,
`interface-build.md` for the entry, and `persistence-build.md` if new data access is needed.

**Regression fix** -- observed behavior is wrong or a test fails. Reproduce before changing
code. Read `proof-debug-observability.md` for the debug workflow, then fix at the narrowest
owner.

Modes may combine when a slice truly crosses multiple boundaries. If a change expands into
multiple independent outcomes, trust models, data lifecycles, or release risks, return to
Node02 for a slice decision rather than silently widening the implementation.

## Challenge Scope

Before implementing, answer these five questions. They prevent scope creep and unnecessary
abstraction:

1. **What is the smallest vertical change that achieves the approved outcome?** If the
   answer involves more than one user-visible outcome, the slice is too wide.

2. **Does an existing route, service, repository, adapter, job, or test already solve part
   of it?** Reuse before creating. Name the specific module and method you are extending.

3. **Is a proposed abstraction protecting a real boundary or hiding uncertainty?** Apply the
   deletion test: if you deleted the abstraction, would complexity vanish (it was a
   pass-through) or reappear across N callers (it was earning its keep)?

4. **Which work is explicitly not in scope and should remain deferred?** Name it so it does
   not creep in during implementation.

5. **What realistic failure can this new path create in production, and which later proof
   will distinguish it from a guess?** Name the failure mode and the test that catches it.

## Frame the Build

Produce a compact implementation frame before editing. This is not a file-by-file plan --
it records the decisions that prevent the implementer from guessing.

- **outcome**: the observable behavior being implemented (one sentence)
- **owners**: existing or new entry, domain, data, and docs owners (named modules)
- **invariant**: the condition that must remain true before, during, and after the change
- **allowed change**: files or modules likely to change and why (name them)
- **non-goals**: related work deliberately left untouched
- **local proof**: the targeted test, reproduction, or safe observation that demonstrates
  the contract
- **side-effect limit**: credentials, data, provider, migration, or environment boundaries
  this slice must not cross
- **escalation**: evidence that would require Node01 (product meaning), Node02 (contract),
  Node05 (quality/security), or Node06 (release) re-entry

Example frame for "user cancels subscription":

- **outcome**: authenticated user cancels their own active subscription; state moves to
  `cancelling`; billing stops at period end; confirmation email sent
- **owners**: `SubscriptionService` (domain, new method), `SubscriptionController` (entry,
  new handler), `SubscriptionRepository` (data, existing), `EmailQueue` (async, existing)
- **invariant**: a subscription can only transition from `active` to `cancelling`; billing
  must not charge after the period end date; cancellation is idempotent (cancelling an
  already-cancelling subscription returns the current state, not an error)
- **allowed change**: `SubscriptionService` (add `cancel` method), `SubscriptionController`
  (add cancel route), subscription test file (add behavior tests)
- **non-goals**: refund logic, plan downgrade, UI changes, email template changes
- **local proof**: unit test through `SubscriptionService.cancel` with in-process fake
  repository; verify state transition, billing stop, email enqueue, and idempotent re-cancel
- **side-effect limit**: no real email sent in tests; no real billing provider called; no
  schema migration
- **escalation**: if billing provider has no "stop at period end" API, return to Node02 for
  contract decision; if cancellation needs refund, return to Node01 for product decision