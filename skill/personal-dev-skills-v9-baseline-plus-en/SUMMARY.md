# Skill collection summary

This package keeps the repository versions of `indie-product-delivery`, Anthropic `skill-creator`, and `humanizer-main` as the baseline. Existing delivery rules, examples, scripts, and evaluation contracts remain the source of truth. New material is inserted only where it clarifies an ambiguity or fills a missing decision path; it does not introduce a competing lifecycle.

## Included skills

| Skill | Purpose | Main changes from the repository baseline |
|---|---|---|
| `indie-product-delivery` | evidence-backed product discovery, design, implementation, quality, release, and post-launch learning | preserves Nodes01–07; promotes the existing HTML material to Node08; keeps AI application work inside Node03; adds selected decision, review, debugging, branch/worktree, module-boundary, and writing practices without replacing the original workflow |
| `skill-creator` | create, test, compare, improve, and package reusable skills | preserves the Anthropic creation/evaluation loop and scripts; moves long runtime branches into references; adds OpenAI outcome-first prompt design, optional Goal/Context/Output/Boundaries lenses, consequential-boundary guidance, no-op pruning, and honest fallbacks when controlled model runs are unavailable |
| `humanizer` | remove machine-shaped prose while preserving facts, meaning, and author voice | preserves all 33 patterns; splits them into conditional references; incorporates Gemini CLI technical-document practices, artifact-specific writing contracts, repository-fact checks, bilingual guidance, and a clarified precedence rule for author samples and repository conventions |

## Additions inside Indie Product Delivery

| Node | Selected source ideas added | Resulting change |
|---|---|---|
| Node01 market and MVP scope | `grilling`, `batch-grill-me`, `grill-with-docs`, `to-questionnaire` | dependency-aware questioning, parallel fact-finding that does not block unrelated decisions, recommendation-based questions, and stakeholder questionnaires for knowledge the user does not own |
| Node02 architecture, contracts, and plan | `domain-modeling`, `codebase-design`, `improve-codebase-architecture`, `to-spec`, `to-tickets`, `wayfinder` | clearer domain language and ownership; compare two feasible designs at costly boundaries; distinguish research, decision, prefactor, tracer, capability, migration, and hardening work before adding dependencies |
| Node03 backend, API, and data build | `implement`, `tdd`, `diagnosing-bugs`, `research`, plus current official model/RAG/agent guidance | AI, RAG, agents, MCP, prompts, retrieval, memory, evaluation, safety, and AI observability become one conditional backend branch; repeated failed fixes trigger assumption review rather than another patch |
| Node04 frontend UX/UI build | repository `frontend-design.md`, `design-an-interface`, `prototype`, and current production frontend guidance | choose one context-specific visual direction, preserve brownfield design systems, avoid generic AI aesthetics, and match implementation complexity to the chosen direction while retaining browser/accessibility proof |
| Node05 QA, review, security, and hardening | `code-review`, deprecated `qa`, `tdd`, `diagnosing-bugs` | findings require evidence, consequence, and repair direction; independent read-only review is reserved for major cross-module changes; quality decisions remain separate from release execution |
| Node06 CI/CD and launch | `git-guardrails-claude-code`, `resolving-merge-conflicts`, original Indie release discipline | distinguishes commit, push, merge, tag, release, and deploy; ordinary work stays on the current branch when allowed; exploratory branches merge only after their stated success condition passes |
| Node07 operations, growth, and iteration | selected `triage` and `handoff` ideas | keeps the original operating loop, adding only clearer ownership and handoff of evidence; no second growth or project-management system is introduced |
| Node08 HTML agent context | original `agent-context-html` plus HTML Effectiveness | a standalone node for choosing HTML as a medium, building spatial technical artifacts and project boards, preserving static readability, validating evidence and accessibility, and handing off stable browser-verifiable documentation |

## Ambiguities clarified

- HTML references now route through Node08; no old `references/agent-context-html/...` path remains.
- The Humanizer default dash rule no longer conflicts with its own voice-calibration rule: a user sample, repository convention, or technical artifact contract takes precedence.
- Skill evaluation never claims an independent benchmark when the runtime cannot provide independent runs.
- Shared Indie rules for comments, 50% meaningful unit-test coverage, local hermetic checks, cloud integration proof, release order, subagents, branches, and worktrees remain in the root skill instead of being replaced by node-local variants.

Substantive Markdown references stay between roughly 1,000 and 3,000 English words. Root skills and routing README files remain shorter because they provide progressive disclosure rather than domain instruction.
