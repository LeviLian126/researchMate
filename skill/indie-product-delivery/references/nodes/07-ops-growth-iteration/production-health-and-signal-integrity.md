# Production Health and Signal Integrity

Use this guide to recover what actually shipped, validate operational signals, distinguish incidents from learning questions, and route active harm before analysis or experiments.

## Sections

- [Post-Launch Discovery and Signal Integrity](#post-launch-discovery-and-signal-integrity)
- [Health, Incident, and Recovery Routing](#health-incident-and-recovery-routing)

## Post-Launch Discovery and Signal Integrity

#### 1. Recover the actual release context

1. Read the Node06 release-state record, source/target, immediate watch result,
   known concerns, rollback or disable posture, expected early signal, support path,
   and any Node05 limitation that remains relevant after release.
2. Classify current mode: immediate post-release watch, stable operating review,
   active incident/support investigation, learning question, experiment readout, or
   periodic founder review.
3. Record facts as `confirmed`, `defaulted`, `inferred`, or `unknown`. A planned
   rollout, assumed adoption, stale dashboard, or remembered metric is not current fact.
4. Stop growth analysis when a release concern, critical path, payment, provider, job,
   privacy, or data-integrity signal suggests active harm.

#### 2. Ask one decision-changing question

1. State the decision before opening a dashboard: what should continue, stop, change,
   investigate, or be built next if the evidence moves in either direction?
2. Name the target segment, user job, release/source context, cohort rule, time window,
   baseline or comparison, expected value signal, and safety guardrail.
3. Prefer a question that can change a near-term decision. "How is everything doing?"
   is a prompt for a wide scan, not a claim or experiment objective.
4. Keep acquisition, activation, retention, conversion, support, and cost separate
   until evidence supports a causal connection.

#### 3. Build the minimal signal card

Use this record before making a post-launch claim:

`decision question -> cohort/time window -> signal or evidence -> source -> confounds -> confidence -> owner -> next action`

| Evidence quality | Meaning | Appropriate claim |
| --- | --- | --- |
| observed | dated event, trusted log, provider record, or reproducible path | state the measured result and scope |
| estimated | incomplete count, proxy, or manually reconstructed sample | state the estimate and its limitation |
| self-reported | user, support, sales, or founder statement | state who reported it, not that it is universal |
| incomplete | missing event, inaccessible source, or insufficient sample | state the gap and route instrumentation/research |

1. Note confounds such as release age, traffic source, cohort mix, seasonality, support
   intervention, incident, external campaign, sample size, or provider changes.
2. Pair a rate or count with at least one concrete account/session/support example when
   safe and proportionate. Redact private identifiers from durable records.
3. Do not force a score, precision, trend, or causal story when the source cannot support it.

#### 4. Work safely with missing instrumentation

1. Inspect safe existing evidence first: critical path, logs, provider/job status,
   support themes, redacted session evidence, sales notes, refund/churn reasons, and
   a small number of opt-in interviews.
2. Define the smallest missing measurement as actor, object, event, safe properties,
   timestamp, storage/retention, owner, and privacy boundary.
3. Route event schema, consent, identity, or retention design to Node02; backend capture
   to Node03; frontend interaction capture to Node04; quality/security evidence to Node05.
4. Until that route produces evidence, use `NEEDS_INSTRUMENTATION` or
   `NEEDS_USER_RESEARCH`, not a confident product conclusion.

## Health, Incident, and Recovery Routing

#### 1. Establish current health

1. Recover the Node06 handoff, release state, current environment, dependencies, known
   concerns, expected watch signal, support channel, and rollback/disable authority.
2. Check only signals that can change an operating decision: primary user path,
   availability, error/correctness, felt latency, job/webhook success, payment integrity,
   data durability, provider quota/cost, and support burden.
3. Use existing project tools and raw outputs. Mark unavailable sources `unknown` or
   `skipped`; do not replace them with a generic health score.
4. Alerts must imply a concrete action. Curiosity or long-term observation belongs in a
   later review, not an immediate incident gate.

#### 2. Triage impact and assign severity

1. Classify the problem and its boundary: active user harm, security/privacy, primary
   path/auth/payment/data failure, degraded important path/support spike, minor UX bug,
   or low-priority edge case.
2. Record affected segment/path, first known time, release/provider/job context, observed
   evidence, current user impact, and containment authority. Keep customer identifiers,
   secrets, payment details, and raw private payloads out of durable docs.
3. Use a short severity model:

| Severity | Meaning | First route |
| --- | --- | --- |
| `SEV0` | security, privacy, data, or billing integrity risk | Node05 and Node06 immediately |
| `SEV1` | primary path, auth, payment, or data failure | Node06 containment, then Node03/04/05 |
| `SEV2` | important degradation, provider/job failure, support spike | owner repair with active watch |
| `SEV3` | minor bug, trust/UX confusion, bounded workaround | Node03/04 or Node01 evidence route |
| `SEV4` | low-impact edge or isolated request | classify, park, or add to learning review |

#### 3. Contain before broad analysis

1. For `SEV0`/`SEV1`, preserve redacted evidence and call the Node06 release workflow for
   authorized disable, rollback, job pause, provider switch, or traffic control.
2. Node07 may acknowledge impact and prepare safe support context, but it never deploys,
   rolls back, changes production configuration, or edits provider state.
3. Route implementation to Node03/04, quality/security proof to Node05, and contract,
   recovery, or shared runtime uncertainty to Node02.
4. Communicate only confirmed impact, safe workaround, next update owner/time, and any
   required customer action. Do not promise a root cause or recovery time without evidence.

#### 4. Investigate systematically after containment

1. Reproduce safely when possible, read the complete error, compare the nearest working
   path or prior release, and trace the relevant request/data/provider boundary.
2. State one hypothesis: "I think X caused Y because Z." Choose the smallest evidence
   collection or authorized repair that could disprove it.
3. Recheck the affected path and adjacent regression after each change. Preserve original
   evidence and distinguish a symptom workaround from root-cause resolution.
4. After three focused attempts expose shared coupling, a contract conflict, or a false
   runtime premise, stop local repair and return to Node02/03/04/05.

#### 5. Turn repeated support into a learning candidate

1. Group resolved or bounded reports by user job, segment, frequency, impact, workaround,
   cost, and underlying cause, not by request wording alone.
2. A single report may remain support work. Repeated, costly, or behavior-changing evidence
   can enter customer synthesis or a next-slice decision after health is stable.
