# System Design

Take the Node01 spec and produce a buildable architecture handoff: module boundaries
defined with deep-module principles, interface contracts explicit, data model complete,
trust boundaries enforced, and evolution and deployment strategy chosen. Node03 or
Node04 should be able to implement without guessing system behavior.

## Read the relevant workflow

| Need | Read |
| --- | --- |
| read existing code, find reuse paths, define module boundaries, dependency direction, deployment topology | `system-discovery-and-modules.md` |
| define interface contracts, data model, trust boundaries, evolution and migration strategy | `contracts-data-and-trust.md` |

Linear flow: discovery first (understand the existing system), then contracts (design
the new contracts). Not every project needs both stages fully. A narrow feature that
changes one existing module may skip to contracts after a quick discovery confirms the
reuse path.

## Boundary with downstream nodes

Node02 makes architecture-level decisions. Downstream nodes execute them.

| Node02 decides (architecture) | Downstream node executes |
| --- | --- |
| module boundaries and interface seams | Node03/04 writes implementation code |
| deployment topology (VPS, SQLite, adapter) | Node06 configures and runs deployment |
| evolution strategy and compatibility window | Node06 executes migration and rollout |
| trust boundary enforcement point | Node05 verifies enforcement works |
| test seams and dependency categories | Node03/04 writes tests, Node05 verifies quality |
| data model and schema semantics | Node03 implements schema, Node06 runs migration |

## Output contract: Architecture Handoff

```markdown
# Architecture Handoff: [Feature Name]

## Source spec
[Node01 spec reference or summary]

## System context
[One-sentence description of the existing system + the boundary of this change]

## Module design
| Module | Interface (seam) | Depth | Adapters | Dependencies |
|---|---|---|---|---|
[Each module: interface definition, deep/shallow assessment, adapters, dependency category]

## Deployment topology
[hosting/data/backend/frontend/realtime/external service architecture choices]

## Data model
[Persistent entities, fields, states, lifecycle, relationships, constraints]

## Interface contracts
[Each cross-boundary interface: caller, input, authz, success, errors, idempotency]

## Trust boundaries
[subject -> resource -> action -> scope -> enforcement -> failure -> evidence]

## Evolution strategy
[Breaking change: compatibility window, migration path, rollback plan. Non-breaking: N/A]

## ADRs
[Only decisions meeting 3 conditions: hard to reverse + surprising + real trade-off]

## Open decisions
[Unresolved architecture questions, each with owner and latest safe decision point]

## Decision
- [ ] GO: Node03/04 can begin implementation
- [ ] NO_GO: unresolved architecture blocker, needs Node01 or user decision
```

Node03/04 should not need to make architecture decisions after receiving this handoff.
Node06 should not need to design migration or rollout strategy, only execute it.
