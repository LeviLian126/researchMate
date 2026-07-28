# Release Execution

Execute an authorized release with evidence at each step, contain before broad analysis, and record what actually happened.

## Sections
- [Readiness](#readiness)
- [Release-readiness matrix](#release-readiness-matrix)
- [Action authority and release status](#action-authority-and-release-status)
- [Environment, pipeline, and CI gates](#environment-pipeline-and-ci-gates)
- [Rollout and recovery](#rollout-and-recovery)
- [Post-deploy smoke, watch, and containment](#post-deploy-smoke-watch-and-containment)
- [Release record and follow-up](#release-record-and-follow-up)

## Readiness

Recover the handoff, not assumptions: the approved slice, acceptance, the quality-gate verdict and its named concerns, the target environment and dep boundary, the source/ref, the credentials and their scope. Discover the live release path each time — which artifact ships, which command runs it, which config it carries — rather than reusing a remembered one.

Release action is an external effect; it needs exact authorization. "Looks ready" is not authorization. Confirm who can approve, what scope (which environment, which data), and the blast radius.

## Release-readiness matrix

Assemble the readiness matrix from evidence, and gate release on what's actually required for this slice:

| Axis | Required |
|---|---|
| scope | the approved slice and its acceptance, not a larger bundle |
| source | the exact commit/ref and its quality-gate verdict |
| authority | named approver and approval scope (environment, data, region) |
| environment | target boundary, deploy method, rollback path |
| gates | the applicable gates passed with fresh evidence; failures classified (red/flaky/missing) |
| data migration | dry-run or pure-backfill transform checked; rollback/down defined |
| provider/external | callbacks, webhooks, keys, and fail-over reviewed for the change |
| smoke/watch | what defines success in the first window, who watches, for how long |

## Action authority and release status

Set the release status to match what's true, not what's planned. Status codes (and what each means) live in `references/methods.md` — `preparation only`, `READY_TO_EXECUTE`, `EXECUTED_AND_VERIFIED`, `EXECUTED_WITH_NAMED_CONCERNS`, `ROLLBACK_OR_DISABLE_ACTIVE`, `BLOCKED`. Don't advance past `READY_TO_EXECUTE` without authorization; don't report `EXECUTED_AND_VERIFIED` for an action that hasn't run with its required immediate proof.

## Environment, pipeline, and CI gates

Establish the deploy boundary: which environment the artifact targets, how it's reached, what config/flags/secrets it carries, and whether it's shared with other traffic. Inspect pipeline and artifact trust: signed/expected artifact, the gates that ran, who can push to the protected branch.

Classify a red, missing, or flaky CI gate by what it actually is, not by how convenient it is:

| Gate state | Treatment |
|---|---|
| red (real failure) | block; fix at the cause; don't bypass unless authorized with a named reason and follow-up |
| missing (didn't run for this slice) | run it or explicitly defer with an owner and trigger |
| flaky (passes on retry, intermittent) | treat as a defect to fix, not a pass — a flaky gate hides real failures; don't ship on green-if-you-rerun |
| red on unrelated test | confirm genuinely unrelated (no shared state or contract); document and proceed if the change can't touch it |

Repair and reprove the narrow pipeline mechanic rather than nudging a gate green.

## Rollout and recovery

Define the executable sequence before running it: ordered steps, the evidence each step produces, the observable success of each, and the rollback at each step. Execute with evidence at each step — a step that "completed" without an observable signal is an assumption, not proof. Decide recovery from the *actual* state, not from where you hoped you'd be: read what shipped, what's live, what failed, before rolling back or re-pushing.

A migration, provider action, or release affecting data or external state is low-reversibility; it needs the same authorization as the release and a recovery path defined in advance.

## Post-deploy smoke, watch, and containment

Establish the actual post-deploy target (which environment, which artifact, which traffic), then run smoke deliberately — the smallest checks that prove the primary path and the change's specific behavior crossed the deployed boundary. Open a bounded watch window: what to watch, who watches, when to stop.

**Contain before broad analysis.** If something breaks after deploy, the first move is containment (rollback, disable, route-around, scale-down) to stop the harm, then investigation — the opposite order costs users time you don't get back. Close the watch window deliberately — a green minute isn't "stable"; state the window and the signal that ended it.

## Release record and follow-up

Write the release record only when the durable truth changed: date/version, changed scope, the artifact/source, the action taken, the immediate proof, any named concerns with owner/trigger/mitigation/watch, and the next action. Write notes that match the reader — ops wants state and the watch signal; the next dev wants what changed and what to verify.

If the next work is production health, customer evidence, or the next slice, that's the ops/learning topic — open it if the present question is "what did this tell us" rather than "did we ship it." These are topic pointers, not a required sequence.
