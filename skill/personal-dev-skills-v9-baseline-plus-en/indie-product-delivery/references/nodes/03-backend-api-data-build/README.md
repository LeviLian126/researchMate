# Backend Build

## Read the relevant workflow

Read `slice-framing.md` first for any non-trivial implementation work. Then read only the
files that match the layers your slice touches.

| Need | Read |
|---|---|
| frame the approved slice; recover implementation truth; build the implementation spine | `slice-framing.md` |
| implement domain behavior, use-case ownership, state transitions, policy | `domain-build.md` |
| implement HTTP, CLI, event, or webhook boundaries; validation, auth enforcement, error mapping | `interface-build.md` |
| implement repositories, queries, transactions, schema evolution, concurrency | `persistence-build.md` |
| implement provider adapters, jobs, callbacks, idempotency, reconciliation | `provider-async-build.md` |
| implement an LLM, RAG, agent loop, tool-calling, MCP, evaluation, or AI-observability branch | `ai-application-build.md` |
| lock core behavior, debug from the real boundary, add proportional observability | `proof-debug-observability.md` |

Return to Node01 or Node02 when product meaning or a public contract remains undecided.
Node03 writes and proves high-quality implementation code; Node05 owns independent quality
review, and Node06 owns release execution.

## Output contract

Return the changed backend surface, owning module and contracts, data/provider/async
effects, core-code tests and proof run, observability added or missing, documentation
impact, and remaining implementation risks or blockers.

Set one implementation status:

| Status | When to use |
|---|---|
| `BUILT` | Requested implementation and required hermetic proof are complete. Named gaps in deployed or environment evidence are listed but do not block the implementation claim. |
| `BLOCKED` | A required implementation fact, safe proof, credential, or environment is unavailable. State what is missing and what was attempted. |
| `NEEDS_CONTRACT` | A contract, boundary, runtime, compatibility, or recovery design must change before implementation can proceed correctly. State what must change and route to Node02. |

Do not issue a quality or ship verdict from Node03.