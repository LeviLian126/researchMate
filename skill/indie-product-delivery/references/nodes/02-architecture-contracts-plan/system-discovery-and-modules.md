# System Discovery and Module Design

Understand the existing system, find reusable paths, define module boundaries and
dependency direction, and choose deployment topology. Use deep-module vocabulary
instead of abstract classification tables.

## Step 1: Read the Node01 spec

Extract from the Node01 handoff: target user, core job, acceptance criteria, scope
(in, out, non-goals), and risk assumptions.

State the architecture question in one sentence:
> What system capability must now exist, for whom, under which constraints, and what
> outcome must remain observable?

Confirm the change does not silently alter product promise (user, pricing, privacy
stance). If a product decision is unresolved, route back to Node01.

## Step 2: Audit existing code

Audit only what is relevant to this change. Do not do a full-repository survey.

**Locate hot spots:**
- If the user named a direction (module, subsystem, pain point), go there directly.
- Otherwise, run `git log --oneline` to find files and areas that keep coming up in
  recent commits. Let those paths pull your attention first.

**What to inspect:**
- Entry points: routes, actions, CLI commands, events
- Domain: use-case owners, state rules, transaction style
- Data: repositories, schema, query filters, constraints
- Access: session, signature, role, tenant enforcement
- External: adapters, jobs, callbacks, timeout and retry conventions
- Tests: framework, helpers, fixtures, assertion style
- Config: env names, feature flags, current diff

For each area, record: what does it own now? Who calls it? What data can it change?
Which pattern is already working and should be preserved?

**Look up facts before asking the user.** Discoverable facts (code, config, docs) are
not questions. Route to Node01 or the user only for product or business decisions.

## Step 3: Build the reuse map

For each sub-problem, find the strongest existing path before proposing new layers.

| Sub-problem | Existing path | Decision | Reason |
|---|---|---|---|
| capability or flow | module, route, job, provider, or none | reuse / extend / replace / new | repo and product fit |

- **Reuse**: a complete suitable path. Use it directly.
- **Extend**: change a proven owner without creating a parallel concept.
- **Replace**: has a named deficiency and an evolution path.
- **New**: no suitable path exists after inspection.

Do not create a second source of truth, a second authorization path, or a second
provider adapter merely because it is locally convenient.

## Step 4: Define module boundaries

Use deep-module vocabulary:

- **Module**: something with an interface and an implementation — a function, class,
  package, or cross-tier slice.
- **Interface**: everything a caller must know to use the module correctly: type
  signature, invariants, ordering constraints, error modes, required configuration,
  and performance characteristics.
- **Seam**: the place where you can alter behavior without editing in that place —
  where the interface lives.
- **Depth**: leverage at the interface. How much behavior can a caller exercise per
  unit of interface they must learn. Deep = large behavior behind a small interface.
- **Adapter**: a concrete thing that satisfies an interface at a seam.

**For each module, ask:**
- Can I reduce the number of methods?
- Can I simplify the parameters?
- Can I hide more complexity inside?
- If I delete this module, does complexity vanish (pass-through, should merge into
  caller) or spread to N callers (it is earning its keep, keep it)?

**Deletion test (mandatory):** For every new or changed module, imagine deleting it.
If complexity vanishes, it is a pass-through — merge it into its caller. If complexity
spreads to multiple callers, it is earning its keep — keep it. The deletion test is
not optional polish. LLM-generated code characteristically over-produces pass-through
modules, premature abstractions, and shallow interfaces. The deletion test catches the
most common architecture failure mode before implementation begins.

**Seam discipline:**
- One adapter means a hypothetical seam. Two adapters means a real one. Do not
  introduce a port unless at least two adapters are justified (typically production
  plus test). A single-adapter seam is just indirection.
- Internal seams (private to the module, used by its own tests) are not exposed through
  the external interface just because tests use them.

**Module layers and dependency direction:**

| Layer | Owns | May depend on | Must not own |
|---|---|---|---|
| UI/view | visible state and user intent | client contract | business truth or authz enforcement |
| entry/controller | transport conversion and request boundary | service/domain | provider-specific policy |
| service/domain | use-case orchestration and invariants | repository/provider contract | transport/UI details |
| repository/data | persistence and query mapping | database/store | caller policy or external workflow |
| provider adapter | external normalization and credentials | provider SDK/protocol | product or business ownership |
| job/script/realtime | scheduled or event lifecycle | service and adapter contract | duplicate domain rules |

Do not introduce a framework merely to make this table look complete. Keep interfaces
stable and mechanisms replaceable where the boundary actually matters.

## Step 5: Classify dependencies, decide test strategy

For each module's dependencies, classify to determine how to test:

| Category | Example | Test strategy |
|---|---|---|
| In-process | pure computation, in-memory state, no I/O | test directly through the interface, no adapter needed |
| Local-substitutable | PGLite for Postgres, in-memory filesystem | use the stand-in in the test suite |
| Remote but owned | your own microservice, internal API | define a port, prod uses HTTP/gRPC adapter, test uses in-memory adapter |
| True external | Stripe, Twilio, third-party services | inject a port, test uses a mock adapter |

**Replace, do not layer:**
- Old unit tests on shallow modules become waste once tests at the deepened module's
  interface exist — delete them.
- Write new tests at the deepened module's interface. The interface is the test surface.
- Tests assert on observable outcomes through the interface, not internal state.
- Tests should survive internal refactors — they describe behavior, not implementation.

## Step 6: Compare architecture forks when there is a real one

Not every change needs this. Only when reasonable engineers could select different
system shapes.

- Always include the current, native, or minimal path as one option.
- Add a more durable path only when its ceiling or exit value is credible.
- For each option: repo fit, contract coverage, complexity, operating cost,
  reversibility, proof burden.
- Recommend one. State why the rejected options are not selected now and how they can
  be revisited.
- Do not manufacture false choices to appear thorough.

## Step 7: Choose deployment topology

Deployment topology is an architecture decision, not an execution detail. Node06
executes the configuration, but the topology shape is decided here.

**Apply the indie baseline** (only when existing conventions are unsafe or stale):

| Layer | Baseline | Reconsider when |
|---|---|---|
| hosting | small VPS, Nginx | hosting, control, or compliance needs differ |
| data | SQLite with PRAGMAs, backups, migrations | write contention, multi-instance, search or analytics pressure |
| backend | vanilla PHP or Python services, repositories, cron | repeated middleware, validation, or auth needs stronger support |
| frontend | vanilla CSS/JS | real shared state, components, or routing needs a build stack |
| realtime | vanilla Node.js only where request/response is the wrong fit | realtime or long-lived protocol is not actually needed |
| external | adapters for Stripe, R2, OpenFreeMap when fit | product, compliance, capability, or exit requirements differ |

Record the condition that makes a change necessary, not "future scale" as a vague
justification. Consider Postgres when write contention, multi-instance, analytics, or
search needs are proven. Consider a queue when retries, long jobs, parallelism, or
durable status are needed. Consider a framework when repeated routing, middleware,
validation, or auth overhead is real.

## When discovery is complete

- The existing system and the change boundary can be stated in one sentence.
- The reuse map is complete (every sub-problem has a reuse, extend, replace, or new
  decision).
- Every new or changed module has passed the deletion test.
- Dependencies are classified (every external dependency has a known test strategy).
- Deployment topology is chosen or confirmed as existing.
- If there was a real architecture fork, 2 to 3 options were compared and one selected.
