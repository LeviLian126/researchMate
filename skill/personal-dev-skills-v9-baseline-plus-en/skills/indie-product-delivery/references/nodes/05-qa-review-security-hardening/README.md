# Quality Gate

## Read the relevant workflow

| Need | Read |
|---|---|
| establish acceptance, risk, evidence depth, review base, and diff or contract findings; reconcile evidence and issue the quality or release-readiness decision | `quality-scope-review-and-decision.md` |
| run runtime or browser QA, reliability, compatibility, performance, security, privacy, or trust proof | `runtime-reliability-and-security-proof.md` |

Every applicable requirement in the selected workflow is a minimum delivery standard because it protects the quality decision. Skip only genuinely irrelevant checks. Add investigation, proof, or repair when it helps complete that decision; stop only when the required credential or environment is unavailable, or when the work belongs to another node.

## Output contract

Return the review scope, evidence matrix and limitations, prioritized findings with
severity/confidence/owner/status, residual concerns, and one quality decision such as
`SHIP`, `SHIP_WITH_CONCERNS`, `BLOCKED`, or the workflow's more specific state. Route
implementation, architecture, or release actions to their owning nodes.
