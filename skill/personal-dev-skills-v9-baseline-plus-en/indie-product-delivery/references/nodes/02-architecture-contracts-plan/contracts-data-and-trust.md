# Contracts, Data, and Trust

Define explicit contracts for every cross-boundary interface, data entity, and trust
boundary. Design evolution and migration strategy. Node03/04 should not need to guess
behavior. Node06 should have a clear strategy to execute.

## Step 1: Build the capability spine

Map each approved capability from the Node01 spec through the system:

```
capability -> entry -> interface/access -> domain policy -> data/provider
-> observable result or recoverable failure -> local proof
```

Name the existing owner at each arrow, or mark it new. A missing owner is a design
signal, not permission to put all behavior in a controller.

## Step 2: Define interface contracts

For every interface that crosses an ownership or trust boundary (HTTP route, CLI
command, event, webhook, admin operation):

| Contract field | Must define |
|---|---|
| caller | user, admin, service, CLI, provider, or job |
| input | source, allowed fields, normalization, size or rate boundary |
| identity | session, token, signature, service identity, or command context |
| scope | tenant, account, owner, object, role, entitlement |
| success | result shape, redirect or event, durable side effect |
| errors | validation, unauthenticated, denied, absent, conflict, provider, internal |
| idempotency | what happens on duplicate request (dedup key? duplicate data? double charge?) |

**Core rules:**
- A UI guard is not an auth enforcement point. The server must independently verify
  identity and scope.
- Client-supplied role, owner, price, and entitlement values are untrusted until an
  enforcement point confirms them.
- Do not return inconsistent ad hoc objects from new entries because the happy path is
  simple. Use the repository's existing error mapper.
- Normalize and validate at the untrusted boundary. Treat request bodies, query
  params, cookies, headers, form actions, CLI args, webhook payloads, uploads, and
  model output as untrusted until validated.

## Step 3: Define the data model

For each persistent entity (table, document, object, or provider-backed record):

```markdown
## [Entity name]
- Meaning and owner: product meaning, owning module, tenant scope
- Identity: primary key, external ID, uniqueness, duplicate behavior
- Fields: type, nullable or default, sensitivity
- States: allowed states, transition owner, terminal or retryable states
- Lifecycle: create, read, list, update, delete, export, retention
- Relationships: cardinality, ownership, cascade behavior
- Integrity: constraints, concurrency rule, idempotency rule
- Visibility: subject scope, admin access, redaction
```

For important reads, define: filter, sort, pagination, permission filter, empty state,
stale state, and index pressure. Do not choose a concrete index or query implementation
unless that choice is architecture-significant.

For each query that drives a product workflow, name its consistency expectation:
whether a just-completed write must appear immediately, whether a short stale view is
honest, and which state the user sees while data catches up.

## Step 4: Define trust boundaries

For each protected read, list, mutation, admin path, job, provider callback, or upload:

```
subject -> resource -> action -> scope -> enforcement -> failure -> evidence
```

| Concern | Answer |
|---|---|
| identity | who or what acts: user, tenant, admin, service, provider, job? |
| scope | which account, org, object, plan, or region applies? |
| enforcement | where is the decision enforced? can callers bypass it? |
| untrusted input | which client, callback, upload, or model output must be checked? |
| failure | what is denied? what is visible? what is logged safely? who can recover? |

**For AI and LLM paths:** prompts, retrieved content, and model output are proposals,
never authority. Before any AI-derived side effect, deterministic server-side policy
must re-establish identity, scope, permission, and parameter constraints. Prompt
instructions or model confidence cannot replace that enforcement.

## Step 5: Evolution and compatibility checklist

This is architecture-level strategy design. Node06 executes the migration and rollout
following this strategy, but the strategy is decided here.

Run this checklist only when the change involves a breaking change. Mark N/A when
not applicable.

For each public contract change:

| Change type | Breaking? | Must do |
|---|---|---|
| new optional field or action | no (additive) | document semantics, preserve prior behavior |
| new required field | yes (potentially) | list affected callers, define default or compatibility path |
| rename or location change | yes (unless old alias remains) | define alias, migration notice, removal condition |
| enum or state expansion | consumer-sensitive | verify callers tolerate unknown or new state |
| error shape or code change | consumer-sensitive | preserve recoverable meaning, update error-to-fix guidance |
| auth or authz change | trust-affecting | re-evaluate access, failure behavior, and approval |
| timing or async change | behavior-affecting | define pending, completion, callback, and timeout semantics |
| idempotency change | data-affecting | define replay safety and durable duplicate identity |
| removal or deprecation | breaking | inventory consumers, define migration, deprecation path, and approval |

**A breaking change must have:** consumer inventory, compatibility window, migration
path, and rollback plan. An irreversible change must have a backup and roll-forward
plan.

**Migration design (architecture level):** For changes involving data migration,
design an expand-and-contract strategy: extend the compatible schema first, then
migrate reads and writes, then clean up the old structure. State whether rollback is
safe. Node06 executes the specific migration operation following this strategy.

## Step 6: Record ADRs

Record an ADR only when all three conditions are true (from domain-modeling):

1. **Hard to reverse** — the cost of changing the decision later is meaningful.
2. **Surprising without context** — a future reader will wonder "why did they do it
   this way?"
3. **Real trade-off** — there were genuine alternatives and you picked one for specific
   reasons.

If any of the three is missing, skip the ADR.

ADR format:
``+Context -> decision -> options rejected -> evidence -> consequences ->
cost and exit -> compatibility -> revisit trigger -> approval state
```

Keep ADRs discoverable from the project board. Do not add a separate ADR artifact
unless the user requests it or the rationale needs durable independent retrieval.

## Step 7: Maintain domain glossary

If designing produces or refines domain terms:

- A term conflicts with existing CONTEXT.md language — call it out immediately.
- A term is fuzzy or overloaded — propose a precise canonical term.
- A term is resolved — update CONTEXT.md immediately, do not batch.

CONTEXT.md is a glossary only, not a spec or scratch pad. No implementation details.

## Step 8: Produce the handoff

Synthesize all steps into the Architecture Handoff document defined in `README.md`.

## When contracts are complete

- Every approved capability has a capability spine.
- Every cross-boundary interface has a complete contract definition.
- Every persistent entity has a data model.
- Every trust boundary has an enforcement definition.
- Breaking changes have compatibility, migration, and rollback strategy (architecture
  level; execution routes to Node06).
- ADRs record only decisions meeting the 3 conditions.
- Open decisions each have an owner and a latest safe decision point.
