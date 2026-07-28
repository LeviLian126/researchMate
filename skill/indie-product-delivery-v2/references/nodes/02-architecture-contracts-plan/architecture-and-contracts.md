# Architecture, Contracts, and Build Plan

Turn approved product scope and repository evidence into explicit system, data, interface, permission, provider, and failure contracts that implementation must not guess. The goal is a design where a convenient assumption can't quietly become a contract.

## Sections
- [Intake and system discovery](#intake-and-system-discovery)
- [Choose a design mode](#choose-a-design-mode)
- [Boundaries and contracts](#boundaries-and-contracts)
- [Architecture decisions](#architecture-decisions)
- [Compare real forks](#compare-real-forks)
- [Low-cost indie baseline](#low-cost-indie-baseline)
- [Module responsibilities and dependency direction](#module-responsibilities-and-dependency-direction)
- [Build plan and handoff](#build-plan-and-handoff)

## Intake and system discovery

Take product truth without reopening product strategy — the architecture question is "what capability must now exist, for whom, under which constraints, with what observable outcome." If a needed input is missing, route it back to product scope rather than choosing it through technical design.

| Input | Needed before contracts | Route when missing |
|---|---|---|
| workflow | actor, entry, action, observable outcome | product scope (Node 01) |
| scope | keep/defer/reject boundary and non-goals | product scope (Node 01) |
| acceptance | behavior that can succeed or fail | product scope (Node 01) |
| constraints | privacy, payment, time, cost, support, platform | product scope (Node 01) or user |
| current truth | source, config, docs, tests, runtime evidence | repo audit |

Inspect only evidence that touches the slice: current modules, entry points, routes, data access, auth/session, provider adapters, jobs, config, deploy boundary, tests, and recently changed files. Record the source path behind each material claim in the evidence inventory (see `references/methods.md`). Don't let routine repo exploration become a whole-repository audit — unknowns that don't touch the data owner, trust boundary, public compatibility, provider behavior, topology, or recovery can stay named for implementation to resolve.

## Choose a design mode

Pick the narrowest mode that covers the architectural uncertainty. Modes can combine only when their boundaries genuinely interact. Don't choose a mode because an implementation technology sounds interesting — a UI-only change that keeps the same data, contract, and behavior stays in frontend build.

| Mode | Use when | Primary output |
|---|---|---|
| Greenfield | no established repo or system shape exists | minimum viable system boundary |
| Existing extension | an approved feature changes an existing workflow | affected-boundary delta |
| Strict contract | API, data, permission, public action, or event changes | explicit contract model |
| Provider or async | external service, webhook, job, cron, or realtime flow exists | trust and lifecycle path |
| Evolution | migration, removal, compatibility, provider state, or topology changes | old/new and recovery design |
| Developer surface | API, CLI, SDK, package, or integration is the product surface | first-success and upgrade contract |

## Boundaries and contracts

Make the contracts explicit so implementation doesn't have to infer them:

- **System boundary** — which capabilities live inside, which stay outside, where the trust edge is.
- **Data contracts** — entities, fields, types, nullability, uniqueness, indexes, tenant/RLS rules, lifecycle, and relations, with their source.
- **Interface contracts** — every endpoint/action: caller, auth, permission, request, validation, response, status, failure, and idempotency/asynchrony semantics.
- **Permission and trust** — identity, session, role, tenant, and the enforcement point on the server side; what an external caller may and may not assume.
- **Provider contracts** — adapter boundary, credentials handling, timeout/retry/callback convention, and provider-specific failure modes.
- **Failure and recovery** — what's consistent after a crash mid-write, a retry, a provider timeout, or a partial migration.

Confirm a change does not silently alter the product promise, pricing, user role, privacy stance, or first success — those route back to product scope, not through technical design.

## Architecture decisions

The decision ladder names the minimum trigger for adding each layer. Each "addition" is a commitment that costs maintenance and drift; reach for it only when the trigger fires.

| Addition | Minimum trigger |
|---|---|
| dependency | standard/native/existing capability can't meet a named contract |
| abstraction | two actual implementations exist, or a protected boundary needs one |
| provider | honest delivery requires its distinct capability |
| configuration | behavior truly varies by environment, user, plan, or operator policy |
| durable model | current storage can't preserve/query/report the required lifecycle safely |
| async mechanism | the request path can't safely own duration, retry, concurrency, or recovery |

## Compare real forks

When a decision has real alternatives, compare them on the axes that actually decide it, not just the one you noticed first:

| Option | Repo fit | Contract coverage | Complexity | Operating cost | Reversibility | Proof burden | Ceiling and trigger |

Then calibrate the approval against confidence:

| Decision condition | Action |
|---|---|
| current/native path satisfies the contract | select it; record the trigger that would justify leaving |
| two paths are viable but costs differ | compare against active constraints and choose deliberately |
| a material fact is unverified but reversible | use a bounded default and define the observation that revisits it |
| a material fact controls privacy, public behavior, cost, or irreversibility | stop for evidence or required product/technical approval |

## Low-cost indie baseline

For an unconstrained greenfield product, the documented low-cost baseline is a starting point, not a prescription. **Existing repo conventions win unless they're unsafe, stale, or explicitly overridden** — the baseline reflects one author's stack assumption, not a universal default.

| Layer | Baseline | Reconsider when |
|---|---|---|
| hosting/web | a small VPS (Ubuntu + Nginx + PHP-FPM) | hosting, control, compliance, or traffic needs differ |
| backend/workers | vanilla PHP services/repositories, cron, Python tooling | repeated middleware/validation/auth or long work needs stronger support |
| realtime | vanilla Node.js only where request/response is the wrong fit | realtime or a long-lived protocol isn't actually needed |
| data | SQLite with PRAGMAs, backups, migrations | write contention, multi-instance, tenant/search/analytics pressure appears |
| frontend | vanilla CSS/JS | real shared state/components/routing or repo convention demands a build stack |
| edge/private admin | Cloudflare DNS/SSL/Tunnel + Tailscale | exposure, identity, or network policy needs a different boundary |
| paid/external | adapters for Stripe hosted flows, object storage, map tiles | product, compliance, capability, or exit requirements differ |

Reach for Postgres when contention/multi-instance/analytics/search are proven, a queue for durable retries/long jobs/parallelism, a framework when repeated routing/middleware/validation/auth justifies it, and split services on proven isolation/reliability/scaling/deploy-cadence needs. Record the condition that makes the change necessary rather than using "scale" as a vague justification.

## Module responsibilities and dependency direction

Use the smallest model already supported by the repository; name only layers that exist or protect a real boundary.

| Layer | Owns | May depend on | Must not own |
|---|---|---|---|
| UI/view | visible state and user intent | client contract | business truth or authorization enforcement |
| entry/controller | transport conversion and request boundary | service/domain | provider-specific policy |
| service/domain | use-case orchestration and invariants | repository/provider contract | transport/UI details |
| repository/data | persistence/query mapping | database/store | caller policy or external workflow |
| provider adapter | external normalization and credentials | provider SDK/protocol | product/business ownership |
| job/script/realtime process | scheduled/event lifecycle | service and adapter contract | duplicate domain rules |

State shared-module ownership, the allowed dependency direction, duplicate-state risk, and the boundary that prevents reverse dependencies. Don't introduce a framework just to fill this table.

## Build plan and handoff

Slice the work by boundary, sequence by reversibility (cheap reversible steps first, low-reversibility ones last with approval), and record the trigger that would justify revisiting each decision. Preserve complete ledgers — every operated entity, field, index, every endpoint, every failure mode — rather than illustrative samples; a design that omits a real route or schema row will resurface as implementation debt.

If the next work is backend or frontend implementation, open Node 03 or Node 04; if it's a quality or release question, open Node 05 or Node 06. These are topic pointers, not a required order — read whichever the work needs.
