# System Design

## Read the relevant workflow

| Need | Read |
|---|---|
| discover the current system and build the leverage, context, and boundary map | `system-discovery-and-boundary-map.md` |
| define interface, data, tenant, trust, provider, event, asynchronous, state, failure, and recovery contracts | `contracts-data-and-trust-model.md` |
| choose runtime, module, dependency, and observability shape; compare architecture forks; record ADR-lite decisions | `architecture-decisions-and-runtime-shape.md` |
| plan compatibility, migration, recovery, design slices, readiness, and the build handoff | `architecture-evolution-and-build-handoff.md` |

Read only the workflow or workflows that materially affect the result. Hand an approved plan to Node03 or Node04. Route quality or security judgment to Node05, release execution to Node06, and spatial HTML explanation to Node08.

## Output contract

Return the smallest buildable system-design handoff: current boundaries, affected
contracts and data/state ownership, relevant architecture decisions, compatibility or
recovery obligations, design slices, proof obligations, unresolved decisions, and one
readiness state: `READY`, `READY_WITH_NAMED_RISKS`, `BLOCKED`, or `FAST_TRACK_ACCEPTED`.
