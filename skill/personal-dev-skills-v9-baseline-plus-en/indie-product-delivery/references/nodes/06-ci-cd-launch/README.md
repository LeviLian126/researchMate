# Release Execution

## Read the relevant workflow

| Need | Read |
|---|---|
| establish target, source, Node05 evidence, environment, pipeline, credentials, and readiness | `release-readiness-environment-and-pipeline.md` |
| execute a rollout, migration, provider action, recovery, smoke/watch, and release record | `rollout-recovery-verification-and-record.md` |

Every applicable requirement in the selected workflow is a minimum delivery standard because it makes the release reproducible and recoverable. Skip only genuinely irrelevant checks. Add preparation, verification, or execution work when it helps complete the requested release outcome; stop when a required secret or API credential is unavailable.

## Output contract

Return the target and source, preflight facts, commands/actions performed, migration or
deployment result, immediate smoke/watch evidence, recovery or rollback judgment, release
record, and any remaining gaps. Distinguish planned, ready, executed, and verified states;
never infer execution from preparation. For every change, include the commit and push result
or the missing credential/API-key blocker that prevented it.
