# Customer Evidence, Experiments, and Next Slice

Use this guide once health is stable to synthesize customer value evidence, choose a bounded experiment or next slice, and preserve the resulting operating decision without creating a history dump.

## Sections

- [Customer Value, Funnel, and Evidence Synthesis](#customer-value-funnel-and-evidence-synthesis)
- [Experiments, Next Slice, and Founder Decision](#experiments-next-slice-and-founder-decision)
- [Ops Learning State and Review Handoff](#ops-learning-state-and-review-handoff)

## Customer Value, Funnel, and Evidence Synthesis

#### 1. Define the question and cohort

1. Restate target segment, user job/pain, product promise, activation definition,
   time-to-value, retention or conversion expectation, and relevant trust guardrail.
2. Ask one decision question and select a cohort by launch, source, plan, segment,
   onboarding path, feature exposure, account age, or a clearly stated manual sample.
3. State the comparison and limitation: baseline, prior cohort, working path, or no
   comparison available. Do not combine unlike cohorts to create a convenient narrative.

#### 2. Follow the smallest useful value path

1. Inspect only the path needed for the question: acquisition -> intent -> signup ->
   activation/time-to-value -> repeat/retention -> conversion -> expansion/referral ->
   churn/refund/support.
2. Use trust, provider cost, support burden, or workflow replacement as value signals
   when they matter to this product. Do not require a full funnel for every decision.
3. Separate acquisition mismatch, comprehension/trust friction, UX friction, missing
   value, pricing hesitation, reliability defect, and provider-cost problem before routing.

| Symptom | Likely first owner |
| --- | --- |
| traffic but low trust action | Node01 or Node04 |
| signup but no activation | Node04 or Node03 |
| activation but no repeat use | Node01 or Node07 experiment |
| retention but no purchase | Node01 pricing/promise review, then Node04 |
| checkout/payment failure | Node03, Node05, and Node06 |
| high use with provider cost spike | Node02, Node03, and Node07 watch |
| users doubt safety or legitimacy | Node01, Node04, and Node05 |

#### 3. Pair numbers with concrete evidence

1. Collect only safe, relevant sources: dated analytics, logs, support, opt-in interviews,
   sales notes, reviews, community discussion, churn/refund reasons, usage records, and
   carefully scoped public market evidence when current conditions matter.
2. Pair rates/counts with concrete sessions, accounts, workarounds, or user language. A
   number can identify where to look; it rarely explains why by itself.
3. Record evidence source, date, segment, sample limitation, privacy handling, and whether
   it is observed, estimated, or self-reported.
4. Never store raw PII, private conversations, payment details, confidential prompts, or
   customer content in durable project state.

#### 4. Synthesize by job and contradiction

1. Group evidence by job/pain, failed outcome, workaround, trigger, willingness to pay,
   and affected segment rather than by the requested feature label.
2. Evaluate behavior, money, frequency, urgency, cost, segment fit, and contradiction.
   Paid/renewed/migrated/invited behavior is stronger than a single request or praise.
3. Name plausible alternatives: wrong traffic, seasonality, onboarding novelty, recent
   release regression, support intervention, sample bias, or a different user job.
4. Classify the result: bug, UX confusion, docs/onboarding, trust, missing value, pricing,
   opportunity, research gap, park, or reject. A conclusion without discriminating evidence
   becomes a hypothesis, not a roadmap item.

## Experiments, Next Slice, and Founder Decision

#### 1. Choose the right decision path

1. Confirm health is stable, the segment and question are defined, and available evidence
   can distinguish an experiment from a known defect or missing product decision.
2. Use an experiment for uncertainty about message, channel, onboarding comprehension,
   manual delivery, support/docs, willingness to engage, or a bounded behavior change.
3. Route directly instead when the work is a confirmed bug, security concern, payment/data
   risk, architecture issue, release concern, or product-scope decision.
4. A pricing, positioning, target user, product promise, or material business-model change
   always re-enters Node01 before an experiment proceeds.

#### 2. Design one experiment

1. Write: `If we change X for segment Y, signal Z should move because R.`
2. Define the current baseline or absence of baseline, allowed change, success metric,
   guardrail, cohort, duration or sample caveat, stop/kill condition, readout time, and owner.
3. Select only one primary change: onboarding wording, documentation, opt-in research,
   manual concierge, support macro, a limited channel message, or a pre-approved product
   surface routed to its implementation owner.
4. Guardrails may include error/support burden, refund/churn, cost, latency, trust,
   accessibility, consent, and target-user harm. An experiment must have a stop path.
5. Do not bundle variables. If a multi-step change is unavoidable, label it exploratory and
   do not infer a single causal conclusion.

#### 3. Execute a safe direct action only when authorized

Node07 may execute only an explicitly authorized action that is all of the following:

- reversible, low-volume, non-code, and non-destructive;
- free of PII, payment, pricing, contract, production configuration, and provider side effects;
- truthful, opt-in where user contact is involved, and consistent with the existing promise;
- bounded by named audience, channel, duration, owner, stop condition, and readout.

Examples: a support macro trial, a documentation experiment, a manual concierge offer,
an opt-in interview invitation, or a limited channel message. Route website/page changes
to Node04, product behavior to Node03/04, instrumentation to Node02/03/04, and release
or provider actions to Node06.

Never send spam, scrape private data, impersonate people, make unapproved claims, use
dark patterns, charge users, alter price/entitlement, or convert a manual trial into an
unreviewed automation.

#### 4. Read the result honestly

1. Compare observed result and guardrails with the original hypothesis, cohort, baseline,
   and known confounds. Collect a short qualitative sample when it explains the behavior.
2. Choose one result: continue, expand, revise, narrow, pause, kill, revert, or route.
3. Do not call an inconclusive sample a win or loss. State whether the experiment reduced
   uncertainty, what remains unknown, and the smallest next evidence needed.

#### 5. Turn evidence into one next slice

1. Rank active harm, security/privacy, activation/payment integrity, support/retention,
   willingness to pay, provider cost/reliability, strategic wedge, then polish.
2. Create a single handoff with source/evidence, desired outcome, owning node, size/risk,
   non-goals, acceptance or success signal, and revisit trigger.
3. Park only with a concrete trigger such as repeated demand, paid pilot, metric threshold,
   interview proof, risk reduction, or time. Reject misaligned, competitor-only, or
   disproportionate work openly.

## Ops Learning State and Review Handoff

#### 1. Update durable state only when facts changed

1. Use the existing HTML project command board and output ownership: keep operations, growth, and release
   facts in their owning board regions; use a concise traceability note only when it is necessary.
2. Update durable pages when health, incident posture, customer evidence, experiment result,
   next decision, active concern, or owner materially changed. Do not rewrite stable product
   or architecture pages merely because an operating review occurred.
3. Preserve stable board facts and avoid a parallel roadmap page, gstack JSONL
   memory, personal builder profile, or another parallel project notebook.

#### 2. Write a current operating checkpoint

1. Record release/context, health status, affected users or segment, decision question,
   evidence sources and quality, confidence, experiment state, decision, owner/route,
   active concern, revisit trigger, and next review timing.
2. Use the status vocabulary that fits the current fact: `HEALTHY`, `WATCH`, `INCIDENT`,
   `MITIGATED`, `NEEDS_INSTRUMENTATION`, `NEEDS_USER_RESEARCH`, `LEARNING_FOUND`,
   `EXPERIMENT_ACTIVE`, `NEXT_SLICE`, `PARKED`, `REJECTED`, or `BLOCKED`.
3. Say `owner missing` or `signal unavailable` when true. Never imply automated monitoring
   or a resolved decision without an actual owner and fresh evidence.
4. Redact customer names, emails, IDs, payment information, private content, provider
   payloads, prompts, and confidential support context.

#### 3. Run a focused founder review

1. Use a periodic review only when it produces a decision. Recover the previous checkpoint,
   release context, health/incident changes, customer evidence, experiment readout, support
   themes, cost/reliability concerns, and accepted/parked/rejected work.
2. Identify meaningful trend or regression using comparable windows and source quality;
   do not create a fixed health score or code-quality retrospective by default.
3. End with one of: keep watching, instrument/research, run one experiment, route one next
   slice, revise product premise, contain an incident, or explicitly defer with a trigger.

#### 4. Revalidate prior learning

1. Before relying on an older insight, check whether its release, cohort, source, product
   behavior, customer segment, or market condition is still applicable.
2. Flag stale learning when its supporting source disappeared, the product changed, or a
   newer result contradicts it. Retain the current confidence and reason rather than deleting
   useful uncertainty.
3. Resolve contradiction by collecting discriminating evidence, narrowing the claim to its
   cohort/time window, or routing a research/instrumentation question. Do not average opposing claims.

#### 5. Handoff deliberately

1. Pass the smallest sufficient context to the owning node: evidence, decision, outcome,
   non-goals, risk, acceptance/success signal, constraints, and revisit trigger.
2. Route continuous operational observation to a real owner or approved automation. Node07
   does not promise background monitoring between sessions.
3. Preserve Node06 authority for any new release action, Node05 authority for quality/ship
   status, and Node01 authority for changed product truth.
