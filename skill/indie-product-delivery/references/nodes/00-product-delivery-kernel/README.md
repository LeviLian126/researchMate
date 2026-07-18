# Product Delivery Kernel

Use this kernel after activation to initialize one compact delivery state, select the current owner, and keep the task moving toward the result requested by the user. Do not treat a possible lifecycle chain as a list of files to load.

## Delivery state

Maintain these fields internally. Expose them only when they help the user understand a decision or blocker.

| Field | Values or meaning |
|---|---|
| `owner` | Node01–Node07 or `agent-context`; the owner of the present decision or action |
| `scope` | `LOCAL`, `MODULE`, `CROSS_BOUNDARY`, or `PRODUCT_DIRECTION` |
| `risk` | `STANDARD`, `SENSITIVE`, or `ACTIVE_HARM` |
| `external_effect` | whether the next action changes anything outside the authorized workspace |
| `mutation` | `PLAN_ONLY`, `REVIEW_ONLY`, `CHANGE_AND_VERIFY`, `EXECUTE_AUTHORIZED`, or `REPORT_ONLY` |
| `required_preconditions` | unresolved product, contract, environment, evidence, or authority facts needed before action |
| `required_gates` | only the quality, security, compatibility, or release decisions actually required |
| `terminal_target` | the result that fulfills the original request |
| `terminal_status` | one global completion or blocker state |

Select scope from the actual change, not sensitive nouns in nearby text:

| Scope | Use when |
|---|---|
| `LOCAL` | one known surface or mechanical edit; no behavior or contract boundary changes |
| `MODULE` | behavior changes within one established owner and contract |
| `CROSS_BOUNDARY` | multiple owners, public interfaces, data flow, providers, compatibility, or deployment boundaries change |
| `PRODUCT_DIRECTION` | target user, promise, pricing, MVP/MAP, positioning, or primary workflow changes |

Select risk independently:

- `STANDARD`: ordinary reversible product work with no sensitive boundary.
- `SENSITIVE`: authentication, authorization, tenancy, private data, money, secrets, destructive data evolution, public compatibility, or low-reversibility design is materially affected.
- `ACTIVE_HARM`: current production behavior may be harming users, data, money, privacy, security, or availability. Containment and direct evidence outrank growth or polish.

Set `external_effect` from the proposed action, not the subject matter. Editing payment code locally is not an external effect; charging a provider is. Writing a migration is local; applying it to shared or production data is external.

Choose mutation from user intent:

| Mutation | Meaning |
|---|---|
| `PLAN_ONLY` | analyze or design without changing the product |
| `REVIEW_ONLY` | inspect and report; do not edit |
| `CHANGE_AND_VERIFY` | make authorized workspace changes and prove them proportionately |
| `EXECUTE_AUTHORIZED` | perform the specifically authorized external action and verify the target |
| `REPORT_ONLY` | observe or synthesize operational evidence without changing product or external state |

## Select the current owner

| Present need | Owner |
|---|---|
| user, market, promise, pricing, positioning, MVP/MAP, acceptance | Node01 |
| system boundary, API/data/permission/provider contract, architecture, migration design, implementation plan | Node02 |
| backend/API/data/auth/job/provider implementation | Node03 |
| frontend flow, content, visual system, interaction, responsive/accessibility implementation | Node04 |
| review, runtime QA, reliability, security, or ship judgment | Node05 |
| CI/CD, release preparation, deploy, rollout, rollback, production verification | Node06 |
| production health, customer evidence, experiment, next operating decision | Node07 |
| durable HTML project documentation or an existing project board | `agent-context` |

A local task with a clear owner goes directly there. Product truth precedes architecture only when product truth is actually unresolved. Contracts precede implementation only when implementation would otherwise invent them. Node05 or Node06 is a gate only when the terminal target or risk requires it.

## Set the terminal target

Use the original request rather than an assumed end-to-end lifecycle:

- `PRODUCT_DECISION`
- `SYSTEM_PLAN`
- `VERIFIED_CHANGE`
- `REVIEW_RESULT`
- `SHIP_DECISION`
- `RELEASE_READY`
- `VERIFIED_RELEASE`
- `INCIDENT_CONTAINED`
- `OPERATING_DECISION`
- `CURRENT_DOCUMENTATION`

For example, “implement but do not deploy” targets `VERIFIED_CHANGE` or `SHIP_DECISION`, never `VERIFIED_RELEASE`. Preparing an operator-ready release without access may complete `RELEASE_READY`; a request to execute the release remains blocked until authority and access exist.

## Interpret operational terms consistently

- **Material**: capable of changing the promised user outcome, public contract, access/data boundary, money movement, external behavior, or recovery from failure.
- **Bounded**: affected surfaces, consumers, data, side effects, and failure/recovery path are known well enough to constrain the action.
- **Meaningful evidence**: directly exercises or observes the claim at its relevant boundary.
- **Exact authorization**: the user or governing instruction identifies the external action, target, scope, and meaningful exclusions.
- **Reversible local change**: confined to the authorized workspace and recoverable without customer impact, external mutation, data loss, or irreversible cost.
- **Current evidence**: obtained from the present checkout, configured environment, or current authorized observation rather than remembered or stale results.

Prefer these concrete predicates over unqualified words such as safe, approved, robust, or clear.

## Use evidence in authority order

For current product facts, prefer current user instructions, repository instructions, source/configuration, tests, and maintained local documentation. For provider, framework, or version-sensitive behavior, prefer installed versions, lockfiles, package metadata, and configuration, then official documentation for that version. Surface conflicts instead of silently selecting the convenient source.

## Apply layered authority

An explicit implementation or fix request authorizes reversible local edits and local verification within its stated scope, including writing migration, payment, permission, or security-related code. It does not authorize the corresponding production effect.

Confirm an unresolved product-direction, public-contract, or low-reversibility architecture choice before landing it when the request does not already decide the outcome and impact.

Require exact authorization before deployment, production migration, real charges or messages, customer/shared-data writes, destructive operations, credential rotation, history rewrite, DNS or traffic changes, rollback, or other external effects. Dynamic security testing additionally requires an owned target, allowed methods, account/data scope, and meaningful exclusions. Static review and local analysis do not require that additional authority.

Commits, branches, pushes, PRs, issues, and other collaboration-system mutations require an explicit request.

## Degrade claims with unavailable tools

- Without a repository or artifact, produce a plan or requirements decision; do not claim current implementation facts.
- Without a browser, do not claim visual or interaction proof. If browser behavior is required acceptance, use `BLOCKED_EVIDENCE`.
- Without a required runtime or test environment, use static evidence only for claims it can support. Missing optional confidence may yield `DONE_WITH_CONCERNS`; missing required proof yields `BLOCKED_EVIDENCE`.
- Without deploy access or exact authorization, do not claim release execution. A preparation request may finish at `RELEASE_READY`; an execution request uses `BLOCKED_AUTHORIZATION`.
- Without current external research, label time-sensitive market or provider conclusions as assumptions.

## Converge

Combine all currently known blocking questions into one clarification round. A user answer or newly discovered repository fact may introduce a genuinely new question.

Do not repeat a failed command, repair, or route without new evidence and a new falsifiable reason. Allow at most three focused repair attempts for one root cause and at most one architecture re-entry for an unchanged task scope. New user requirements or newly discovered cross-boundary facts may reset the relevant budget. When no new authorized, evidence-producing action remains, finish with the applicable blocker instead of continuing a “next step” loop.

## Finish globally

Every task ends internally as one of:

| Status | Use when |
|---|---|
| `DONE` | the requested deliverable exists and required acceptance has direct evidence |
| `DONE_WITH_CONCERNS` | the requested result is complete and any residual issue is non-blocking, bounded, and disclosed |
| `BLOCKED_USER_DECISION` | a required product or tradeoff decision cannot be inferred safely |
| `BLOCKED_AUTHORIZATION` | the remaining action exceeds granted authority or access |
| `BLOCKED_EVIDENCE` | required proof cannot be obtained in the available environment |
| `ABORTED_UNSAFE` | continuing would create unacceptable or unauthorized harm |

`ROUTE_NEXT` is an internal transition, never a terminal result. Node05 and Node06 may retain domain states such as `SHIP`, `READY_TO_EXECUTE`, or `EXECUTED_AND_VERIFIED`, but map them to a global status based on the original terminal target.

When durable project documentation is requested, or an established project board owns facts changed by the task, load `references/agent-context-html/instructions.md` and update that board in place. Do not create a board for an unrelated ordinary code edit.
