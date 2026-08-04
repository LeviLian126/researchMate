# OpenAI prompting reference note

## Provenance and archive boundary

- Official page: https://learn.chatgpt.com/docs/prompting
- Official Markdown endpoint: https://learn.chatgpt.com/docs/prompting.md
- Retrieved for analysis: 30 July 2026
- Redistribution status: no open-source license was verified for this page.

The full official page is therefore not vendored in this repository. This file preserves a detailed structural summary and the canonical URLs. Re-fetch the official Markdown endpoint when current wording matters.

## Core prompting model

The page presents four optional ingredients rather than a rigid syntax:

- **Goal:** the outcome or change the user wants.
- **Context:** facts and sources that can alter the result.
- **Output:** the audience, format, length, or detail level that makes the result usable.
- **Boundaries:** facts to preserve, actions to avoid, and points requiring review before external impact.

It recommends leading with the result. Specify a process only when the process itself matters; otherwise let the model choose and revise its approach. Short prompts are often enough, and follow-ups are part of the normal workflow.

## Choosing useful context

The page distinguishes context by task:

- Attach documents, spreadsheets, presentations, or PDFs for summarization, comparison, transformation, and file creation.
- Add screenshots or diagrams when visual detail changes the task, and identify the relevant region or behavior that the image cannot show.
- Request Web search and source links when information must be current or independently checked.
- Use a Project when related chats should share files, sources, or a local folder.
- For connected sources, name the system and the kind of evidence to find rather than prescribing every search.
- Plugins provide reusable instructions and tool connections; availability depends on the product surface, plan, workspace, and enabled plugin.
- Put cross-chat preferences in personalization, while keeping one-task facts and constraints in the current prompt.

## Boundaries, readiness, and review

Good boundaries prevent concrete harm or rework: preserve approved values, constrain sources or budget, flag gaps instead of guessing, and draft rather than send when another person is affected. The guide favors one or two consequential boundaries over micromanaging every internal step.

Explain how the deliverable will be used so the model can choose organization and depth. For important work, ask for a final check tied to objective completeness—such as owners and dates, agreement across generated files, link validity, or an explicit list of unverified information—and then review before sharing.

## Follow-up behavior

Refinement can add evidence, correct direction, request another option, or change detail without restarting. While Codex is running:

- steering modifies the active run when the correction should affect current work;
- queuing saves a follow-up for the next run.

The desktop and CLI expose different controls, so a durable skill should describe the semantic choice rather than hard-code one shortcut.

## Chat and ChatGPT Work

The page routes quick questions, brainstorming, short rewrites, and lightweight drafts to Chat. It routes multi-source, multi-step, tool-using, change-making, recurring, or larger deliverable work to ChatGPT Work.

For Work, start with one reviewable result, limit sources/date ranges, define audience and output, separate requirements from optional polish, and require approval before sending, publishing, or changing shared information. Refine a recurring workflow in an ordinary chat before scheduling it; use an in-chat schedule when continuity matters and a standalone schedule when every run should begin fresh.

Its Work examples cover turning several source files into mutually consistent deliverables, researching a purchase decision with current sources and assumptions, and coordinating a launch with owners, dependencies, risks, drafts, and missing-decision checks.

## Codex-specific guidance

A useful coding prompt names behavior, relevant files or reproduction steps, constraints that must remain stable, and verification. The page's examples emphasize:

- **Codebase explanation:** inspect the request flow, module responsibilities, validation points, compatibility rules, and change hazards; return a file list or checkable sequence.
- **Bug fixing:** provide a reproducible failure, preserve public contracts, make the smallest justified patch, add a regression test when useful, rerun the reproduction, and report checks.
- **Test writing:** name the exact function or selected lines and follow nearby test conventions, covering expected and edge behavior.
- **Screenshot prototyping:** combine the image with framework, routing, component, interaction, validation, responsive, and keyboard requirements; verify in a running browser when permitted.
- **Live UI iteration:** keep each follow-up narrow, review in the browser, preserve accepted edits, and tell Codex about manual reverts so it does not overwrite them.
- **Cloud refactoring:** plan against local code, make milestones/file moves/compatibility/rollback explicit, delegate bounded milestones to an isolated environment, then review and integrate the diff.
- **Local and GitHub review:** state focus areas, apply findings selectively, and rerun review or checks after repairs.
- **Documentation:** identify the exact document scope, require accuracy and link validation, then inspect the rendered page.

The page also distinguishes IDE context (open/selected files may be supplied automatically) from CLI context (paths should be mentioned or attached), and notes that sandbox/network boundaries may require approval. The durable lesson is to state required context and authority rather than assume a surface can access it.

## Principles to use in the later skill

- State the desired outcome and reviewable deliverable, not only the activity.
- Supply only context that can change the result, using the right source type.
- Name consequential constraints, authority boundaries, and failure conditions.
- Ask for verification that matches the changed boundary and final usage.
- Use follow-up steering to refine a result instead of encoding every preference in one oversized prompt.
- Store durable workflow knowledge in a skill; keep task-specific facts in the active request.

## Integration note

Combine these principles with the local `skill-creator` progressive-disclosure structure. Prompt guidance shapes a task request; a skill should retain only durable workflow knowledge, routing rules, reusable references, and deterministic helpers.
