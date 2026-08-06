# Outcome-first prompt design for skills

Use this guide while drafting or revising instructions. It supplements the creation and evaluation loop; it does not replace concrete examples, source research, or behavior tests.

## Start from the result

Describe the observable result before prescribing a procedure. A useful instruction tells the agent what must be true when the task is complete, who will use the result, and what evidence distinguishes completion from a plausible-looking attempt. Add a sequence only when order affects correctness, safety, reproducibility, or the user's working method.

The following four lenses are available, not mandatory headings:

| Lens | Question |
|---|---|
| goal | What should the agent accomplish or decide? |
| context | Which facts, files, sources, tools, or prior decisions can change the result? |
| output | What artifact or state must be ready to use, and at what level of detail? |
| boundaries | Which few mistakes would make the result unsafe, misleading, costly, or unusable? |

Use only the lenses that earn their context cost. A rigid form filled with empty sections is worse than a short instruction that makes the result and limits clear.

## Add context that changes behavior

Point to authoritative local files, repository instructions, schemas, examples, or official documentation and say what the agent should learn from each. Do not paste general background the model already knows. For version-sensitive libraries and services, instruct the agent to inspect the installed version and current official source rather than encoding a long snapshot that will age inside the skill.

Separate user decisions from discoverable facts. The agent should inspect safe sources before asking the user to repeat information. It should still ask when the missing input is a value judgment, risk preference, authorization, or product choice that cannot be inferred safely.

## Specify outputs as contracts

Name the output when its form changes the work: an edited file, a report, a branch, a static HTML artifact, a structured JSON object, a verified deployment, or a decision record. State the fields or sections that consumers rely on. Use a template when exact structure is part of compatibility; otherwise describe the information and reader job without forcing every result into the same shape.

Ask for a final check that matches the task. Examples include verifying that every action has an owner, every citation supports its claim, every changed link resolves, or every externally visible action was authorized. Avoid generic “double-check your work” lines that do not change behavior.

## Keep boundaries few and consequential

Boundaries prevent real problems: changing an approved public contract, inventing missing facts, sending or deploying without authorization, writing outside the requested scope, or exposing private data. A long list of prohibitions makes the important constraints harder to find and can steer the model toward the very behavior being named. Prefer a positive target, then state the high-consequence exception precisely.

Match freedom to the task. Use high-level guidance when several approaches can succeed, a preferred pattern or pseudocode when consistency matters, and a deterministic script when the operation is fragile or exact. Do not use imperative intensity to compensate for an unclear goal.

## Write instructions that earn their tokens

Run a sentence-level no-op test: if removing a sentence would not change a competent agent's choice, evidence, output, or safety, remove it. Also inspect negative space. What important decision is currently delegated to generic model habits because the skill says nothing about it? Add only the missing guidance that is specific to this workflow.

Prefer short explanations of why a non-obvious rule matters. Use tables when they expose repeated relationships or routing choices. Use examples when they disambiguate behavior that prose cannot define cleanly. Do not accumulate examples that all exercise the same happy path.

## Validate the prompt through behavior

Static validation proves that files and metadata are well formed. It does not prove that the skill triggers correctly or improves output. Test realistic should-trigger prompts, near-miss prompts that belong to adjacent skills, and behavior cases that stress the skill's distinctive decisions. Compare with a baseline under the same task, files, tools, model, and evaluation criteria whenever the runtime supports a controlled comparison.

Read the execution trace as well as the final artifact. A skill may produce an acceptable result while causing unnecessary research, repeated questions, excessive tool use, or a brittle script. Revise the instruction that caused the behavior rather than adding a special-case prohibition for each visible symptom.

## Description Optimization

The description field in SKILL.md frontmatter is the primary mechanism that determines whether Claude invokes a skill. After creating or improving a skill, offer to optimize the description for better triggering accuracy.

### Step 1: Generate trigger eval queries

Create 20 eval queries — a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

The queries must be realistic and something a Claude Code or Claude.ai user would actually type. Not abstract requests, but requests that are concrete and specific and have a good amount of detail. For instance, file paths, personal context about the user's job or situation, column names and values, company names, URLs. A little bit of backstory. Some might be in lowercase or contain abbreviations or typos or casual speech. Use a mix of different lengths, and focus on edge cases rather than making them clear-cut (the user will get a chance to sign off on them).

Bad: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

For the **should-trigger** queries (8-10), think about coverage. You want different phrasings of the same intent — some formal, some casual. Include cases where the user doesn't explicitly name the skill or file type but clearly needs it. Throw in some uncommon use cases and cases where this skill competes with another but should win.

For the **should-not-trigger** queries (8-10), the most valuable ones are the near-misses — queries that share keywords or concepts with the skill but actually need something different. Think adjacent domains, ambiguous phrasing where a naive keyword match would trigger but shouldn't, and cases where the query touches on something the skill does but in a context where another tool is more appropriate.

The key thing to avoid: don't make should-not-trigger queries obviously irrelevant. "Write a fibonacci function" as a negative test for a PDF skill is too easy — it doesn't test anything. The negative cases should be genuinely tricky.

### Step 2: Review with user

Present the eval set to the user for review using the HTML template:

1. Read the template from `assets/eval_review.html`
2. Replace the placeholders:
   - `__EVAL_DATA_PLACEHOLDER__` → the JSON array of eval items (no quotes around it — it's a JS variable assignment)
   - `__SKILL_NAME_PLACEHOLDER__` → the skill's name
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → the skill's current description
3. Write to a temp file (e.g., `/tmp/eval_review_<skill-name>.html`) and open it: `open /tmp/eval_review_<skill-name>.html`
4. The user can edit queries, toggle should-trigger, add/remove entries, then click "Export Eval Set"
5. The file downloads to `~/Downloads/eval_set.json` — check the Downloads folder for the most recent version in case there are multiple (e.g., `eval_set (1).json`)

This step matters — bad eval queries lead to bad descriptions.

### Step 3: Run the optimization loop

Tell the user: "This will take some time — I'll run the optimization loop in the background and check on it periodically."

Save the eval set to the workspace, then run in the background:

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from your system prompt (the one powering the current session) so the triggering test matches what the user actually experiences.

While it runs, periodically tail the output to give the user updates on which iteration it's on and what the scores look like.

This handles the full optimization loop automatically. It splits the eval set into 60% train and 40% held-out test, evaluates the current description (running each query 3 times to get a reliable trigger rate), then calls Claude to propose improvements based on what failed. It re-evaluates each new description on both train and test, iterating up to 5 times. When it's done, it opens an HTML report in the browser showing the results per iteration and returns JSON with `best_description` — selected by test score rather than train score to avoid overfitting.

### How skill triggering works

Understanding the triggering mechanism helps design better eval queries. Skills appear in Claude's `available_skills` list with their name + description, and Claude decides whether to consult a skill based on that description. The important thing to know is that Claude only consults skills for tasks it can't easily handle on its own — simple, one-step queries like "read this PDF" may not trigger a skill even if the description matches perfectly, because Claude can handle them directly with basic tools. Complex, multi-step, or specialized queries reliably trigger skills when the description matches.

This means your eval queries should be substantive enough that Claude would actually benefit from consulting a skill. Simple queries like "read file X" are poor test cases — they won't trigger skills regardless of description quality.

### Step 4: Apply the result

Take `best_description` from the JSON output and update the skill's SKILL.md frontmatter. Show the user before/after and report the scores.

---

### Package and Present (only if `present_files` tool is available)

Check whether you have access to the `present_files` tool. If you don't, skip this step. If you do, package the skill and present the .skill file to the user:

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

After packaging, direct the user to the resulting `.skill` file path so they can install it.

---
