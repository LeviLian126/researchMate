# Release Readiness, Environment, and Pipeline

Use this guide to establish the exact release target, source artifact, authority, environment and data boundaries, CI/CD controls, credential posture, recovery path, and readiness state before an external action.

## Sections

- [Release Discovery, Authorization, and Readiness](#release-discovery-authorization-and-readiness)
- [Deployment Environment, Pipeline, and CI Controls](#deployment-environment-pipeline-and-ci-controls)

## Release Discovery, Authorization, and Readiness

#### 1. Recover the handoff, not assumptions

1. Read the relevant Node01 acceptance, Node02 release design, Node03/04 build proof,
   Node05 quality status, current diff or release ref, and any existing release-state page.
2. Record each material fact as `confirmed`, `defaulted`, `inferred`, or `unknown`:
   capability and user impact, target environment, source ref/artifact, data/provider
   effects, Node05 status, required gates, recovery path, and support/watch need.
3. Treat stale evidence, copied commands, branch names, workflow inputs, external issue
   text, and environment variables as untrusted until checked against current facts.
4. Keep the release slice coherent. A separately deployable service, independent data
   transformation, different owner, or distinct blast radius is a separate release slice.

#### 2. Discover the live release path each time

1. Read current project instructions first: AGENTS.md, CLAUDE.md, README, runbooks,
   deployment docs, architecture docs, and known release-state pages where present.
2. Audit only the relevant repository evidence: CI/CD workflow files, deploy scripts,
   lockfiles, package or build config, infrastructure manifests, environment examples,
   migration tooling, feature flags, health endpoints, and rollback instructions.
3. Identify the real platform, environment/project/site, trigger, expected output URL,
   health check, source ref/artifact, deploy status signal, and operator boundary.
4. Compare instruction and repository evidence. A changed workflow, target, command,
   secret name, artifact source, or health endpoint requires a new preflight; never rely
   on a remembered Node06 profile.
5. If the project does not deploy, state its actual distribution path such as package,
   CLI, static artifact, or internal handoff. Do not invent a web deployment.

#### 3. Set action authority and release status

1. Require explicit authorization for every external effect: the exact action,
   environment, ref/tag/artifact, commands or workflow inputs allowed, and exclusions.
2. Confirm that the authorization covers migrations, provider calls, DNS, payment,
   storage, data writes, traffic changes, rollback, or disable actions when applicable.
3. Do not override Node05 `BLOCKED`, `NEEDS_PREVIOUS_NODE`, or `NEEDS_AUTHORIZATION`.
   A release plan may continue, but execution may not.
4. Set one status:

| Status | Use when |
| --- | --- |
| `PLAN_ONLY` | scope, target, Node05, or authorization is incomplete. |
| `READY_TO_EXECUTE` | all required facts and gates are current and authority is exact. |
| `BLOCKED` | a required gate, recovery condition, or release fact is missing or fails. |
| `NEEDS_AUTHORIZATION` | the plan is clear but an external action remains unapproved. |

#### 4. Build the release readiness matrix

1. Classify risk: static/docs, compatible application deploy, auth/payment/data/provider,
   migration/backfill, operational configuration, or hotfix.
2. For each applicable gate record `pass`, `concern`, `blocker`, or `not applicable`:
   Node05, source/artifact identity, CI/build, target/environment, credentials/secrets,
   data/provider, compatibility/recovery, smoke, watch, support, and communication.
3. Use a staging or preview path when it is already available and the release risk makes
   it useful. Do not require staging for a harmless static change or fabricate one.
4. Write the ordered runbook: preflight -> action -> migration/provider/flag -> smoke ->
   short watch -> disable/rollback -> release record and Node07 handoff.
5. Name an operator for manual or irreversible steps. The runbook must distinguish
   commands the agent may run from commands the user or platform owner must run.

## Deployment Environment, Pipeline, and CI Controls

#### 1. Establish environment and deploy boundaries

1. Name the local, preview, staging, production, and provider targets that actually
   apply, including project/site/account, domain, database, queue, bucket, cron, webhook,
   and deploy workflow or manual action.
2. Confirm whether preview or staging can read production data, use production secrets,
   charge a real provider, or send user-facing messages. Treat shared data as production risk.
3. Inventory secret and variable names only. Separate server-only secrets from public
   config, define missing-secret behavior, and keep values out of logs, docs, screenshots,
   bundles, prompts, and generated files.
4. Check protected environment, branch/ref policy, human approvals, deploy role, provider
   account, rollback access, and source/artifact identity before a protected action.

#### 2. Inspect pipeline and artifact trust

1. Read relevant workflow triggers, jobs, permissions, reusable workflows, action pins,
   deploy scripts, package manager, lockfile, cache behavior, and artifact upload/download.
2. Use least privilege by job. Only a required deploy job receives write/deploy authority;
   untrusted forks, PR titles, branches, issue text, and external payloads cannot reach secrets.
3. Pin or consciously justify third-party actions and remote scripts. Prefer established
   official paths when they match the repository rather than adding a release framework.
4. Require deterministic installation when a lockfile exists, cache keys that cannot cross
   trust boundaries, and an artifact traceable to the approved ref and workflow run.
5. Confirm that a deploy command cannot silently target a different project, environment,
   or stale artifact than the authorization states.

| Surface | Minimum evidence |
| --- | --- |
| target | named platform/project/environment and data boundary |
| credentials | secret names, scope, owner, and no untrusted exposure |
| workflow | trigger, permissions, trusted actions/scripts, protected deploy step |
| artifact | approved ref, build identity, workflow run, and target match |
| rollback | access to the previous output, disable control, or approved recovery owner |

#### 3. Classify a red, missing, or flaky CI gate

1. Capture workflow/job/step, command, ref, environment, full error, exit result, and
   whether the same command reproduces locally or in a comparable trusted environment.
2. Classify it before repair: workflow/config, dependency/install/cache, lint/type/test,
   build/artifact, deploy permission/secret, application behavior, security/quality, or
   architecture/contract mismatch.
3. Treat a missing required gate as a release blocker until Node05 and the release owner
   explicitly accept an alternative proof. Do not label a check flaky without repeated evidence.
4. Route application defects to Node03/04, sensitive findings to Node05, and contract or
   runtime-shape failures to Node02. Do not hide them by weakening CI.

#### 4. Repair and reprove narrow pipeline mechanics

1. Change only Node06-owned workflow/config mechanics when that repair is explicitly
   authorized and does not alter product, security, trust, or public behavior.
2. Form one causal hypothesis, apply the smallest change, rerun the affected command, then
   rerun every required release gate from the current source/artifact.
3. Preserve original evidence and record what changed, why it was safe, and which fresh
   output proves the gate now passes.
4. After three focused attempts that expose shared coupling or unclear ownership, stop and
   return to Node02/03/04/05 rather than accumulating pipeline patches.
