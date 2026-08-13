# QA Node

Independently determine whether the delivered change is trustworthy enough for its stated goal and
risk. Every QA pass requires both forms of evidence: read the source and real calling context to find
defects tests may miss, and run at least one executable proof that reaches the changed behavior's
real boundary. Inspect the tests as part of judging that proof; reading tests without executing a
relevant behavior does not satisfy verification. A green command is evidence, not a substitute for
understanding the code, and visual review alone is not a substitute for executable behavior.

For the large-refactor, `HIGH_RISK`, and pre-release cases routed here by the top-level skill, use an
independent subagent or fresh session that did not choose the implementation path. Run verification
in two phases so the subagent does not inherit the implementer's assumptions. In Phase 1, give it
the goal, acceptance, interface signatures, schema, repository rules, and risk classification so
it can design contract-first tests without seeing the implementation. In Phase 2, give it the
implementation diff, Phase 1 tests, and raw runtime evidence so it can review the source and
confirm coverage gaps—not the implementer's diagnosis or desired verdict. Small changes keep the
top-level proportional verification rule and do not open an independent session by default.

## Read the relevant workflow

| Need | Read | Requirement |
| --- | --- | --- |
| understand the diff and calling context, audit AI-generated code, evaluate test strength, run static gates | `code-and-test-review.md` | always for code QA |
| prove runtime behavior or a user-visible journey, inspect frontend states and responsive behavior, debug failures | `runtime-frontend-qa.md` | when the claim depends on startup, integration, browser, or user-visible behavior |
| trace security, privacy, abuse, resource, concurrency, and dependency-failure risks | `security-and-reliability.md` | when the system or change exposes any of these boundaries |

Within each required workflow, select checks from the goal, changed boundaries, reachable failure
modes, and blast radius. For every applicable security, privacy, resilience, or AI-control risk, pair
source inspection with the smallest safe negative or failure proof that can reach it. If the needed
environment is genuinely unavailable, record the missing executable evidence as a proof gap; a static
trace may explain the risk but is not equivalent to a PASS. Do not omit a relevant risk because it is
inconvenient, and do not run unrelated checks merely to complete a matrix.

## Classify risk

| Risk | Typical trigger | Verification depth |
| --- | --- | --- |
| STANDARD | bounded change with no sensitive contract, data, permission, money, migration, provider, upload, or AI-control impact | inspect the changed source and tests; run the narrowest real behavior proof plus applicable baseline security checks |
| HIGH_RISK | auth, tenant boundary, payment, migration, public contract, schema, upload, external side effect, or AI/LLM control path changes | independently trace the full affected flow and adversarial paths; exercise security, resilience, state, and environment evidence that can falsify the claim |

No secret leak, reachable XSS, or known high-risk dependency is acceptable merely because a change is
small. Other domains become mandatory when the system and change make them relevant.

## Independent review surfaces

Use this table to keep source inspection and executable proof complementary. Mark a surface
`PASS`, `FAIL`, `NOT_RUN`, or `NOT_APPLICABLE` only when that status helps explain the verdict.

| Surface | Question the verifier must answer | Typical evidence |
| --- | --- | --- |
| intent and diff | does the change implement the requested behavior without unrelated or hidden scope? | requirement, base-aware diff, surrounding owner code |
| source and call logic | do inputs, branches, state changes, permissions, side effects, and failures compose correctly across the real call path? | manual source trace, installed API/config verification |
| AI coding defects | is any plausible-looking code fabricated, incomplete, over-abstracted, silently degraded, or disconnected from production behavior? | focused source audit and runtime/import evidence |
| test strength | can the tests fail on a meaningful contract violation, and do they assert state and side effects rather than mocks alone? | test review, regression red/green evidence, targeted mutation when valuable |
| runtime behavior | does the built application or affected journey work through the real boundary and environment? | startup/build, integration, browser, provider or deployed observation |
| security and privacy | can an untrusted actor cross a trust boundary, disclose data, alter protected state, or abuse a workflow? | source-to-control-to-sink trace and safe negative proof |
| resilience and cost | are resource growth, timeout, retry, concurrency, cleanup, and dependency failure bounded where the change exposes them? | limits, fault injection, deterministic race/property/performance evidence |

## Severity

| Severity | Meaning | Effect on verdict |
| --- | --- | --- |
| Blocker | app cannot start, core flow broken, security hole, data loss risk | must FIX, cannot PASS |
| Major | significant UX issue, non-core flow broken, test quality issue, medium-risk security issue | must FIX before PASS |
| Minor | cosmetic, edge case, nice-to-have | record, acceptable |

## Verdict

| Verdict | Condition |
| --- | --- |
| PASS | all material claims and applicable high-impact risks have adequate evidence; no Blocker or unresolved Major remains |
| FIX | Blocker or Major found, fixable within current scope; re-verify after fix |
| BLOCKED | cannot verify (missing environment or credentials) or cannot fix (needs upstream node) |

## Output contract

A QA report must let the reader reconstruct the verdict: name the goal, source/base and changed
surface; summarize the applicable review table and actual commands or observations; report defects
with severity, location, impact, and retest; distinguish local, server, browser, and unverified
evidence; then state `PASS`, `FIX`, or `BLOCKED`. Include detailed security, responsive, performance,
or resilience results when those domains affected the verdict, not as empty mandatory sections.

## Boundaries with other nodes

QA verifies code that is already built. It does not design UI, change public contracts,
execute deployment, or write implementation code. Route those to Node01 (product),
Node02 (contracts), Node03 (backend), Node04 (frontend), or Node06 (release). Narrow
bug fixes found during QA are allowed; changing product flow, public API, auth or
billing policy, or large refactors are not.
