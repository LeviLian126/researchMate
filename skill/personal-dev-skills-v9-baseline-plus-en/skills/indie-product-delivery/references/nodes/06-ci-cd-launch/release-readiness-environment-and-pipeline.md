# Release Readiness, Environment, and Pipeline

Use this guide to establish the exact release target, source artifact, environment and data boundaries, CI/CD controls, credential posture, recovery path, and readiness state. The goal is to make a release reproducible and diagnosable, not to add a permission ceremony around ordinary repository work.

## Sections

- [Release Discovery and Readiness](#release-discovery-and-readiness)
- [Deployment Environment, Pipeline, and CI Controls](#deployment-environment-pipeline-and-ci-controls)

## Release Discovery and Readiness

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

#### 3. Set release status and protect credentials

1. Record the exact action, environment, ref/tag/artifact, commands or workflow inputs,
   and exclusions so the release can be reproduced and audited.
2. Keep credentials, API keys, tokens, and secret values out of commands, logs, artifacts,
   commits, and release records. Use configured secret references and fail clearly when a
   required secret is unavailable; never invent one.
3. Do not override a Node05 blocker or owner route. A release plan may continue while
   evidence is incomplete, but do not claim the release is verified until the evidence exists.
4. Describe readiness with the clearest applicable result:

| Status | Use when |
| --- | --- |
| preparation only | scope, target, Node05 evidence, or release fact is incomplete |
| ready to execute | all required facts and gates are current |
| blocked | a required gate, recovery condition, or release fact is missing or fails |

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
4. Check protected environment, branch/ref policy, required CI checks, deploy role, provider
   account, rollback access, and source/artifact identity before a protected action.

#### 2. Model gate topology and promotion semantics

Model the protected release path explicitly:

    source revision -> build artifact -> required quality aggregate
    -> production promotion/alias -> production smoke

Distinguish artifact construction from promotion to the protected production target. A
provider may construct a candidate before CI finishes, but prevent production promotion,
aliasing, or protected traffic from selecting it until the required aggregate gate passes.
Verify the actual provider behavior; a green build or deployment record alone does not
prove that the intended revision was promoted.

When branch protection or a deployment provider needs one stable external release
contract, expose a stable aggregate gate name. Make it depend on every required quality
job, run even when an upstream job fails, skips, or is canceled, and fail unless every
required result is successful or explicitly not applicable. Keep internal job names,
matrices, and any independently useful required checks free to evolve without silently
changing that external contract.

#### 3. Inspect pipeline and artifact trust

1. Read relevant workflow triggers, jobs, permissions, reusable workflows, action pins,
   deploy scripts, package manager, lockfile, cache behavior, and artifact upload/download.
2. Use least privilege by job. Only a required deploy job receives write/deploy authority;
   untrusted forks, PR titles, branches, issue text, and external payloads cannot reach secrets.
3. Pin or consciously justify third-party actions and remote scripts. Prefer established
   official paths when they match the repository rather than adding a release framework.
4. Require deterministic installation when a lockfile exists, cache keys that cannot cross
   trust boundaries, and an artifact traceable to the approved ref and workflow run.
5. Confirm that a deploy command cannot silently target a different project, environment,
   or stale artifact than the recorded release facts.

| Surface | Minimum evidence |
| --- | --- |
| target | named platform/project/environment and data boundary |
| credentials | secret names, scope, owner, and no untrusted exposure |
| workflow | trigger, permissions, trusted actions/scripts, protected deploy step |
| artifact | approved ref, build identity, workflow run, and target match |
| rollback | access to the previous output, disable control, or approved recovery owner |

#### 4. Design the job graph, cache, and change scope

Run independent quality jobs in parallel and express only real dependencies. Cancel
superseded runs for the same branch or change when doing so cannot interrupt a protected
release action. Key caches with the lockfile, platform, toolchain, and material build
inputs, and do not share writable caches across trust boundaries.

Test path filters in both directions. Confirm that owned source, lockfile, container,
workflow, and deployment-configuration changes trigger their required gates, and that a
docs-only change does not rebuild or restart unrelated services. Never filter out the
workflow or deployment configuration that defines the filter itself. Distinguish CI path
filtering from each deployment provider's independent build filter.

Measure the whole workflow wall time and the critical path, not the sum of parallel job
durations. Record cold-cache and warm-cache observations separately when speed is part of
the release claim; optimize the longest required path before polishing short jobs.

#### 5. Prove new pipeline mechanics in the hosted environment

Static workflow validation and local command success do not prove that a remote action
reference exists, a container image has the assumed entrypoint, or a hosted runner can
execute the job. Before calling a new gate operational:

1. validate syntax, expressions, job dependencies, and aggregate-gate logic;
2. verify remote action, reusable-workflow, image, and tool references exist at the exact
   recorded tag, version, digest, or commit;
3. run the gate on its actual hosted operating system and architecture;
4. read the complete failed step log and preserve the first causal error;
5. after repair, rerun the affected proof and every required aggregate gate.

Verify a newly configured provider check on the next eligible protected deployment. Some
providers expose a check for selection only after a hosted run publishes its exact name,
and some configuration changes apply only to subsequent deployments. Record that
activation boundary rather than claiming the current deployment was retroactively gated.

#### 6. Classify a red, missing, or flaky CI gate

1. Capture workflow/job/step, command, ref, environment, full error, exit result, and
   whether the same command reproduces locally or in a comparable trusted environment.
2. Classify it before repair: workflow/config, dependency/install/cache, lint/type/test,
   build/artifact, deploy permission/secret, application behavior, security/quality, or
   architecture/contract mismatch.
3. Treat a missing required gate as a release blocker until Node05 and the release owner
   explicitly accept an alternative proof. Do not label a check flaky without repeated evidence.
4. Route application defects to Node03/04, sensitive findings to Node05, and contract or
   runtime-shape failures to Node02. Do not hide them by weakening CI.

#### 7. Repair and reprove narrow pipeline mechanics

1. Change only Node06-owned workflow/config mechanics when that repair is part of the
   current task and does not alter product, security, trust, or public behavior.
2. Form one causal hypothesis, apply the smallest change, rerun the affected command, then
   rerun every required release gate from the current source/artifact.
3. Preserve original evidence and record what changed, why it was safe, and which fresh
   output proves the gate now passes.
4. When another focused attempt would add no new evidence, or the evidence exposes shared
   coupling or unclear ownership, stop and return to Node02/03/04/05 rather than
   accumulating pipeline patches.

## Keep source-control actions intentional

Treat commit, push, merge, history rewrite, tag, release, and deployment as distinct actions so the release record can say exactly what happened. Inspect status and the full relevant diff before committing; use focused paths rather than broad staging when unrelated work exists.

Ordinary specified work stays on `main` by default. Create an exploratory branch only when
the result is uncertain enough that easy abandonment is part of the plan or the user asks
for one. Define success before the exploration. Merge the branch only after its behavior,
quality gates, and user-expected outcome are confirmed; otherwise retain useful findings if
needed and discard the code without forcing it into `main`.

Multiple writing agents require independently owned slices, one branch or worktree per writer, and one integration owner. Shared contracts, schemas, core types, or the same files are a signal to serialize the work instead.
