# Runtime Adaptations

## Claude.ai-specific instructions

In Claude.ai, the core workflow is the same (draft → test → review → improve → repeat), but because Claude.ai doesn't have subagents, some mechanics change. Here's what to adapt:

**Running test cases**: No subagents means no parallel execution. For each test case, read the skill's SKILL.md, then follow its instructions to accomplish the test prompt yourself. Do them one at a time. This is less rigorous than independent subagents (you wrote the skill and you're also running it, so you have full context), but it's a useful sanity check — and the human review step compensates. Skip the baseline runs — just use the skill to complete the task as requested.

**Reviewing results**: If you can't open a browser (e.g., Claude.ai's VM has no display, or you're on a remote server), skip the browser reviewer entirely. Instead, present results directly in the conversation. For each test case, show the prompt and the output. If the output is a file the user needs to see (like a .docx or .xlsx), save it to the filesystem and tell them where it is so they can download and inspect it. Ask for feedback inline: "How does this look? Anything you'd change?"

**Benchmarking**: Skip the quantitative benchmarking — it relies on baseline comparisons which aren't meaningful without subagents. Focus on qualitative feedback from the user.

**The iteration loop**: Same as before — improve the skill, rerun the test cases, ask for feedback — just without the browser reviewer in the middle. You can still organize results into iteration directories on the filesystem if you have one.

**Description optimization**: This section requires the `claude` CLI tool (specifically `claude -p`) which is only available in Claude Code. Skip it if you're on Claude.ai.

**Blind comparison**: Requires subagents. Skip it.

**Packaging**: The `package_skill.py` script works anywhere with Python and a filesystem. On Claude.ai, you can run it and the user can download the resulting `.skill` file.

**Updating an existing skill**: The user might be asking you to update an existing skill, not create a new one. In this case:
- **Preserve the original name.** Note the skill's directory name and `name` frontmatter field -- use them unchanged. E.g., if the installed skill is `research-helper`, output `research-helper.skill` (not `research-helper-v2`).
- **Copy to a writeable location before editing.** The installed skill path may be read-only. Copy to `/tmp/skill-name/`, edit there, and package from the copy.
- **If packaging manually, stage in `/tmp/` first**, then copy to the output directory -- direct writes may fail due to permissions.

---

## Cowork-Specific Instructions

If you're in Cowork, the main things to know are:

- You have subagents, so the main workflow (spawn test cases in parallel, run baselines, grade, etc.) all works. (However, if you run into severe problems with timeouts, it's OK to run the test prompts in series rather than parallel.)
- You don't have a browser or display, so when generating the eval viewer, use `--static <output_path>` to write a standalone HTML file instead of starting a server. Then proffer a link that the user can click to open the HTML in their browser.
- Generate the eval viewer when the user needs to inspect multiple outputs or benchmark dimensions before revising the skill; use `generate_review.py` rather than bespoke HTML. Do not create it merely because the runtime can.
- Feedback works differently: since there's no running server, the viewer's "Submit All Reviews" button will download `feedback.json` as a file. You can then read it from there (you may have to request access first).
- Packaging works — `package_skill.py` just needs Python and a filesystem.
- Description optimization (`run_loop.py` / `run_eval.py`) should work in Cowork just fine since it uses `claude -p` via subprocess, not a browser, but please save it until you've fully finished making the skill and the user agrees it's in good shape.
- **Updating an existing skill**: The user might be asking you to update an existing skill, not create a new one. Follow the update guidance in the claude.ai section above.

---

## Choose the strongest honest evaluation available

Runtime capability changes the mechanics, not the standard of evidence. Use this order:

| Available capability | Evaluation approach |
|---|---|
| independent subagents or fresh model sessions | launch controlled with-skill and baseline runs from the same inputs and evaluate them blind where useful |
| one model session with filesystem access | preserve an old snapshot, run deterministic checks, inspect traces, and ask the user to compare concrete outputs; disclose that the evaluator has seen the skill |
| no execution runtime | validate structure, links, scripts, examples, and trigger boundaries; prepare a reproducible eval set without inventing scores or timing |

Do not simulate independence by renaming outputs or by grading a result you authored as if it came from another agent. The user can still make a useful qualitative judgment when the limitation is explicit and the comparison materials are preserved.

## Preserve the same artifact contract

Changing runtimes may change how files are opened, how feedback is collected, or whether runs can execute in parallel. It does not change the expected skill folder, test prompt, output artifact, or evaluation criteria. Keep those stable so later runs remain comparable.

## Keep controlled variables stable

When comparing a skill across runtimes, keep the user prompt, input files, repository ref, model configuration, available tools, output request, and evaluation rubric unchanged wherever the platform permits. Record unavoidable differences before judging the outputs. A faster run with fewer tools or a better answer produced from richer context is not clean evidence that the skill itself improved. Treat runtime-specific gains as useful observations, but separate them from claims about the instruction bundle.
Prefer one recorded comparison matrix over scattered informal impressions.
Record it once, centrally.
