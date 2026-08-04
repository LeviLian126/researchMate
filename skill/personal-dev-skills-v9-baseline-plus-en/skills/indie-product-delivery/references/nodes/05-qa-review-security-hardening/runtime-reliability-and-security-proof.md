# Runtime, Reliability, and Security Proof

Use this guide when direct runtime behavior, compatibility, reliability, performance, data evolution, security, privacy, or trust claims require risk-triggered evidence.

## Sections

- [Runtime, Browser QA, and Root-Cause Debug](#runtime-browser-qa-and-root-cause-debug)
- [Reliability, Performance, and Evolution Review](#reliability-performance-and-evolution-review)
- [Security, Privacy, and Trust Hardening](#security-privacy-and-trust-hardening)

## Runtime, Browser QA, and Root-Cause Debug

#### 1. Select proof depth and repair scope

Select proof depth from the changed risk and the evidence needed for the user's decision.
When the current task includes a narrow repair, fix it directly and rerun the relevant proof.

| Mode | Use when | Scope |
| --- | --- | --- |
| Quick | G0/G1 smoke or changed static/local surface | changed page/route and primary interaction |
| Focused | named G2 journey or regression | primary path, key states, adjacent regression, desktop+narrow |
| Full | G3, launch candidate, or explicit full QA | critical journeys/roles, console/network, responsive/accessibility |
| Regression | prior issue/report/fix | original path plus fixed/persistent/new outcome |
| Diff-aware | patch with no URL | map diff to affected routes; use Quick fallback if unclear |

Confirm target build/version, safe account/data, available environment, available
backend/mock, and evidence location. Never record passwords, cookies, tokens, raw PII,
or provider secrets.

#### 2. Reconnoiter before driving interaction

For dynamic pages, wait for usable rendered state before selecting elements. Inspect
route, viewport, page content, console, relevant network behavior, and semantic
selectors. Then execute the journey.

    navigate -> wait for meaningful render/data condition -> inspect rendered state
    -> locate role/text/test selector -> interact -> inspect result/network/console

Do not infer runtime behavior from source code alone. Do not use arbitrary sleeps when
an element, response, loading state, or network condition can be observed.

#### 3. Verify the journey and visible states

Walk each relevant journey:

    entry -> comprehension -> action -> response -> feedback -> persistence/navigation
    -> recovery or next action

| Area | Verify when relevant |
| --- | --- |
| action | primary action is visible, enabled only when honest, and has clear consequence |
| input | empty, invalid, boundary, long, duplicate, stale, and recovery behavior |
| state | loading, empty, success, pending, auth, denied, conflict, provider, partial/stale |
| navigation | deep link, back/forward, current location, retry/exit path |
| responsive | desktop and narrow viewport, primary action, overflow, touch, navigation |
| accessibility | keyboard path, focus-visible, labels, dialog/menu behavior, contrast/motion basics |
| integration | disclosed mock or safe real endpoint, error mapping, no private leakage |
| runtime | console errors, failed requests, unexpected retries, layout/runtime failure |

A browser result can demonstrate visible outcome and request behavior. It cannot alone
prove database persistence, tenant isolation, payment finality, webhook verification, or
server authorization; add the appropriate API/integration/security evidence.

#### 4. Debug from root cause

When runtime evidence fails:

1. Preserve exact precondition, route, viewport, data/auth state, command, error,
   screenshot, console/network signal, and relevant recent change.
2. Reproduce narrowly and identify whether it is deterministic, state-dependent,
   environment-dependent, or externally dependent.
3. Compare the nearest working path and trace browser -> route -> API -> backend/mock
   -> state owner -> rendered result.
4. State one falsifiable hypothesis with evidence.
5. Make the smallest safe diagnostic or repair that tests the hypothesis.
6. Rerun the original proof, then an adjacent regression path when warranted.

| Failure class | Route |
| --- | --- |
| user outcome/acceptance ambiguous | Node01 |
| API/auth/error/permission/async contract contradictory | Node02 |
| backend/mock/provider behavior wrong | Node03 |
| frontend state/render/interaction defect | Node04 |
| local quality finding/retest remains | Node05 |
| environment/release/rollout behavior | Node06 |

Do not make multiple speculative fixes at once. When another attempt would add no new
evidence, stop and return to the owner if the evidence suggests shared state,
cross-module coupling, a wrong contract, or environment/architecture failure.

#### 5. Repair only within the current scope

When the task includes a narrow fixture/isolation repair, Node05 may repair that issue,
obvious changed-code guard/error, a focused frontend state, docs/evidence, or other
mechanical defect that preserves product and contract behavior. It must not alter product
flow, public API, auth/billing policy, lifecycle, dependency, broad refactor, or deployment.

Capture before/after evidence for meaningful visual/interaction fixes. Add regression
proof for durable behavior bugs when a fitting existing layer exists; pure visual CSS
may rely on repeatable browser evidence.

## Reliability, Performance, and Evolution Review

#### 1. Select triggered concerns

| Trigger | Review focus |
| --- | --- |
| public API/CLI/webhook | field/type/status/error compatibility, pagination, rate/default behavior, docs/examples |
| provider/job/queue/cron | timeout, retry, idempotency, dedupe, callback verification, reconciliation, manual recovery |
| multi-write/state transition | transaction boundary, conflict, rollback, partial completion, durable audit/retry |
| migration/backfill/schema | compatibility, existing data, lock/downtime, batch/resume, validation, repair, release order |
| query/list/search/export | bounds, tenant filter, pagination, N+1, index/query shape, cost |
| frontend data/render | fetch waterfall, unstable lists, layout work, asset/bundle impact, loading behavior |
| flaky/failing tests | isolation, time/locale/random/network dependency, test order, fixture cleanup |
| regression | original proof, correct layer, adjacent behavior, durable guard |

Do not require every category for every change. Record NOT_APPLICABLE with the reason
when a specialist path was considered but not triggered.

#### 2. Evaluate test quality and negative paths

For changed behavior, ask whether evidence tests the contract rather than merely a mock
or implementation detail.

| Test concern | Check |
| --- | --- |
| negative path | invalid input, denied access, absent/private resource, error/retry/rollback branch |
| edge case | empty/zero/single/maximum, boundary type, Unicode/special input, stale/concurrent state |
| regression | original bug behavior fails before fix when feasible and passes after it |
| isolation | no shared mutable state, order dependence, uncontrolled clock/locale/random/network |
| async | no arbitrary sleep/tight timing assertion; condition or deterministic fixture instead |
| real boundary | mock only where external/non-deterministic edge requires it |
| coverage | changed public behavior and new branch have a fitting proof layer |

Use a failure-isolation ladder when mutable state or order may influence the result:

    original reproduction -> targeted proof -> owning module suite
    -> full relevant suite -> repeat or vary order when the risk remains

A targeted test passing does not close a shared-state or order-dependent failure. Inspect
global stores, local files, ports, clocks, locale, randomness, process state, and fixture
cleanup when an isolated result differs from the full suite.

Cover the core business behavior changed by the slice with a fitting proof layer. Measure
line or statement coverage when the repository already supports it and record the command,
scope, result, and exclusions, but do not turn the percentage into the quality goal.
Generated/vendor code, declarative schemas, framework bootstrap, and behavior that only
a real database, queue, provider, browser, or process can prove may use another fitting
evidence layer instead. Do not exclude difficult core code, create tests for trivial
accessors, or assert mock interactions merely to improve the number.

In a legacy repository with an existing baseline, a bounded change should not reduce it
and must add meaningful proof for the core behavior it changes. Record a remaining
project-wide deficit rather than expanding an unrelated request into a test rewrite.
Passing a percentage never compensates for missing proof of
authorization, state transitions, money/quota rules, idempotency, retries, recovery, or
other high-impact behavior.

Node03 owns implementation-time contract proof. Node05 decides whether the coverage
scope, exclusions, and selected proof layers support the quality claim; it does not
impose a uniform quota on every function or require a new framework solely for the
metric.

Before preserving or raising a coverage threshold, verify that the instrumented
denominator includes the production modules named by the quality claim. Fix scope and
exclusions first, measure the honest baseline second, and set the threshold third. Do not
treat a lower percentage after correcting an incomplete denominator as a regression, and
do not describe utility-only or layer-only instrumentation as repository, application, or
frontend coverage.

#### 3. Review compatibility and recovery behavior

Check the contract selected by Node02 and implemented by Node03/04.

| Concern | Evidence question |
| --- | --- |
| API shape | did fields/types/status/method/auth/default/error behavior change for a consumer? |
| pagination/rate | are limits, cursors/page size, rate/cost and empty behavior preserved or documented? |
| provider/job | is duplicate/replay safe, timeout bounded, callback verified, failure mapped, recovery named? |
| transaction | can partial failure violate the invariant; is rollback/conflict outcome visible? |
| reconciliation | does local/remote mismatch have a source of truth, retry owner, and repair evidence? |
| public docs | do API/module/current-state examples match actual behavior? |
| error/recovery | can caller distinguish invalid, denied, conflict, temporary, terminal, and recovery-required? |

A compatibility or recovery question that lacks a system decision returns to Node02. An
implementation defect returns to Node03/04. Do not let a QA reviewer invent a migration,
versioning, or compensation strategy.

#### 4. Review data evolution and migration safety

For a relevant schema/data change, verify the Node02 evolution record has been
implemented and Node06 receives the facts needed to execute safely.

| Area | Review |
| --- | --- |
| reversibility | rollback/forward-fix rationale and old/new code compatibility |
| data loss | columns/tables/type changes, references, existing null/data assumptions |
| backfill | bounded batch/order, resumability, idempotency, progress and failure evidence |
| locks/indexes | concrete table/workload/engine risk, duplicate/missing index, safe rollout requirement |
| multi-phase | old/new schema and code coexistence, feature/config order, mixed-version behavior |
| validation | dry-run/count/sample/constraint/postcheck and repair path |
| release handoff | backup/authorization/rollout/rollback owned by Node06, not run here |

Missing migration/recovery evidence is a blocker for a sensitive or release gate. A
local migration script existing is not proof that production execution is safe.

#### 5. Review performance proportionally

Trace changed workload rather than guessing at scale.

| Risk | Check |
| --- | --- |
| data | query in loop, missing scope/index, unbounded list/export, repeated serialization |
| algorithm | nested scans, repeated sort/filter, linear lookup inside loop, unnecessary allocations |
| async | blocking I/O/CPU in request/event path, fanout, timeout/retry storm |
| frontend | fetch waterfall, heavy dependency/asset, unstable render/list, layout thrash, image loading |
| cost | provider quota/rate, expensive retry, repeated background work, customer-triggered amplification |

A clear local defect can be fixed or routed to implementation. Capacity, cache, queue,
storage, SLO, or topology choices remain Node02/06 concerns. Do not block on a
hypothetical benchmark when no relevant workload trigger exists.

#### 6. Prove container delivery in layers

Treat container evidence as separate claims. Select the layers triggered by the quality
question and state exactly which target and platform were proved.

| Evidence | Proves | Does not prove |
| --- | --- | --- |
| container-file lint | authored instructions avoid the checked structural and security defects | an image builds or runs |
| dependency/intermediate target build | system and application dependencies resolve for that target | the complete production image starts |
| full image build | the selected production image can be produced on the tested platform | known-vulnerability or runtime health status |
| image or filesystem scan | the scanner's current known-vulnerability result under the recorded severity/fix policy | business correctness or startup |
| container smoke/health | the produced image starts and satisfies the tested health contract | complete user journeys or external integrations |

For a heavy image, permit a clearly named intermediate pull-request target only when it
materially reduces cost while retaining useful failure detection. Record it as partial
container proof and require the full production target at a scheduled or release gate.
Do not substitute local lint for a hosted Linux build or substitute a dependency-layer
build for a complete image claim.

## Security, Privacy, and Trust Hardening

A completed review means no known blocking evidence was found within the recorded scope;
it never proves that a system is unbreakable, fully secure, or free of vulnerabilities.

#### 1. Establish the security test boundary

Before dynamic security testing, record the owned target, revision, environment, account/data
scope, allowed methods, exclusions, side-effect limits, and reporting location.

| Safe baseline | Separate high-impact boundary |
| --- | --- |
| owned source review, local static tools, dependency/lockfile review, test fixtures, local/staging test accounts, provider sandbox, non-destructive checks | real-data access, brute force, DoS/load abuse, third-party scans, payment bypass, bulk mutation, persistence, credential rotation, cloud/DNS changes |

Never paste discovered secrets, tokens, private payloads, exploit strings, or real user
data into reports. Redact evidence while retaining enough context for the owner to fix.

#### 2. Build a sensitive-path inventory

Default to paths triggered by the active slice plus the shared boundaries they depend on.
Expand to a repository-wide posture audit only when the user explicitly requests a full
security audit; do not turn an ordinary change review into a whole-repository ceremony.
In that audit, census every owned entry and execution surface before sampling code.

| Area | Inventory |
| --- | --- |
| identity/access | login/session/token, role, tenant, owner, admin, service/provider identity |
| entry surfaces | public/authenticated/admin/machine API, route, CLI, upload, webhook, realtime connection |
| inputs | query/body/header/cookie, file, URL, event, import, retrieved content, model output |
| data | PII/private identifiers, retention/export/delete, database scope, logs/analytics |
| external/execution | payment, storage, provider callback, AI, email/message, integration, queue/job/schedule |
| rendering | unsafe HTML/template/URL/content, download/export, client-side secrets |
| delivery/infrastructure | dependency/lockfile, CI, container/image, IaC, deploy, environment, credential boundary |
| operations | debug/admin tools, maintenance commands, observability, documentation |
| enforcement | validation, authn, authz, scope filter, signature verification, error disclosure |

Mark each as present, changed, inherited, or not applicable. A feature touching no
obvious auth code can still create an authorization or data exposure boundary.

For an explicit repository-wide audit or a suspected or confirmed credential leak,
inspect relevant version history without printing secret values. Treat a credential
committed at any point as an incident even when the current file no longer contains it:
record revocation and rotation as required actions, establish the exposure window, and
check provider audit logs and abuse evidence through the authorized owner. Do not rotate
credentials or rewrite history without explicit authority, and never treat deletion or
history rewriting as a substitute for rotation.

#### 3. Perform static-first trust review

| Threat area | Inspect |
| --- | --- |
| validation | type/schema/size, allowlists, server-owned fields, untrusted external/model input |
| authn/authz | missing guard, default allow, IDOR, tenant/owner scope, role escalation, expiry |
| injection | SQL/query, command, template/XSS, SSRF, path/header/LDAP, deserialization |
| secrets/crypto | hardcoded key, weak/predictable token, nonconstant secret compare, logs/URLs/errors |
| privacy | unnecessary collection, private response fields, raw PII logs, retention/export leakage |
| uploads/callbacks | type/content/path, ownership, visibility, signature/timestamp/replay/correlation |
| money/entitlement | server lookup, final state, event dedupe, amount/plan authority |
| dependencies/CI | provenance and maintenance, lock changes, install scripts/actions, untrusted trigger data, permissions, supply chain |
| infrastructure | container user/privilege, secrets in images, broad IAM, production-data crossover, privileged host access, TLS verification |
| AI/provider | prompt/RAG injection, retrieval poisoning, deterministic tool/action authorization, output trust, redaction, bounded loops/context/fanout/cost |

Review enforcement at the server/data boundary, not just UI hiding. A formal finding
must show the exploit path: attacker-controlled input, the actual data or control path,
the missing or bypassed control, and the resulting capability or impact. Cite the exact
code, configuration, or line context and name the remediation owner and required retest;
do not infer a vulnerability from a dangerous primitive or vague pattern alone.

After confirming a vulnerability, search the authorized repository scope for the same
dangerous primitive, data path, or control omission. Verify and report sibling instances
separately; variant analysis does not authorize expanding the requested mutation scope.

#### 4. Run controlled negative checks within the target scope

Use local/staging/test accounts and non-destructive probes. Examples include denied
owner/tenant access, invalid input, forged/malformed callback fixture, missing/expired
identity, safe upload rejection, private-field omission, rate guard, or sandbox payment
event. Stop immediately if target ownership, data safety, or mutation scope is unclear.

Do not access other-user data, exfiltrate sensitive records, brute force credentials,
overload services, bypass real payment, or run a third-party scanner on an unowned
target. Route required production verification to Node06 only with explicit scope.

#### 5. Classify and retest

| Severity | Meaning |
| --- | --- |
| Critical | auth bypass, cross-tenant leak, secret exposure, payment compromise, RCE, destructive unauthenticated action |
| High | likely unauthorized data access, stored XSS, unsafe file access, webhook bypass, sensitive PII leak, SSRF |
| Medium | bounded exposure, weak validation, incomplete defense-in-depth, recoverable misconfiguration |
| Low/Info | limited hardening or documentation issue without meaningful exploit path |

Critical/High blocks SHIP until resolved and retested or explicitly handled through the
organization's emergency process. Medium/Low may become a concern only when acceptance
and sensitive proof remain intact and owner/trigger/mitigation are explicit.

Assign every confirmed finding one disposition: `fix`, `mitigate`, `accept`, or `defer`.
Acceptance or deferral applies only to non-Critical/High findings and must record bounded
impact, compensating control, owner, and a dated or evidence-based review trigger.
