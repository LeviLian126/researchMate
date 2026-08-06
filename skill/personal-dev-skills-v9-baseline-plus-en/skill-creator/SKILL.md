---
name: skill-creator
description: Create or improve agent skills that add real capability without wasting context. Use when designing a new skill, revising an existing skill, improving its trigger description, deciding what belongs in SKILL.md versus references/scripts/assets, auditing a skill for contradictions or token waste, or choosing and running the right level of behavioral evaluation.
---

# Skill Creator

Create skills that make an agent better at a defined class of work. The goal is not a
complete-looking instruction manual. The goal is a reusable capability that improves the
agent's decisions or output enough to justify its context cost.

## Route the current request

First identify the user's actual goal:

| Request | Primary result |
| --- | --- |
| create a new skill | a usable skill folder with clear trigger, workflow, resources, and validation |
| improve an existing skill | a better skill with the same intended capability and fewer failure modes or wasted tokens |
| audit a skill | findings about conflict, confusion, useless text, missing capability, and token value |
| optimize triggering | a description and trigger examples that improve recall without causing adjacent false triggers |
| evaluate behavior | the strongest honest evaluation available for the skill's output type |

Recover intent from the conversation and existing files before asking questions. Ask only when
the missing fact could change the skill's goal, trigger boundary, output contract, resource
design, or evaluation route.

## Design for capability and token value

Before writing, state the capability in one sentence:

> Given [task/context], help the agent produce [observable result] with [important boundary or evidence].

Keep an instruction only when it changes an agent's choice, evidence, output, safety, or
reliability. Remove ordinary model knowledge, motivational prose, duplicated rules, workflow
ceremony, and details that belong to a narrower reference. Explain why a non-obvious rule
matters; use hard constraints only for consequential failures.

Design around these questions:

- **Goal:** What becomes possible or more reliable?
- **Trigger:** When should this skill activate, and what adjacent work should not trigger it?
- **Context:** What facts, conventions, tools, and resources change the result?
- **Boundary:** What must remain explicit, evidenced, or outside the skill's scope?
- **Output:** What artifact, state, decision, or report should the user receive?
- **Freedom:** Which steps need a precise procedure, and which should remain agent judgment?
- **Token value:** Does each section earn its context cost?

Prefer outcome-first instructions over a mandatory sequence. Add a fixed order only when order
affects correctness, safety, reproducibility, or the user's working method. Prefer cohesive
modules and one owner per rule. Use progressive disclosure so the entrypoint routes to only
the reference, script, or asset needed for the current variant.

## Build the skill

### 1. Capture the contract

Recover or establish:

- capability and non-goals;
- trigger contexts and near-miss contexts;
- input and output contract;
- important boundaries and failure modes;
- repository conventions, tools, dependencies, and runtime assumptions;
- what evidence will distinguish a useful result from a plausible-looking one.

For a new skill, create the directory with the repository's supported initializer when one is
available. For an existing skill, inspect and preserve useful current resources instead of
reinitializing the directory.

### 2. Write the smallest effective entrypoint

The frontmatter description is the primary trigger surface. State what the skill does and
when to use it, including concrete contexts and meaningful near-misses. Do not put important
trigger conditions only in the body.

Keep `SKILL.md` focused on the core workflow, routing, boundaries, and output contract. Put
variant-specific knowledge, long examples, schemas, and detailed checklists in references.
Put deterministic or repeatedly rewritten work in scripts. Put reusable output material in
assets. Keep references directly discoverable from the entrypoint or its routed README; avoid
deep reference chains.

Use imperative instructions, but prefer explaining the reason over accumulating MUST/NEVER
rules. Preserve the distinction between ordinary guidance, fragile operations, and hard safety
boundaries.

### 3. Perform the independent skill audit

After the first complete draft, create one independent audit pass using
`agents/skill-auditor.md`. Give it the skill files and the task-local goal, not the intended
diagnosis or expected fixes. It should inspect whether the skill:

1. contains contradictions or priority conflicts;
2. contains wording that can make an agent hesitate, misroute, or misunderstand;
3. contains repetition, ritual, ordinary model knowledge, or low-value prose that can be removed;
4. adds real capability rather than restating what a capable agent already knows;
5. spends tokens in proportion to the improvement it creates;
6. has enough context, boundaries, and output detail to prevent the important failure modes.

The auditor should label each finding with evidence, impact, and one action: keep, clarify,
move to reference, replace with a script/asset, or delete. It should also name useful missing
guidance rather than optimizing only by deletion.

Apply the findings once, using judgment. Do not turn the audit into an automatic rewrite loop.
If a finding changes the user's intended capability, surface that decision instead of silently
choosing.

## Choose evaluation automatically

Evaluation is evidence for a decision, not a ritual. Route it from the kind of result the skill
produces:

### Branch 1: agent-evaluated measurable result

Use the main agent's evaluation when success has clear observable metrics, such as extraction
accuracy, schema validity, file completeness, command success rate, test pass rate, latency,
token usage, or deterministic state transitions. Define the metric, baseline or expected
range, test inputs, and failure interpretation. Use scripts for assertions when possible.

### Branch 2: user-evaluated subjective result

Route evaluation to the user when quality depends mainly on taste, visual judgment, voice,
persuasiveness, product feel, or other human preference, such as frontend design, copywriting,
branding, or editorial tone. Prepare a small representative test set and a clear review frame:
what changed, what the user should compare, and what decision their feedback will inform.

### Optional hybrid

Use both when a result has objective constraints and subjective quality. The agent checks the
hard constraints; the user judges the experience or preference. Do not claim that a measurable
pass proves a subjective result.

If the runtime cannot provide independent controlled runs, do not claim a behavioral benchmark.
Perform the strongest honest static review or example-based check, state the limitation, and
leave a reproducible evaluation set if it will help later.

## Advanced evaluation only when it earns its cost

Use the evaluation references and scripts for larger or higher-risk work:

- baseline comparison when the question is whether the skill improves behavior over no skill or
  an earlier version;
- repeated runs when variance, flakiness, latency, or token cost matters;
- grader, analyzer, or blind comparator when assertions or competing versions need independent
  review;
- the HTML viewer when the user needs to inspect multiple outputs or benchmark dimensions.

Do not create a benchmark, viewer, or multi-agent evaluation merely because the skill-creator
can. A one-shot design plus independent audit and lightweight proof is the default.

Read only the advanced reference needed for the selected route:

| Need | Read |
| --- | --- |
| outcome-first instructions and trigger design | `references/prompt-and-description-design.md` |
| measurable or comparative evaluation | `references/evaluation-and-iteration.md` |
| runtime limitations and honest fallbacks | `references/runtime-adaptations.md` |
| eval, grading, benchmark, and comparison schemas | `references/schemas.md` |
| grade output against assertions | `agents/grader.md` |
| blind comparison | `agents/comparator.md` and `agents/analyzer.md` |
| independent skill audit | `agents/skill-auditor.md` |

## Output contract

Return:

- the skill path and intended capability;
- what changed or was created;
- trigger and near-miss behavior;
- resource routing and any scripts/assets added;
- audit findings applied or intentionally rejected;
- validation actually run and its result;
- evaluation route: measurable, user-evaluated, hybrid, or not run;
- remaining uncertainty and the next useful action.

Do not report a benchmark, user preference, generated artifact, or external action that was not
actually observed. Keep the final report shorter than the work needed to produce the skill.

## Final checks

Run the available skill validator. Check local links and resource routes. Inspect frontmatter,
trigger wording, output contract, and changed files. For a substantial skill, confirm that
large references have a table of contents and that no rule is duplicated across entrypoint and
references. If a script was changed, run it on a representative input. Stop when the skill is
coherent, useful, validated, and the next evaluation would not change the design decision.
