# Source preservation manifest

This phase preserves upstream and local source text before synthesis. Files under `originals/` are reference inputs, not automatically active instructions. Higher-priority system, developer, user, and repository rules always win.

## Preserved collections

| Material | Preservation scope | License / status | Intended nodes |
|---|---|---|---|
| `originals/indie-product-delivery/` | Complete current 34-file skill | Local project material | All delivery nodes; primary workflow baseline |
| `originals/skill-creator/` | Complete supplied source files, excluding generated Python bytecode caches | Apache-2.0 | v2 structure, progressive disclosure, later eval loop |
| `originals/humanizer-main/` | Complete 9-file source | MIT | Human writing |
| `local-source-notes.md` | Hashes, provenance gaps, and original summaries for local `gemini-human.md` and `frontend-design.md`; full text is not copied into v2 | Redistribution license not established | Human writing, technical docs, and frontend |
| `originals/gstack-main/` | Governing `AGENTS.md`, its linked iOS-testing note, MIT license, and 19 selected complete `SKILL.md` files | MIT | Discovery, architecture, frontend, QA, release |
| `originals/html-effectiveness/` + `web/html-effectiveness-homepage.md` | Complete upstream repository snapshot, including 20 example HTML files, README, license, security policy, and index; complete readable homepage text transcribed to Markdown | Apache-2.0; commit recorded in `UPSTREAM_COMMIT` | HTML docs plus selected visual examples across nodes |
| `web/openai-prompting-notes.md` | Structured summary and canonical URLs; no verbatim full-page archive | Official page, redistribution license not verified | Skill construction and human writing |

## Selected gstack sources

- Product: `office-hours`, `plan-ceo-review`, `spec`
- Architecture/backend: `plan-eng-review`, `investigate`, `review`
- Frontend: `plan-design-review`, `design-consultation`, `design-review`, `design-html`
- QA: `qa-only`, `qa`, `cso`, `benchmark`
- Release: `setup-deploy`, `ship`, `land-and-deploy`, `canary`, `document-release`

The full gstack checkout remains at `skill/gstack-main/`. Only node-relevant source files are copied here to keep the v2 working set reviewable. Its upstream `AGENTS.md` says generated skill files should normally be changed through templates; these copies are frozen research inputs and will not be edited in place.

## Integrity and attribution

`source-files.sha256` records SHA-256 hashes for every file under `references/originals/`. Authored transcripts, summaries, manifests, and node skeletons are tracked normally but are outside that frozen-source checksum set. Preserve upstream license files when later extracting or adapting text. Add attribution and modification notices required by the applicable license.

## Known provenance gaps

Do not publish the full text of `frontend-design.md` or `gemini-human.md` until their source and license are confirmed. They can inform local comparison and synthesis, while the final workflow should be expressed in original language. The imported `gemini-human.md` also links to `references/docs-auditing.md`, which was not present anywhere in the supplied local source tree; the missing companion is recorded rather than fabricated.

## Why the OpenAI page is not copied verbatim

The official Markdown endpoint makes the page easy to retrieve, but availability is not a redistribution license. The repository therefore keeps the URL, retrieval date, structure, and principles rather than a full copyrighted copy. If a later license grants redistribution, add the licensed source snapshot and its license at that time.
