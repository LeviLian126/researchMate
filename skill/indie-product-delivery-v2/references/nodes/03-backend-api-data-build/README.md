# Backend Build

Use this when the present need is backend implementation: building an approved backend slice, placing behavior in the right owner, or implementing HTTP/action/CLI/admin/event/webhook boundaries, persistence, providers, or async work.

| Need | Read |
|---|---|
| frame a slice; place domain behavior; implement HTTP/action/CLI/admin/event/webhook boundaries | `backend-build.md` |
| implement repositories, schema evolution, concurrency, providers, callbacks, jobs, idempotency, reconciliation | `backend-build.md` |
| prove behavior, debug from the real boundary, add proportional observability, or decide local hermetic vs deployed/server proof | `backend-proof.md` |

Shared mechanisms (fact states, reuse/extend/replace/new, status/evidence discipline) live in `references/methods.md`.
