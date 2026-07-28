# Quality Gate

Scope review to the change, run the right proof with the right authority, and issue a ship/hold decision grounded in evidence rather than a vibe.

## Sections
- [Scope the review](#scope-the-review)
- [Choose the proportional gate](#choose-the-proportional-gate)
- [Review in risk order](#review-in-risk-order)
- [Sensitive-path inventory and static-first trust review](#sensitive-path-inventory-and-static-first-trust-review)
- [Runtime, reliability, and security proof](#runtime-reliability-and-security-proof)
- [The ship/hold decision](#the-shiphold-decision)

## Scope the review

Recover what the change actually is and what authority you have: the approved slice and acceptance, the diff base, what's stable versus changed, and what the delivery/quality evidence so far shows. Classify facts by state (see `references/methods.md`). Establish the review base — the exact commit, environment, and config the evidence runs against — so a gate result can't quietly swap environments. A small change doesn't shrink the *applicable* requirements; it shrinks the set that *apply*.

## Choose the proportional gate

Match the gate to the risk, not to a ritual. The point is effort proportional to consequence, so a typo fix doesn't run a full security review and a payment change doesn't skip one.

| Gate | When | Evidence depth |
|---|---|---|
| read-only diff review | doc-only, no behavior change | confirm intent and affected anchors |
| contract review | API/data/permission/public behavior changes | contract model + affected behavior proof |
| behavior review | changed runtime behavior, no public contract | boundary behavior + regression proof |
| hardened review | payment, auth, PII, tenant, admin, destructive, or external-facing changes | the contract review **plus** special-risk proof and static-first trust review |
| release-readiness review | change heads to deploy | reconcile prior gates, fresh verification, and the decision record |

## Review in risk order

Read the full diff and affected context, then attack in risk order rather than top-to-bottom:

1. authorization and access control — who can trigger, who's denied, where it's enforced server-side;
2. state transitions and concurrency — invariants, races, idempotency, multi-write consistency;
3. failure and error paths — what's visible to the caller, what's safe to retry, what leaks state;
4. public contracts — compatibility, migrations, breaking changes;
5. changed branches and new behavior — then the happy path last.

Surface findings against named risk; don't restate intent. A defect that affects a risk bucket is a finding regardless of file size.

## Sensitive-path inventory and static-first trust review

Static review and local analysis touch nothing external, so they need no extra authority — use them freely. Dynamic checks (active probes, real payloads, scanning an owned target) need an owned target, allowed methods, and account/data scope: don't run them on assumptions.

Build the sensitive-path inventory for the change: auth/session/role/tenant enforcement, PII flows, payment or charge paths, admin or cross-tenant access, credentials and secrets, destructive writes, external calls and callbacks, provider fail-open defaults, rate/cost exposure. For each, name the enforcement point and where a failure would land.

Then review static-first: read the enforcement path in source, confirm checks happen on the server side and the resource, confirm failure is safe (deny-by-default, no fail-open), confirm secret handling stays at the edge, and confirm error responses don't leak identifiers or state. Run controlled negative checks only when authorized — they act on the world, so they need the same authority as any external effect.

## Runtime, reliability, and security proof

Run proof proportional to the risk (the hermetic-vs-deployed split lives in Node03). Cover what the gate actually claims:

- **Runtime/browser** — the journey and its full states (empty, loading, error, partial), not just the happy path; see Node04 for the browser proof matrix.
- **Reliability** — test quality and negative paths: do tests assert the contract or just that no exception fired; does a failing path surface a safe error.
- **Compatibility and recovery** — does the change keep what callers depend on; does a partial failure leave consistent state.
- **Data evolution** — migration is additive/backfillable first, dry-run before live, rollback defined; a long migration doesn't block read/write without an approved plan.
- **Performance** — proportional: bounds and limits for new list/search/export shapes, a real signal only when a deployed boundary matters.
- **Security/privacy** — the sensitive-path inventory and static-first review above; negative checks only when authorized.

Repair only within authority — a fix to a defect you found is still a change, and the same scope/proof rules apply to it. Don't silently harden beyond the task without noting it.

## The ship/hold decision

Reconcile the evidence before the status, then issue a risk-tiered verdict. Require fresh verification evidence for claims that gate release — a stale "it passed" doesn't count for a change that's moved since.

| Verdict | When |
|---|---|
| `SHIP` | every applicable gate passed with fresh evidence; no open risk above threshold |
| `SHIP_WITH_NAMED_CONCERNS` | holds with bounded concerns, each with an owner, trigger, mitigation, and watch |
| `HOLD` | an applicable gate failed or an evidence gap blocks a real risk decision |
| `BLOCKED` | something outside the change (authority, environment, a dependency) prevents resolving the gate |

Record the durable quality state: what was reviewed, the evidence, the verdict, the named concerns, and the next owner/action. Don't declare release readiness unless the change is also heading to deploy under the release node — a quality gate says "safe and proven," not "released."
