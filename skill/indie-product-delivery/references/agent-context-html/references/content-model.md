# Project Documentation Content Model

Use this reference to turn Node01 product truth and Node02 architecture truth into a complete HTML documentation set. Show the current summary immediately; put dense records on focused linked pages and use disclosure controls inside those pages where helpful.

## Purpose

Provide the evidence model for a serious, complete project documentation set.

## Documentation topology

Default to English and choose page boundaries by information responsibility:

| Surface | Responsibility |
| --- | --- |
| current snapshot | project identity, verified release boundary, commercial state, capability summary, top risks, next action, freshness, and navigation |
| product | audience, buyer, beneficiary, problem, promise, scenarios, first success, market evidence, alternatives, distribution, pricing, trust, and non-goals |
| delivery | full capability map, user journeys, MVP/MAP boundary, acceptance, implementation evidence, validation, dependency, owner, risk, and roadmap status |
| architecture | frontend/backend/data/integration/work-execution/runtime boundaries, request and data flows, ownership, failure/recovery, and decisions |
| database contracts | entity map and every evidenced table, material field, type, nullability, default, key, constraint, index, tenant rule, RLS, lifecycle, and relation |
| API contracts | every evidenced endpoint/action with caller, auth, permission, request, validation, response, status, failure, idempotency/asynchrony, source, and test proof |
| operations and decisions | environment/release state, run commands, observability, security, costs, blockers, risks, decision ledger, and ordered actions |
| activity | material historical releases, migrations, incidents, security reviews, experiments, and approved milestones only |

Combine low-volume topics when that improves reading. Split a topic when a single page would hide complete ledgers behind an overview, force excessive scrolling, or reduce contract detail to examples. Keep page names descriptive and navigation consistent; do not introduce modes or a client-side router.

## Workflow

Populate the sections below from the strongest available Node01/Node02 and repository evidence. Summaries may retain only decision-relevant facts, but database and API contract ledgers must preserve every evidenced field and operation in scope.

## Coverage manifest

Build a countable inventory before composing pages. This is a completion boundary, not an optional planning note.

| Source surface | Inventory unit |
| --- | --- |
| product and roadmap documents | every maintained capability, requirement/story ID, acceptance condition, status-bearing item, price/package fact, risk, and decision in scope |
| frontend and backend | every user-visible route/surface and every material action, handler, integration, background job, and authorization boundary |
| OpenAPI, route schemas, or action contracts | every operation plus every referenced request, response, error, permission, and asynchronous/idempotency semantic |
| migrations and maintained schemas | every table/entity, every evidenced field, PK/FK, unique/index/check/enum constraint, referential action, RLS/tenant rule, and lifecycle rule |
| tests and configuration | every result or setting used to support a shipped, validated, environment, dependency, or operational claim |
| architecture and decision records | every material component, boundary, handoff, failure/recovery path, selected option, rejected alternative, and revisit trigger |

Record expected and rendered counts by category. Include every inventory item in a full ledger, or record an explicit exclusion with its reason and source. A diagram or summary may precede the ledger, but it never replaces it. Examples may explain a pattern only after complete coverage exists. If the evidence volume is large, split it across linked pages or generate compact expandable records; do not sample it down to a demo.

## Evidence record

Attach this compact record to material facts, status-bearing rows, diagrams, and decisions:

| Field | Record |
| --- | --- |
| status | `shipped`, `in-progress`, `candidate`, `deferred`, `blocked`, `unknown`, or a validation state |
| evidence | precise source path, test, config, migration, route, command result, maintained document, or approved external source |
| confidence | confirmed, partial, inferred, or absent |
| gap | missing fact, conflict, risk, or limiting condition |
| next action | concrete check, decision, implementation, or validation step; owner when known |

## 1. Project summary and market reality — Node01

Show these facts near the top because product scope gives architecture and progress their meaning:

| Area | Capture |
| --- | --- |
| identity | project name, concise description, lifecycle/release state, and current owner when known |
| people | target user, buyer, beneficiary, role, situation, and first reachable audience/channel |
| problem | current workaround/status quo, pain, cost of doing nothing, and switching trigger |
| promise | narrow outcome, value path, why now, and the first observable success moment |
| market evidence | supporting and opposing evidence, confidence, alternatives, and riskiest assumption |
| commercial model | price, currency, billing cadence, package/entitlement, trial/limits, payment state, and evidence; show `unknown` rather than guessed pricing |
| trust | privacy, security, reliability, migration, support, legitimacy, and other adoption objections |

Keep audience, buyer, and beneficiary separate when they differ. Preserve non-goals and rejected scope because they explain why an apparently absent capability is intentional.

## 2. Capability map and delivery — Node01 with implementation evidence

Group capabilities by user outcome or journey stage, not by repository folder. Use one row/card per capability with:

| Field | Capture |
| --- | --- |
| capability | user-facing outcome and related requirement/story ID |
| journey | trigger, key states, first success, and failure/recovery state when material |
| scope | MVP/MAP, later candidate, deferred, rejected, or non-goal |
| delivery | shipped, in-progress, blocked, not-started, or unknown |
| acceptance | observable success criterion and validation state |
| implementation | responsible module/surface, dependency, and evidence |
| risk and action | named gap/blocker, decision trigger, owner, and next action |

Render shipped, in-progress, candidate, deferred/rejected, and unknown work as distinct labeled lanes or a timeline. Do not use color alone, and do not promise candidate work as committed delivery.

## 3. Architecture and runtime shape — Node02

Draw a labeled flow from user intent to durable result. Each node or boundary should state responsibility, input/output, owner, dependencies, evidence, and material failure/recovery behavior.

Include only applicable components, but explicitly mark absent/unknown core layers:

| Layer | Capture |
| --- | --- |
| frontend | user surfaces, client state, routes, rendering, and what the client must not enforce |
| backend/domain | actions/use cases, invariants, authorization enforcement, and module ownership |
| data | repositories/stores, durable records, query/mutation boundaries, tenancy, retention, and concurrency concerns |
| integration | providers, webhooks, imports/exports, contract owner, timeout/retry/reconciliation behavior |
| work execution | jobs, queues, schedules, event lifecycle, acceptance state, executor, retry owner, and visible progress |
| trust and runtime | auth/session model, permissions, environment/deploy boundary, observability, operating cost, and recovery authority |

For material architecture choices, show the selected option, alternatives rejected, rationale/evidence, consequences, cost/reversibility, and the condition that should reopen the decision.

## 4. Technology and data contracts — Node02

### Stack ledger

List frontend, backend, data, infrastructure, testing, CI/CD, analytics/observability, and third-party components. For each, show version when evidenced, responsibility, why it exists, source/configuration location, operating cost, and exit/revisit trigger.

### Database ledger

Show a compact entity map first. Make each table/entity expandable and include:

| Field | Capture |
| --- | --- |
| entity | table/collection name, business purpose, owner, and lifecycle |
| field contract | field name, type, nullable/required, default/generated rule, and business meaning |
| integrity | primary/foreign/unique keys, index, enum/check rule, referential behavior, and migration evidence |
| access | tenant/user boundary, authorization relevance, retention/deletion, sensitive classification, and audit implications |
| relation | cardinality, dependent records, consistency/concurrency behavior, and source evidence |

Do not reveal actual secret values or personal records. Use field names and contract semantics, not production samples.

### API and action ledger

Show a compact endpoint/action index and make each record expandable:

| Field | Capture |
| --- | --- |
| identity | method/event, path or action name, purpose, caller, and owning module |
| access | authentication, permission/tenant rule, rate/entitlement rule when applicable |
| request | required/optional fields, types, validation, idempotency/correlation behavior |
| response | success shape/status, asynchronous acceptance and progress semantics, and consumer impact |
| failure | error codes/shapes, retry/timeout behavior, safe recovery, and user-visible state |
| proof | source route/handler, schema/OpenAPI, contract test, integration test, or explicit gap |

## 5. Control room

End with a decision-ready snapshot:

- release and validation state by environment or current verified boundary;
- top risks, blockers, unknowns, and conflicting evidence with severity/consequence;
- material decision ledger: context, decision, alternatives, consequence, owner, and revisit trigger;
- ordered next actions that name the affected capability/contract and the evidence that will close the item.

Replace superseded current truth in place. For major releases, versions, incidents, migrations, security reviews, experiments, or approved milestones, add a compact record to the linked activity subpage: date/version, scope, evidence, impact, and follow-up. The activity page is historical context only; the current board remains authoritative.
