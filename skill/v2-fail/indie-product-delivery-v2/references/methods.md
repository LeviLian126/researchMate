# Shared Methods

A few decision mechanisms recur across delivery topics. They live here once so each node can refer by name instead of re-deriving them. Read this when a node points to one of these mechanisms.

## Fact states

Before acting on a fact about the product, contract, or system, classify it. The point is keeping a convenient assumption from quietly becoming a contract.

| State | Meaning | Build treatment |
|---|---|---|
| confirmed | backed by current contract, repo evidence, or explicit user decision | implement on it |
| defaulted | reversible local detail chosen under an existing convention | record briefly; reversible if wrong |
| inferred | likely from code but not approved as contract truth | verify or constrain before relying on it |
| unknown | missing, conflicting, or unverifiable without external access | name the bounded gap, or stop |

You can default freely the local things that don't change an observable contract — naming, fixture values, helper placement, log wording. Don't default public fields, schema semantics, tenancy, authorization, entitlement, provider behavior, compatibility, cost, or recovery. These are contracts, not conveniences: a guess here becomes a rule someone depends on.

## Confidence and naming the gap

State confidence 0–100%. Below 70%, naming the missing facts is more useful than pushing ahead — say what would change direction, scope, risk, or handoff. Attach a current guess to every question so the human is choosing between options, not filling a blank. Ask one question when its answer changes the next question; batch only for broad scoping.

## Reuse / extend / replace / new

For each sub-problem, take the strongest existing path before proposing a new layer. New layers carry hidden cost: more to test, more to keep consistent, more reasons for two similar things to drift.

| Choice | When | Why it's cheap or expensive |
|---|---|---|
| reuse | a complete suitable path exists | preserves a proven owner; nothing new to maintain |
| extend | a proven owner needs to change | one change, no parallel concept created |
| replace | the path has a named deficiency | needs a defect, consumer impact, and an evolution route |
| new | no suitable path exists | genuinely novel; record why existing paths can't cover it |

`new` is the expensive default — reach for it only with evidence that reuse/extend/replace won't work.

## Evidence inventory

Keep a compact record so a claim can be separated from a convenient assumption. Confidence is about the supporting evidence, not the importance of the decision.

| Claim or unknown | Evidence source | Confidence | Consequence if wrong | Next check / owner |

When sources conflict, record the conflict, use the safer temporary assumption, and find the smallest check that resolves it. A low-confidence detail shouldn't trigger an architecture-wide rewrite — escalate only when the unknown can change the data owner, trust boundary, public compatibility, provider behavior, topology, or recovery path. A local unknown that doesn't touch those boundaries can remain named in the handoff for implementation to resolve.

## Status and evidence discipline

Consistent words make a board readable across pages and stop status inflation.

Delivery / capability status:
- `shipped`, `done`, `validated` — direct implementation, deployment, test, config, or maintained-contract evidence
- `in-progress`, `partial`, `blocked`, `candidate`, `deferred`, `unknown`, `untested` — name the missing proof, decision, dependency, or action that would move them

Evidence quality (for signal cards and claims):

| Quality | Meaning | Allowed claim |
|---|---|---|
| observed | dated event, trusted log, provider record, reproducible path | state the measured result and scope |
| estimated | incomplete count, proxy, or manually reconstructed sample | state the estimate and its limitation |
| self-reported | user, support, sales, or founder statement | state who reported it, not that it's universal |
| incomplete | missing event, inaccessible source, insufficient sample | state the gap and route instrumentation/research |

Mark inference as inference. When sources disagree, show the conflict and lower confidence rather than silently picking one. "Real-time" means the latest inspected evidence snapshot — don't simulate live telemetry without an authorized data source.

## Release status codes

| Status | Meaning |
|---|---|
| preparation only | no external release action occurred |
| `READY_TO_EXECUTE` | all known gates pass; action awaits authorization |
| `EXECUTED_AND_VERIFIED` | authorized action and required immediate proof passed |
| `EXECUTED_WITH_NAMED_CONCERNS` | bounded concern has owner, trigger, mitigation, and watch |
| `ROLLBACK_OR_DISABLE_ACTIVE` | containment changed the live state; follow-up remains |
| `BLOCKED` | release can't safely proceed or resume |

## Severity (incident routing)

Severity is about impact and how fast to act, not ceremony. Contain before broad analysis; investigate systematically after containment.

| Severity | Meaning | First route |
|---|---|---|
| `SEV0` | security, privacy, data, or billing integrity risk | release + quality immediately, then architect/backend |
| `SEV1` | primary path, auth, payment, or data failure | containment first, then backend/frontend/quality |
| `SEV2` | important degradation, provider/job failure, support spike | owner repair with active watch |
| `SEV3` | minor bug, trust/UX confusion, bounded workaround | backend/frontend or market-evidence route |
| `SEV4` | low-impact edge or isolated request | classify, park, or add to learning review |

The route columns point at which topic may help, not a required sequence — read whichever is relevant, in any order.
