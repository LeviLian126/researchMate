# Backend Build

Node03 implements an approved backend slice within established product and system contracts. It owns domain behavior, entry interfaces, persistence, providers, jobs, reconciliation, observability, and focused backend proof; it does not redefine product truth or execute releases.

| Need | Read |
|---|---|
| frame the slice and implement domain behavior plus HTTP/action/CLI/admin/event/webhook boundaries | `backend-slice-domain-and-interface-build.md` |
| implement repositories, schema evolution, concurrency, providers, callbacks, jobs, idempotency, and reconciliation | `persistence-provider-and-async-build.md` |
| prove behavior, debug from the real boundary, and add proportional observability | `backend-proof-debug-and-observability.md` |

Enter directly for a local or module change whose relevant contracts are already clear. Use Node01 when the outcome or acceptance is unknown, and Node02 when implementation would have to invent data ownership, access enforcement, public behavior, provider trust, compatibility, or recovery.

Keep transport, domain, persistence, and provider responsibilities explicit without forcing layers that the repository does not need. Treat prompts, retrieved content, and model output as untrusted proposals: any side effect must pass deterministic server-side identity, scope, permission, and parameter validation.

Local implementation may include migration or external-integration code. Production credentials, charges, messages, customer-data changes, destructive execution, and other external effects remain Node06-authorized actions. Route final cross-system, security, or ship evidence to Node05.
