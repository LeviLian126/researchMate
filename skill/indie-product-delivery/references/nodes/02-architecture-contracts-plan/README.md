# System Design

Node02 owns system boundaries and contracts that implementation must not invent. Use it for new or changed data ownership, public interfaces, permissions, providers, asynchronous behavior, compatibility, migrations, runtime shape, module ownership, dependencies, or low-reversibility architecture.

| Need | Read |
|---|---|
| discover the current system; define interface, data, tenant, trust, provider, and failure contracts | `system-boundaries-data-and-trust-contracts.md` |
| choose runtime/module/dependency shape; plan compatibility, migration, recovery, and build slices | `architecture-evolution-and-build-plan.md` |

Do not require Node02 for a known local implementation inside an established contract. Return to Node01 only when user value, promise, pricing, entitlement, primary workflow, scope, or acceptance is genuinely undecided.

A build-ready decision names the affected owners and consumers, inputs and outputs, data lifecycle, enforcement boundary, failure/recovery behavior, compatibility path, and evidence that would prove the contract. For cross-boundary or high-risk choices, also inspect worst-case impact, cascade or single-point failure, detectability, and degradation or isolation. Skip this blast-radius check for reversible local changes.

Group interfaces, types, behavior, and tests that change for the same reason when that improves cohesion; do not reorganize an existing repository merely to make directories look cleaner. For real developer products—API, CLI, SDK, package, webhook, or integration—define the target developer mental model, safe minimum-success defaults, actionable errors, and only consumer-justified escape hatches.

Hand an approved plan to Node03/04. Route quality or security judgment to Node05 and release execution to Node06. Node02 may define recovery and rollout contracts but does not execute production actions.
