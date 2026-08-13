# Code and Test Review

Independently inspect the changed source and its real call path before relying on runtime results.
Then judge whether the test evidence can expose the important ways the goal could fail. Use the
tables to focus attention; select depth from the changed contract and risk rather than treating the
headings as a mandatory sequence.

## Understand the change and call path

Before judging code, confirm what changed and why.

- Get the diff: `git diff <base>...HEAD`. Determine base from PR metadata, CI config,
  or the remote tracking branch. Do not default to `main` without checking.
- Recover intent from requirements, issue text, PR description, or acceptance criteria.
  A commit message is weak evidence; do not treat it as the source of truth.
- Scan for unrelated changes: side modifications not tied to the requirement, debug
  code (`console.log`, `print`, `debugger`), temporary flags, or mass reformatting
  noise. Flag each as a finding; they inflate the diff and hide real changes.
- Scan for placeholder signals in changed code: search for `TODO`, `FIXME`, `pass`,
  `return None`, `return True`, `return []`, or a function returning a fixed value
  without consulting its inputs. Treat each as suspicious unless the contract
  genuinely requires a stub. LLM-authored code can carry correct structure and types
  while the decision logic is absent.

## Audit AI-generated code

LLM-generated code has characteristic failure modes that compilation and tests alone
do not catch. Scan every changed file across the table, then investigate the candidates that are
applicable and reachable in the current system.

| Check | What to find | Why it is LLM-specific |
| --- | --- | --- |
| Hallucinated API | calls a method, function, or field that does not exist, or uses a parameter signature that does not match the installed version | LLMs mix memories from different versions or libraries |
| Placeholder return | `return None`, `return True`, `pass`, or a fixed value that ignores the inputs | LLMs produce correct structure but leave decision logic empty |
| Hardcoded data | fake data disguised as real logic, e.g. `return [{"name": "test"}]` | LLMs use sample data to "make the code run" |
| Silent fallback | try/except that swallows the exception and returns a default without logging or re-raising | LLMs prefer "code that does not error" over correct error handling |
| Test weakening | deleted, skipped, or weakened existing tests, or updated snapshot/golden files without a reason | LLMs may change assertions to make tests pass |
| Over-broad permission | default-allow logic, missing tenant or owner scope, admin routes without guards | LLMs often skip multi-tenant isolation |
| Missing error handling | unbounded loops, N+1 queries, no timeout or retry, resources not closed | LLMs write happy paths and skip resource management |
| Fabricated dependency | imports a package that does not exist, or assumes a config key that was never defined | LLM memories contain outdated or invented package names |
| Disconnected implementation | new code is never reached from the production entrypoint, registration, route, job, or build artifact | LLMs can implement a convincing island without wiring it into the system |
| Plausibility-only logic | types and control flow look complete but a required state transition, persistence write, permission, or side effect never occurs | surface coherence can hide an absent business outcome |
| Cargo-cult abstraction | unnecessary interfaces, helpers, factories, or generic wrappers obscure one concrete rule and its owner | familiar patterns are reproduced without a real seam or second implementation |
| Context contradiction | code follows a remembered convention or adjacent example that conflicts with current repository contracts, config, or dependency versions | generated changes may combine individually plausible but incompatible contexts |

For each finding, record: file, line, the problem, the expected behavior, and severity.
Verify API existence against the installed version and official documentation, not
model memory. Before flagging an import as fabricated, check whether the package is
listed in the lockfile or installed in `node_modules` or the virtual environment.

## Review test strategy and strength

Tests that pass do not prove the code is correct. Verify that tests actually test the
contract.

- Does the test execute the target code, or only verify mock calls and fixed return
  values? A test that asserts `mock.called` without checking real behavior is mock
  theater.

Design tests from the public contract—interface signature, schema, acceptance criteria,
and error specification—not from reading the implementation. Tests that mirror the code's
internal branches share the implementer's assumptions and cannot expose the blind spots
that produced the bug. Enumerate scenarios from the contract first (normal, boundary,
error, state transition, concurrency, authorization), then read the code only to confirm
coverage gaps. In Phase 1, the same subagent writes tests while forbidden from reading
the implementation source—give it only the interface, schema, and acceptance criteria.
In Phase 2, lift the restriction so it can review the source and confirm coverage gaps.

Build a compact risk map before asking for more tests. Use the goal and public boundary to decide
which dimensions can reveal a material failure.

| Test dimension | Apply when it can falsify |
| --- | --- |
| normal and boundary behavior | the promised result, size/range limit, empty state, or compatibility edge |
| schema and logical validity | malformed types, missing/null/unknown fields, or valid fields forming an invalid combination |
| authorization and abuse | actor, tenant, object, role, route, method, workflow order, or server-owned fields can be manipulated |
| state, replay, and concurrency | steps can be skipped/reordered/repeated, delivery can duplicate, or shared state can race |
| side effects and invariants | persistence, messages, charges, jobs, cleanup, ownership, or totals can diverge from the returned result |
| resource and dependency failure | input can amplify work, or timeout, quota, partial response, restart, and retry can corrupt or multiply effects |
| property, fuzz, performance, mutation | examples cannot cover an important input space, parser, invariant, capacity claim, or assertion-strength question |

Prefer the cheapest deterministic layer that reaches the real contract. Escalate to integration,
browser, fault, performance, fuzz, or mutation evidence only when a smaller test cannot faithfully
observe the risk. Any bug, bypass, crash, race, or pathological input found during review should
become a minimized regression test or retained corpus case when the repository has a suitable seam.

### Bug-fix evidence chain

For a bug fix, all five steps are required. Missing any step lowers verdict confidence.

1. Reproduce the failure on the baseline.
2. Add a minimal regression test.
3. Prove that test fails on the baseline.
4. Prove that test passes on the patched version.
5. Run the relevant regression suite to confirm no side effect.

### Test anti-patterns

Flag any of these as Major severity:

- Shared mutable state or execution-order dependence between tests.
- Arbitrary `sleep` used where a condition wait or deterministic fixture is available.
- Mock that completely replaces the integration behavior being verified.
- Test that depends on a real external side effect (live API call, real database write
  that is not cleaned up).
- Snapshot or golden file updated without human review of the semantic change.
- Test that was deleted, skipped, or had its assertions weakened without a reason.

## Run static and build gates

Run the repository's own commands. Do not invent commands that do not exist.

Discover commands in this order:

1. `AGENTS.md`, `CONTRIBUTING.md`, `README`
2. `Makefile`, `justfile`, `Taskfile.yml`
3. `package.json` scripts, `pyproject.toml`, `tox.ini`, `go.mod`, `Cargo.toml`
4. `.github/workflows`, pre-commit config

Run the repository gates that apply to the changed deliverable. When several apply, prefer format
check, lint, type check, build, then targeted tests so cheap failures surface early. Record the exact
command and its exit code or result for each command actually run; do not run an unrelated build or
full suite merely because it appears in this ordering.

When no standard command exists: describe what you searched, propose the minimum
viable command, and mark it as NOT_RUN until it actually executes. Do not guess a
command and report it as passed.

## Findings to record

For each finding, record what was checked, the evidence, impact, and severity. Feed material
findings into the verdict in `README.md`. A static gate failure is at least Major when it invalidates
the deliverable; a hallucinated API, disconnected core path, or placeholder outcome on a required
flow is Blocker.
