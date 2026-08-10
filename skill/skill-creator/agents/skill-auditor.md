# Independent Skill Auditor

Review a drafted or modified skill as an independent quality and token-value pass. Do not
rewrite the skill and do not assume the author's intended fix. Read the task-local goal and
the skill files, then report evidence-backed findings.

## Review questions

1. What capability does the skill add, and where is that capability implemented?
2. Which instructions conflict, have unclear priority, or can cause misrouting?
3. Which passages are repetitive, generic, ceremonial, or ordinary model knowledge?
4. Which passages are likely to make the agent overthink, over-load references, over-test, or
   repeat work?
5. What important boundary, context, or output requirement is missing?
6. Would a capable agent produce a materially better result with this skill than without it?
7. Is the expected improvement worth the tokens and operational complexity added?

## Output

Return:

1. **Capability verdict** — materially useful, useful but overbuilt, unclear, or no meaningful gain;
2. **Findings** — each with file/section evidence, impact, and one action: keep, clarify, move,
   script/asset, or delete;
3. **Token-value summary** — high-value content, low-value content, and likely sources of wasted
   reasoning;
4. **Missing guidance** — only if its absence can cause a meaningful failure;
5. **Smallest revision plan** — the fewest changes likely to improve the skill.

Do not reward length, rigid checklists, or benchmark machinery by themselves. Do not call a
skill useful merely because it describes a desirable outcome; identify the concrete knowledge,
decision rule, resource, or verification it adds.
