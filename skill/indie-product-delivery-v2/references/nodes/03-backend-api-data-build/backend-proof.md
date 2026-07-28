# Backend Proof, Debug, and Observability

Prove an implemented backend slice, debug failures from the real boundary, add proportional observability, and prepare evidence without claiming release readiness — that judgment lives in the quality node.

## Sections
- [Hermetic local vs deployed/server proof](#hermetic-local-vs-deployedserver-proof)
- [Risk-tiered, contract-first testing](#risk-tiered-contract-first-testing)
- [Debug from root cause](#debug-from-root-cause)
- [Proportional observability](#proportional-observability)
- [Verify before claiming completion](#verify-before-claiming-completion)

## Hermetic local vs deployed/server proof

Follow the repository's execution-environment policy. Where it's silent, default to local hermetic proof and defer cross-module integration to the deployed/server environment. The reason is practical, not dogmatic: standing up a local database, broker, vector store, object store, provider simulator, or container usually doesn't reproduce the real boundary anyway and adds cost — so locally it's evidence, just not the same evidence. Install a new environment or dependency only when the user explicitly allows it.

For each changed behavior, choose the smallest proof that demonstrates the actual boundary, preferring existing framework, fixtures, helpers, and commands.

| Case | Required when | Hermetic local proof | Deployed/server proof |
|---|---|---|---|
| success | every changed capability | unit/domain/contract behavior through the real owner with in-process fakes | accepted request or job crosses the deployed modules that own the outcome |
| validation | untrusted input or field mapping | rejected/normalized input and schema behavior | deployed boundary rejects the same unsafe input without state leakage |
| authentication/access | protected/owned/tenant data | permission policy and concealed-resource contract | real identity, session, RLS, and cross-user denial in the authorized environment |
| conflict/duplicate | stateful write, retry, webhook, job, or payment | deterministic idempotency and transition rules | durable duplicate/conflict outcome across deployed state and executors |
| provider failure | remote dependency or async work | fixture-driven timeout, malformed response, error mapping | bounded provider or managed-sandbox failure through deployed protected config |
| transaction rollback | multi-write invariant | repository/transaction contract with isolated in-process state | failed managed DB write leaves durable deployed state consistent |
| migration/recovery | schema or data evolution | migration-file validation, dry-run, or pure backfill transform | authorized deployed migration, restart, repair, and recovery evidence |
| performance trigger | new list/search/export/fanout/query shape | bounds, limits, query-shape contract, deterministic benchmark | measured deployed latency, resource, quota, or queue signal |
| regression | previously working behavior broke | smallest network-free reproduction that fails before the fix | repeat only when the regression depends on a real deployed boundary |

Name the environment a test runs in — a test that flips environments silently hides what it actually proved. When integration is reserved for deployed/server environments, an in-process fake is valid only for a domain or contract boundary, not as a substitute integration environment. If authorization or the deployed environment is unavailable, keep the integration claim explicitly `unverified` rather than starting equivalent services locally. When the repo has no server-only rule, use the smallest authorized proof environment and keep local infrastructure proportional.

## Risk-tiered, contract-first testing

Test through meaningful boundaries in risk order: authorization and state transitions first, then failure handling and changed branches, then the happy path. A test against a mock that proves the mock mirrors the mock, not the contract — prefer the real owner with in-process fakes, and reach for a deployed boundary only when the risk demands it. A safe manual check is acceptable when automation is absent or the proof needs a real boundary; state its limit.

## Debug from root cause

Reproduce before fixing. Read the failure at the real boundary — the log, the returned status, the actual state after the call — rather than theorizing from the symptom. When several layers are involved, narrow to the smallest case that still fails before changing code; a patch that suppresses the symptom while the cause migrates is debt, not a fix.

## Proportional observability

Add signals that match the risk: structured error events on failure paths, a metric for the operation's outcome and latency when the boundary is performance-sensitive, enough log context to reconstruct a failing request without dumping secrets or PII. Don't instrument every function — instrument the boundaries and the failures that would otherwise be invisible.

## Verify before claiming completion

Claim only what the evidence supports: the boundaries proved, the cases run, and what's explicitly `unverified`. Don't describe release readiness here — hand the evidence forward and let the quality gate judge it. Report the slice, the proof that exists, the known gaps, and what the next owner needs to verify.
