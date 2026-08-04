# Backend Build

## Read the relevant workflow

| Need | Read |
|---|---|
| frame the approved slice; recover implementation truth; implement domain behavior, use-case ownership, state transitions, interface validation, authentication, authorization, stable results, and behavior-preserving refactors | `backend-slice-domain-and-interface-build.md` |
| implement repositories, schema evolution, concurrency, providers, callbacks, jobs, idempotency, and reconciliation | `persistence-provider-and-async-build.md` |
| implement an LLM, RAG, agent, tool-calling, MCP, evaluation, memory, or AI-observability branch | `ai-application-build.md` |
| lock core behavior, debug from the real boundary, and add proportional observability | `backend-proof-debug-and-observability.md` |

Read only the workflow or workflows that materially affect the current slice. Return to Node01 or Node02 when product meaning or a public contract remains undecided. Node03 writes and proves high-quality implementation code; Node05 owns independent quality review, and Node06 owns release execution.

## Output contract

Return the changed backend surface, owning module and contracts, data/provider/async
effects, core-code tests and proof run, observability added or missing, documentation
impact, and remaining implementation risks or blockers. State whether the slice is
complete, complete with named gaps, blocked, or needs Node01/02 re-entry. Do not issue a
quality or ship verdict from Node03.
