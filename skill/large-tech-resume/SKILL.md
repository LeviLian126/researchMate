---
name: large-tech-resume
description: "Create evidence-driven, technically deep resumes for big-tech backend, AI full-stack, LLM application, Agent, RAG, and software-engineering roles from real job descriptions and repository evidence. Use when analyzing a project for resume positioning, improving preview.md/cv.md, validating resume claims, or planning project upgrades to close JD gaps."
---

# Large-Tech Engineering Resume

## Goal

Turn real hiring requirements and a project's verifiable implementation into two ready-to-use artifacts:

- `resume/preview.md`: the evidence ledger, JD-to-project reasoning, uncertainty register, measurement plans,
  and an improvement roadmap;
- `resume/cv.md`: complete role-specific project sections that can be submitted directly, without asking the
  user to select bullets from a candidate pool.

The purpose of metrics is to prove technical depth, difficulty, correctness, scale, or measurable change. A
number that does not explain why the engineering matters is noise and must be removed. The target reader is a
big-tech engineering interviewer, not a project-status reviewer.

## Context to inspect

Read only the sources that can change the resume's truth or positioning, then follow their evidence to code:

1. Repository instructions and current source, tests, configuration, migrations, deployment and runtime traces.
2. `resume/JD.md`: current market abstraction and its cited enterprise recruitment sources. Treat it as the
   JD model, not as evidence that this project implemented every listed technology.
3. Existing `resume/preview.md`, `resume/cv.md`, and any prior prompt only as revision history; replace weak
   rules rather than inheriting their candidate-pool behavior.
4. Maintained product/architecture docs and real production or benchmark observations, checking dates and
   stale-status markers before using them.

Separate four things throughout the work:

| Layer | Question | Allowed conclusion |
|---|---|---|
| JD abstraction | What do real roles screen for? | Rank role competencies and vocabulary |
| Project implementation | What mechanism exists in this repository? | Claim an implemented design or boundary |
| Measured outcome | What changed under a known test or runtime condition? | Claim a result with baseline, method and scope |
| Future plan | What would close a gap? | State an estimate and verification plan, never a completed result |

## Evidence and number discipline

Build an evidence ledger before writing bullets. Every substantive claim must have a source, an evidence class,
and a boundary describing what it does not prove.

- **Measured**: before/after, latency distribution, QPS, recall/precision, failure rate, cost, recovery time,
  or efficiency measured with a named method, environment, sample and baseline.
- **Static implementation**: a source path, test, migration or configuration proves a mechanism exists. It does
  not prove adoption, performance improvement, scale, or production reliability.
- **User-confirmed**: ownership, dates, role, public status or an outcome explicitly supplied by the user.
- **Estimated target**: an optimistic planning hypothesis for a missing result. Put it in `preview.md` with a
  confidence note and a concrete test plan; never present it as achieved in `cv.md`.

Do not use bare counts as achievements. API paths, schemas, tests, files, queues, migrations, MCP tools and
similar counts may appear only when they explain a meaningful contract, isolation boundary, workload shape or
verification surface. “Implemented 46 APIs” is not a technical highlight. Prefer the problem and mechanism:
“made asynchronous evidence runs idempotent across HTTP, outbox and worker retries, then verified duplicate
delivery leaves one terminal state.”

Every proposed metric must answer at least one of: what bottleneck changed, what correctness property was
protected, what failure boundary was exercised, what scale was sustained, or what decision the measurement
enabled. If the data is missing, estimate an optimistic target only as a hypothesis and define:

`subject → baseline/control → tool and environment → workload/sample → metric → acceptance threshold → artifact`

Never invent a denominator, user population, traffic volume, improvement percentage, production result or
business impact merely to make a bullet impressive.

## JD-to-project reasoning

Use `JD.md` to build a compact role model, then map each role to the project's strongest demonstrated mechanisms.
Supported role lenses include AI full-stack, LLM application, Agent/RAG, backend/platform, and AI quality/AI
coding. Do not force every role or every JD keyword into the output.

For each role, decide:

1. Which business/problem context is closest to the JD;
2. Which two or three mechanisms demonstrate engineering depth;
3. Which reliability, security, performance or evaluation boundary makes the work interview-worthy;
4. Which result is measured, which is only implemented, and which gap remains;
5. Which simple project upgrade would produce the highest-value new evidence.

Use the JD's wording to choose recognizable concepts, but do not copy requirements into the resume. The project
implementation is the proof; the JD only determines relevance and ordering.

## Workflow

### 1. Establish the technical story

Trace the project's meaningful end-to-end paths: input and state, core decision, data/queue/provider boundary,
failure handling, observability, and user-visible result. Identify the hardest engineering decision and the
trade-off behind it. Distinguish a real workflow from a library that is merely installed. For AI systems, verify
whether “Agentic” means bounded planning/tool/state transitions or only retrieval, reranking and generation.

### 2. Build the preview ledger

Write `resume/preview.md` with these sections:

1. **Positioning** — one accurate project definition and the role lenses it can support.
2. **JD capability matrix** — requirement, why it matters, project proof, strength, missing proof and best
   expression. Keep generic JD abstraction separate from project implementation.
3. **Technical chain** — the few business/engineering flows that carry the story, including key alternatives,
   invariants and failure branches.
4. **Evidence ledger** — source, claim, class, scope and prohibited inference.
5. **Data and measurement** — measured results first; static mechanisms second; optimistic estimates clearly
   marked with a test plan.
6. **Role narratives** — one ranked, complete set of technically deep bullets per supported role. Do not create
   interchangeable bullets simply to increase choice or count.
7. **Gap analysis** — what the JD asks for that the project does not yet prove.
8. **Three-tier upgrade plan** — required below.
9. **Interview defense** — the problem, decision, trade-off, verification and redesign answer for each high-value
   claim.

### 3. Create the improvement roadmap

Append a section that ranks upgrades from easy to hard, not by keyword quantity but by evidence gained:

| Tier | Meaning | Each item must include |
|---|---|---|
| Easy / days | Reuses current contracts and can produce a new artifact quickly | gap, minimal change, optimistic target, test method, acceptance artifact |
| Medium / about a week | Crosses modules or adds a real production-quality boundary | architecture impact, migration/rollback, measurable comparison, JD coverage |
| Hard / multi-week | Changes system capability or operating model | staged design, dependencies, risk, load/security/evaluation plan and go/no-go evidence |

Prefer upgrades such as a retrieval benchmark, feedback-to-Bad-Case loop, release evaluation gate, recovery
drill, or performance artifact when they are genuinely compatible with the code. Do not add Multi-Agent,
Kubernetes, WebSocket, caching or model training only to match a keyword. Each plan item must say how its
optimistic estimate will be tested; an estimate is not a resume accomplishment until measured.

### 4. Produce the final CV

Write `resume/cv.md` immediately after the preview is internally consistent. Include complete, role-specific
project versions for every supported target role; each version has project name/date/role, one-line problem
definition, a focused stack line, and 3–5 complementary bullets. The file must be directly usable: no “choose
one,” no evidence IDs, no source paths, no unresolved placeholders, no test plans, and no unmeasured numbers.

The same project may be described differently by role, but never with contradictory facts. Keep a measured result
only when its method and scope are known. When a gap has no measured outcome, describe the verified mechanism and
its protected property rather than a speculative percentage.

## Bullet standard

Write each bullet around one consequential engineering decision:

`problem/context → action and mechanism → affected object/flow → verified result or protected property`

Prefer design depth over inventory. Mention the algorithm, state transition, consistency model, isolation rule,
failure policy, benchmark comparison or observability boundary that makes the work non-trivial. A useful bullet
lets an interviewer ask “why this design, what failed, and how did you prove it?”

Use the quality example in [references/quality-example.md](references/quality-example.md) as a style reference:
it combines a concrete business problem, named mechanism, meaningful scope and a measured before/after result.
Do not copy its numbers or pretend this project has the same scale.

## Boundaries

- Do not turn dependency presence, route count, test count, deployment existence or a demo mock into a result.
- Do not claim ownership, users, scale, performance, accuracy, cost savings or production behavior without
  evidence or explicit user confirmation.
- Do not call a sequential retrieve–rerank–generate path Agentic; reserve the term for the bounded planning,
  state, tool, review or recovery workflow that is actually implemented.
- Do not let JD keywords override the repository's real architecture or invent missing subsystems.
- Do not make the user select bullets after the skill runs. Resolve the ranking using JD relevance, technical
  depth, evidence strength and interview value, then deliver complete CV variants.
- Continue autonomously unless the user explicitly requests a plan/grill/approval or a critical ambiguity cannot
  be discovered and would change the role, ownership or public claim. In the latter case, state the assumption,
  proceed with a safe bounded version, and record the proof gap in `preview.md`.

## Final audit

Before handoff, verify:

1. `preview.md` and `cv.md` are the only required output artifacts and both reflect the same source facts;
2. every CV bullet has a concrete problem, mechanism and supported outcome/property;
3. no standalone inventory metric remains;
4. every estimate is labeled and paired with a reproducible measurement plan in preview;
5. role variants prioritize different JD needs without contradicting one another;
6. the three-tier roadmap is ordered by effort and evidence value;
7. stale docs, demo-only paths and unverified production claims are not presented as current proof.
