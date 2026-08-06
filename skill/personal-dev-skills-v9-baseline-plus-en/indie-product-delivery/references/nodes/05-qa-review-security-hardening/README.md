# QA Node

Verify LLM-generated code actually works before it ships: the app starts, core user
flows pass end-to-end, the frontend renders correctly across mobile and desktop
resolutions without layout or visual bugs, LLM-specific code defects are caught here
rather than in production, and database, data-privacy, API, and auth security meet
indie-product standards.

## Read the relevant workflow

| Need | Read |
| --- | --- |
| review diff, audit LLM code quality, check test validity, run static gates | `code-and-test-review.md` |
| start the app, run E2E user journeys, verify multi-resolution frontend visuals, debug runtime issues | `runtime-frontend-qa.md` |
| security review (database, data privacy, API, auth, dependencies, file upload, XSS, injection) and reliability checks | `security-and-reliability.md` |

Run every checkpoint that applies to the change. Skip only genuinely irrelevant
checks and record why. Do not skip a checkpoint merely because it is inconvenient.

## Classify risk

| Risk | Trigger | What changes |
| --- | --- | --- |
| STANDARD | no auth, payment, migration, public API, data schema, or file upload touched | run CP9 baseline items (no secret leak, no XSS, no known-high-risk dependency) + CP11 basic scan |
| HIGH_RISK | any of the above touched | run CP9 in full across all 6 security domains + CP10 reliability + CP11 full scan |

Even STANDARD changes must run basic security checks. No secret leak, no XSS, and
no known high-risk dependency are indie-product baselines, not optional.

## Checkpoints

| CP | File | What it checks |
| --- | --- | --- |
| CP1 | code-and-test-review | change understanding: diff, intent, unrelated changes, TODO/stub |
| CP2 | code-and-test-review | LLM code audit: hallucinated API, placeholder returns, silent fallback, swallowed exceptions |
| CP3 | code-and-test-review | test quality: real contract testing, positive/negative/boundary coverage |
| CP4 | code-and-test-review | static gates: lint, type check, build, targeted unit tests |
| CP5 | runtime-frontend-qa | app startup: dev server or build runs without error |
| CP6 | runtime-frontend-qa | E2E user journeys: core flows pass end-to-end |
| CP7 | runtime-frontend-qa | multi-resolution frontend: 6-level device matrix fully covered |
| CP8 | runtime-frontend-qa | debug: root-cause and fix when CP5-CP7 fail |
| CP9 | security-and-reliability | full security review: database, privacy, API, auth, dependencies, frontend |
| CP10 | security-and-reliability | reliability: error handling, retry, idempotency, concurrency, data consistency |
| CP11 | security-and-reliability | security verification: non-destructive negative checks and tool scans |

## Severity

| Severity | Meaning | Effect on verdict |
| --- | --- | --- |
| Blocker | app cannot start, core flow broken, security hole, data loss risk | must FIX, cannot PASS |
| Major | significant UX issue, non-core flow broken, test quality issue, medium-risk security issue | strongly recommend FIX |
| Minor | cosmetic, edge case, nice-to-have | record, acceptable |

## Verdict

| Verdict | Condition |
| --- | --- |
| PASS | all applicable checkpoints pass, no Blocker, app works end-to-end |
| FIX | Blocker or Major found, fixable within current scope; re-verify after fix |
| BLOCKED | cannot verify (missing environment or credentials) or cannot fix (needs upstream node) |

## Output contract

A QA report must contain all of the following to claim the project passed QA:

1. **Review scope**: revision, base, changed file list.
2. **Checkpoint matrix**: each CP marked PASS, FAIL, or NOT_RUN, with the command or observation used.
3. **Defect list**: each defect with severity, file and line, description, and fix direction.
4. **Security results**: one conclusion each for database, data privacy, API, auth, and dependency security.
5. **Multi-resolution results**: screenshot or observation for each of the 6 device levels.
6. **Verdict**: PASS, FIX, or BLOCKED.

### Hard PASS conditions

All of the following must be satisfied to issue PASS:

- The app starts without errors.
- All core user journeys pass end-to-end.
- The frontend has no layout overlap, overflow, or visual bug across 6 device resolutions.
- No console errors or failed network requests on core paths.
- No LLM code defects: no hallucinated API, no stub or placeholder return, no swallowed exception, no test weakening.
- Static gates pass: lint, type check, build.
- Tests exercise the real contract, not mock theater.
- Database security passes: no SQL injection, connection secured, least-privilege access.
- Data privacy passes: PII not leaked, HTTPS enforced, no secret in repo.
- Auth and authorization pass: no auth bypass, no IDOR, session secured.
- No known high-risk dependency vulnerabilities.
- For HIGH_RISK changes: full security review passes.

## Boundaries with other nodes

QA verifies code that is already built. It does not design UI, change public contracts,
execute deployment, or write implementation code. Route those to Node01 (product),
Node02 (contracts), Node03 (backend), Node04 (frontend), or Node06 (release). Narrow
bug fixes found during QA are allowed; changing product flow, public API, auth or
billing policy, or large refactors are not.
