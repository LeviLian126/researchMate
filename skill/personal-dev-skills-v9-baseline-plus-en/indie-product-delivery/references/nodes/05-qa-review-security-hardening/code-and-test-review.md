# Code and Test Review

Static review of LLM-generated code before runtime verification. Run CP1 through CP4
in order; each checkpoint produces findings that feed the final verdict.

## CP1: Understand the change

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

## CP2: LLM code audit

LLM-generated code has characteristic failure modes that compilation and tests alone
do not catch. Check every changed file for each pattern below.

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

For each finding, record: file, line, the problem, the expected behavior, and severity.
Verify API existence against the installed version and official documentation, not
model memory. Before flagging an import as fabricated, check whether the package is
listed in the lockfile or installed in `node_modules` or the virtual environment.

## CP3: Test quality review

Tests that pass do not prove the code is correct. Verify that tests actually test the
contract.

- Does the test execute the target code, or only verify mock calls and fixed return
  values? A test that asserts `mock.called` without checking real behavior is mock
  theater.
- Coverage dimensions: normal input, invalid input, boundary values, empty input,
  error propagation. At least the first two must be covered for any new behavior.

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

## CP4: Static gates

Run the repository's own commands. Do not invent commands that do not exist.

Discover commands in this order:

1. `AGENTS.md`, `CONTRIBUTING.md`, `README`
2. `Makefile`, `justfile`, `Taskfile.yml`
3. `package.json` scripts, `pyproject.toml`, `tox.ini`, `go.mod`, `Cargo.toml`
4. `.github/workflows`, pre-commit config

Execute in order: format check, then lint, then type check, then build, then targeted
unit tests for affected modules. Record the exact command and its exit code or result
for each.

When no standard command exists: describe what you searched, propose the minimum
viable command, and mark it as NOT_RUN until it actually executes. Do not guess a
command and report it as passed.

## Findings to record

For each checkpoint, record: what was checked, what was found, the evidence (command,
output, file, line), and the severity. Feed all findings into the final verdict in
`README.md`. A static gate failure is at least Major; a hallucinated API or placeholder
return on a core path is Blocker.
