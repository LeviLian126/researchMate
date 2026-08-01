# Ops, Learning, and Iteration

Recover what shipping actually told you, distinguish incidents from learning, and decide the next slice from evidence rather than optimism.

## Sections
- [Recover the actual release context](#recover-the-actual-release-context)
- [Signal integrity](#signal-integrity)
- [Health, triage, and containment](#health-triage-and-containment)
- [Pair numbers with concrete evidence](#pair-numbers-with-concrete-evidence)
- [Customer value, funnel, and routing](#customer-value-funnel-and-routing)
- [Experiments and the next slice](#experiments-and-the-next-slice)
- [Operating checkpoint and review](#operating-checkpoint-and-review)

## Recover the actual release context

Start from what shipped and what the launch watch recorded, not from the plan — the plan says what you meant to do, the log says what happened. Identify the version, the scope that went out, the expected and observed signals, the named concerns from release, and the known instrumentation gaps. Ask the one decision-changing question first — "is users' money, data, privacy, or access safer now than before, and how do I know?" — before investigating the rest.

## Signal integrity

Build a minimal signal card for the questions that actually matter; resist instrumenting everything. Tag each signal by evidence quality (the meaning table lives in `references/methods.md`: observed / estimated / self-reported / incomplete), because the claim you're allowed to make depends on it — an estimated metric is a hypothesis, not a fact.

When instrumentation is missing, say so and route the fix rather than filling the gap with an inference; a number you can't trace is worse than an admitted gap. Distinguish an incident (something broke that needs containing) from a learning candidate (something happened that's worth understanding) — they get different responses.

## Health, triage, and containment

Establish current health from real signals, then triage by severity. Severity routing (SEV0–SEV4) lives in `references/methods.md`; the key discipline is the same as release: **contain before broad analysis** — if users are being harmed, stop the harm (rollback, disable, route-around) before investigating why. Investigation that runs while harm continues is a second incident.

After containment, investigate systematically: reproduce from the actual state, narrow to the smallest failing case, fix the cause rather than the symptom, and verify the fix before closing. Turn repeated support on the same issue into a learning candidate rather than treating each report as novel.

## Pair numbers with concrete evidence

A number alone is a claim; pair it with the evidence behind it and the limitation on it. "Activation up 30%" needs the cohort, the window, and the denominator; "churn dropped" needs what churn means here and over what period. Without the pair, the number is a story you're telling yourself. Keep inferred claims visibly marked as inferred, and when sources disagree, show the conflict and lower confidence rather than silently picking one.

## Customer value, funnel, and routing

Synthesize value by job and by contradiction — what people *did* matters more than what they *said*, and a contradiction between behavior and claim is the most informative signal you have. Follow the smallest useful value path: pick the funnel step that's actually broken.

| Symptom | Likely first owner |
|---|---|
| traffic but no trust action | market/positioning (Node 01) or frontend (Node 04) |
| signup but no activation | frontend (Node 04) or backend (Node 03) |
| activation but no repeat use | market (Node 01) or an experiment here |
| retention but no purchase | market pricing/promise (Node 01), then frontend (Node 04) |
| checkout/payment failure | backend (Node 03), quality (Node 05), and release (Node 06) |
| high use with provider cost spike | architecture (Node 02), backend (Node 03), and this watch |
| users doubt safety or legitimacy | market (Node 01), frontend (Node 04), quality (Node 05) |

The owner column points at which topic may help — read whichever is relevant, in any order. It isn't a sequence or a ticket-routing system; it's "where the answer probably lives."

## Experiments and the next slice

Choose the decision path that fits the question:

| Decision need | Path |
|---|---|
| "is this worth building at all" | the smallest test that changes the build/no-build decision, not the most rigorous one |
| "which variant wins" | one metric you'd act on, defined before you run it |
| "where's the bottleneck" | instrument the suspected step, or a cheap qualitative proxy first |
| "what should we do next" | the learning that most changes the next decision, weighted by cost and reversibility |

Design one experiment at a time — the question, the metric and its threshold decided *before* running, how you'll read both outcomes (including a null), and what each outcome would change. Execute a safe direct action only when authorized (production changes are external effects). Read the result honestly: a no-effect is a result, not a failure to be explained away.

Turn the evidence into one next slice: the smallest move that's worth shipping, with its acceptance, risk, and the signal you'll watch. Don't preserve every learning in current-state docs — only what's durable; routine observations belong in the decision, not the artifact.

## Operating checkpoint and review

Write a current operating checkpoint: what shipped, the health state and confidence behind it, the open concerns with their triggers, and the prioritized next actions. Run a focused founder review of the decision, not a status theater. Revalidate prior learning only when a new signal, a contradiction, or a changed assumption makes it suspect — don't re-litigate settled decisions on a schedule.

State confidence 0–100% and, below 70%, name the missing facts that would change the next decision (the mechanism lives in `references/methods.md`). Keep inferred or self-reported claims marked; don't promote an estimate to observed because it would be convenient.
