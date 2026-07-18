# Rollout, Recovery, Verification, and Record

Use this guide to execute an authorized rollout or migration, verify the actual target, contain failures, close the immediate watch window, and record durable release state for operations.

## Sections

- [Rollout, Migration, Provider, and Recovery Execution](#rollout-migration-provider-and-recovery-execution)
- [Post-Deploy Smoke, Watch, and Incident Routing](#post-deploy-smoke-watch-and-incident-routing)
- [Release State, Notes, and Node07 Handoff](#release-state-notes-and-node07-handoff)

## Rollout, Migration, Provider, and Recovery Execution

#### 1. Recover the approved execution slice

1. Classify the slice: simple deploy, additive schema, expand/contract, destructive
   migration, backfill, provider/webhook, job/cron, payment/entitlement, DNS/CDN, cache,
   feature flag, import/export, or incident recovery.
2. Read the Node02 evolution/compatibility and recovery decisions, Node03 implementation
   evidence, Node05 proof status, and release-intake authorization before executing.
3. For each slice state the old/new state, consumers affected, compatibility window,
   preconditions, expected observables, stop condition, and human recovery owner.
4. Do not combine separately reversible or independently risky changes merely because they
   can be released in one command. Split the runbook when blast radius or recovery differs.

#### 2. Define the executable sequence

1. List actions in order with source ref/artifact, exact target, safe inputs, expected
   output, checkpoint, and what may be performed automatically versus manually.
2. Define a pause before every irreversible or externally charged effect. At each pause,
   check the expected observable before continuing.
3. Prepare the approved backup/snapshot, dry-run, idempotency key, batch/progress record,
   rate/cost limit, or provider sandbox evidence when the design calls for it.
4. Record which actions are retryable, which are safe only once, how duplicate callbacks
   are recognized, and where reconciliation or manual repair begins.

| Slice | Typical approved sequence |
| --- | --- |
| compatible deploy | verify artifact -> deploy -> smoke -> short watch |
| additive schema | backup/preflight -> expand -> compatible deploy -> smoke |
| expand/contract | expand -> dual read/write -> backfill -> cutover -> later cleanup |
| provider/webhook | compatible receiver -> safe test event -> switch -> reconcile -> smoke |
| job/cron | deploy -> controlled manual run -> enable schedule -> watch first run |
| payment/entitlement | approved test evidence -> deploy -> webhook/entitlement smoke -> active watch |
| DNS/CDN/flag | confirm previous state -> small switch -> propagation/behavior check -> disable path |

#### 3. Execute with evidence, not optimistic progress

1. Reconfirm the exact authorized target, source, and action immediately before execution.
2. Run one sequence step at a time; capture the actual output and compare it with the
   expected checkpoint before running the next step.
3. Keep destructive cleanup, contract removal, and old-data deletion out of the first
   release unless the approved slice specifically requires it and recovery remains viable.
4. When a step diverges, stop the sequence, preserve evidence, and use the approved
   disable, rollback, forward-fix, or manual recovery path. Do not improvise data repair.

#### 4. Decide recovery from the actual state

1. Prefer the least harmful available control: feature flag/config disable, job pause,
   provider switch, traffic reduction, artifact rollback, restore, then forward-fix.
2. Roll back application output only when it remains compatible with the current data and
   provider state. A forward-fix may be safer after irreversible schema/data changes.
3. If a provider, migration, or reconciliation step needs human intervention, record the
   exact observed state, safe next action, owner, and evidence required before resuming.
4. Treat failed recovery or uncertain user/data impact as a Node05-quality and Node07-incident
   concern after the immediate containment decision is complete.

## Post-Deploy Smoke, Watch, and Incident Routing

#### 1. Establish the actual post-deploy target

1. Confirm the environment, URL or endpoint, deployed ref/artifact/version, release
   timestamp, authorized test account/data, provider mode, and expected user-visible change.
2. Verify that deploy status or artifact identity matches the approved source. A green
   workflow alone does not prove the intended artifact reached the intended environment.
3. Select the smallest sufficient smoke matrix from the change and risk:

| Change/risk | Minimum immediate evidence |
| --- | --- |
| static/docs/config | target availability and affected route or configuration check |
| normal feature | availability, primary action, relevant API/data result, logs or error signal |
| frontend surface | affected route, primary action/state, narrow viewport where relevant, console/network |
| auth/tenant/private data | approved account boundary and denial/ownership behavior where safe |
| migration/backfill | expected schema/state checkpoint, compatible read/write, recovery signal |
| provider/job/webhook | safe trigger/status/callback or reconciliation evidence, error signal, first-run watch |
| payment/entitlement | approved non-charging proof or tightly authorized live path, webhook/result evidence |

#### 2. Run smoke deliberately

1. Wait for the target to be ready using the project-defined signal, then inspect the
   rendered or returned state before acting on it.
2. Use non-destructive reads and safe test data by default. Do not charge money, send a
   real message, mutate customer data, or invoke an irreversible provider action without
   specific authorization.
3. For UI paths, inspect the rendered DOM/state, perform the intended interaction, then
   collect console/network evidence and a narrow desktop/mobile check when relevant.
4. For backend, data, job, or provider paths, record the endpoint/status, durable state,
   correlation ID or redacted log signal, and visible outcome. Keep private identifiers out
   of the durable release record.
5. Compare actual results with release expectations. Mark each proof `pass`, `concern`,
   `fail`, or `not run`, with the reason and safe next action.

#### 3. Contain before expanding investigation

1. On a critical failure, preserve the smallest useful evidence first: target/ref,
   timestamps, error output, observed state, and affected user path.
2. Apply the approved least-harmful containment: flag/config disable, job pause, provider
   switch, traffic reduction, rollback, or forward-fix. Do not keep probing a harmful path.
3. For a non-critical failure, reproduce once, compare the nearest working path or prior
   release, trace the data/request boundary, form one hypothesis, and perform the smallest
   authorized verification or repair.
4. Re-run the affected smoke plus nearby regression proof after every repair. Three focused
   attempts that reveal shared coupling, a contract conflict, or an invalid runtime premise
   require a return to Node02/03/04/05 rather than another release patch.
5. A production incident becomes Node07 work after immediate containment, release-state
   capture, and owner routing are complete.

#### 4. Close the immediate watch window

1. Choose watch duration by blast radius: immediate observation for static changes, a
   short log/support window for normal features, and first real event or scheduled run for
   auth, payment, data, provider, or job changes.
2. Watch only the signals that can falsify the release claim: availability, error rate,
   queue/job status, provider failures, support reports, cost/rate signals, or critical path.
3. If the window closes cleanly, hand ongoing health and learning questions to Node07. If it
   does not, maintain containment and route the incident to its implementation, quality, or
   architecture owner.

## Release State, Notes, and Node07 Handoff

#### 1. Update durable truth only when it changed

1. Update the Release/Validation or Control Room region of the HTML project command board only when the
   release, environment behavior, recovery posture, operational dependency, or named concern is durable and
   useful to future work.
2. Preserve stable board facts and its established page ownership. Follow
   `references/agent-context-html/instructions.md`; do not rewrite stable architecture or product pages merely because a release occurred.
3. Use current command output, workflow result, deploy/provider status, and smoke evidence
   as source material. A planned action that was not executed remains a plan, not release state.

#### 2. Write the release record

1. Choose one factual status:

| Status | Meaning |
| --- | --- |
| `PLAN_ONLY` | no external release action occurred. |
| `READY_TO_EXECUTE` | all known gates pass but action awaits authorization. |
| `EXECUTED_AND_VERIFIED` | authorized action and required immediate proof passed. |
| `EXECUTED_WITH_NAMED_CONCERNS` | bounded concern has owner, trigger, mitigation, and watch. |
| `ROLLBACK_OR_DISABLE_ACTIVE` | containment changed the live state and follow-up remains. |
| `BLOCKED` | release cannot safely proceed or resume. |

2. Record: release slice, environment, source ref/artifact, target identity, Node05 and
   CI evidence, executed sequence, migration/provider/config changes, smoke result,
   disable/rollback or forward-fix path, watch window, operator, and next owner.
3. Redact secret values, customer data, private identifiers, vulnerable implementation
   details, payment data, raw provider payloads, and private incident evidence. Link to
   authorized internal evidence where that is safer than reproducing it.
4. Keep `known concerns` concrete: impact boundary, owner, trigger, mitigation, revisit
   condition, and whether Node07 or a previous node owns the follow-up.

#### 3. Write notes that match the reader

1. User-facing notes describe what people can do now, changed behavior, downtime,
   limitations, required action, or an honest known issue. Do not turn internal refactors
   and infrastructure mechanics into product claims.
2. Maintainer notes describe affected modules/contracts/config, source/target, evidence,
   support handling, operational dependencies, recovery controls, and unresolved risk.
3. Group material only when useful: `Added`, `Changed`, `Fixed`, `Security`,
   `Operational`, and `Known concerns`. Preserve prior release history; do not regenerate
   or overwrite it from a release summary.

#### 4. Handoff to Node07

1. Pass the release state, immediate watch result, expected early signals, support or
   incident context, active concern, and explicit revisit trigger to Node07.
2. Route continuing availability, first real usage, scheduled-job outcome, feedback,
   retention, conversion, cost, and experiment learning to Node07.
3. Retain Node06 ownership for a new deploy, rollback, migration execution, or release
   authorization. Node07 may detect the need but does not invent or execute the release action.
