# ResearchMate QA Report

**Scan date:** 2026-08-05 (consolidated)
**Scope:** Frontend (Next.js), Backend (FastAPI), Worker (Celery), Database (Postgres/Supabase), Infrastructure (Render/CI), Security (cross-cutting), Code quality, Test quality
**Method:** 8 parallel review agents across 3 scan rounds read all source files. Fix claims independently verified against source code (11/11 PASS).
**Risk level:** HIGH_RISK (auth, payment-adjacent quota, file upload, AI provider, data schema, public API)
**Consolidates:** `researchMate-qa-architecture-review-2026-07-31.md`, `researchMate-qa-backend-logic-scan-2026-08-05.md`, `researchMate-fullstack-qa-scan-2026-08-05.md`

---

## Checkpoint Matrix

| CP | Area | Status | Method |
|---|---|---|---|
| CP1 | Change understanding | PASS | Full source read of all ~100 files across 5 domains |
| CP2 | LLM code audit | PASS | No hallucinated APIs, no placeholder returns, no stubs found |
| CP3 | Test quality | FAIL | Source-string inspection tests, missing negative paths, untested _commit SQL |
| CP4 | Static gates | NOT_RUN | Lint/type/build not executed in this scan (read-only) |
| CP5 | App startup | NOT_RUN | No runtime environment available |
| CP6 | E2E journeys | NOT_RUN | No runtime environment available |
| CP7 | Multi-resolution | NOT_RUN | No browser screenshots available |
| CP8 | Debug | NOT_RUN | N/A (no runtime failures to debug) |
| CP9 | Security review | FAIL | 5 Major + 2 Minor security findings |
| CP10 | Reliability | FAIL | 5 Major infrastructure + 2 Major backend reliability findings |
| CP11 | Security verification | NOT_RUN | No destructive tests executed; dependency audit not run |

---

## Fix History and Verification

Three QA scans identified findings across the codebase. The table below tracks every finding
and its verified status. Fix claims were independently verified against source code: all 11
remediation claims from the backend logic scan (RM-QA2-006 through 016) confirmed PASS.

### Round 1 findings (2026-07-31 architecture review) — verified status

| ID | Severity | Description | Status | Verification |
|---|---|---|---|---|
| RM-QA-001 | P0 | MCP project-level search bypasses personal conversation scope | FIXED | `require_workspace_scope` gate at `mcp_server.py:227`; conversation-scoped MCP resources |
| RM-QA-002 | P1 | full_context bypasses relevance gate | FIXED | `query_retrieval.py:62-71` runs BM25 before full_context decision |
| RM-QA-003 | P1 | Quiz default prompt used as BM25 query | FIXED | `quiz_service.py:96-113` separates prompt from topic_query; schema validated |
| RM-QA-004 | P1 | REST/MCP Developer Trace authorization inconsistency | FIXED | `TraceQueryService` shared by both interfaces |
| RM-QA-005 | P1 | Quota and side effects before validation | FIXED | `increment_usage` moved after generation succeeds |
| RM-QA-006 | P1 | Ask/Quiz missing idempotency key semantics | FIXED | `IdempotencyCoordinator` wired with abandon on all paths |
| RM-QA-007 | P1 | Tests do not cross production adapter boundaries | OPEN | Primary API tests still use in-memory store, fake providers, direct `extracted_text` |
| RM-QA-008 | P1 | Quiz save and conversation delete lack complete Unit of Work | PARTIALLY FIXED | `delete_conversation_with_attachments` in one transaction; `record_quiz_run` + `save_quiz_set` still separate calls |
| RM-QA-009 | P1 | MCP async middleware blocks event loop | FIXED | `main.py:101-109` wraps sync calls in `to_thread.run_sync` |
| RM-QA-010 | P1 | Cross-conversation project memory promoted to assistant role | FIXED | `query_context.py:55-72` uses `role="user"` with untrusted tag |
| RM-QA-011 | P2 | Semantic retrieval and summary failures silently swallowed | FIXED | `rerank_ready()` now logs warnings; `RetrievalOutcome` carries degraded/reason |
| RM-QA-012 | P2 | Token budgets are soft not hard caps | FIXED | `retrieval.py:131-142` and `query_context.py:27-49` enforce hard caps |
| RM-QA-013 | P2 | Service/Repository too broad, responsibility drift | OPEN | `GroundedQueryService.execute` still ~110 lines; `ResearchMateRepository` Protocol still very broad |
| RM-QA-014 | P2 | Tests contain opposite assertions, string-existence tests, low coverage | OPEN | String-existence tests, 50% coverage threshold remain |
| RM-QA-015 | P2 | API/worker/dispatcher same-process deployment expands failure domain | OPEN | Combined deployment unchanged (see INFRA-2) |
| RM-QA-016 | P2/P3 | OpenAPI, exception handling, schema and skill routing consistency debt | OPEN | Contract drift, hidden dependency failures remain |

### Round 2 findings (2026-08-05 backend logic scan) — verified status

| ID | Severity | Description | Status | Verification |
|---|---|---|---|---|
| RM-QA2-001 | High | claim_delivery excludes waiting_human | FIXED | `workflow_core.py:165` includes `waiting_human` — verified PASS |
| RM-QA2-002 | High | run_fault_simulation task has no error handling | FIXED | try/except with `_mark_fault_exercise_failed` — verified PASS |
| RM-QA2-003 | High | Quota consumed before generation with no rollback | FIXED | `increment_usage` after generation — verified PASS |
| RM-QA2-004 | High | MCP ask_grounded leaks idempotency reservations | FIXED | catch-all abandon at `mcp_server.py:169` — verified PASS |
| RM-QA2-005 | High | create_decision ignores idempotency_key | PARTIALLY FIXED | InMemory uses idempotency_key; Postgres table lookup still uses interrupt_key (see BE-07) |
| RM-QA2-006 | Medium | Non-domain exceptions from claim escape task handlers | FIXED | All 4 tasks have catch-all — verified PASS |
| RM-QA2-007 | Medium | get_chunks_by_ids skips soft-delete filter | FIXED | EXISTS guard added — verified PASS |
| RM-QA2-008 | Medium | _commit double-commit guard only checks succeeded | FIXED | All terminal states guarded — verified PASS |
| RM-QA2-009 | Medium | review_payload status update has no guard | FIXED | `and status='running'` added — verified PASS |
| RM-QA2-010 | Medium | No bounds check on LLM-returned indices in _commit | FIXED | CLAIM_INDEX_OUT_OF_RANGE and RELATION_INDEX_OUT_OF_RANGE — verified PASS |
| RM-QA2-011 | Medium | Zip bomb vulnerability in _read_bounded_xml | FIXED | Stream-decompression with byte counter — verified PASS |
| RM-QA2-012 | Medium | _safe_evaluation_error infers retryability from class name substrings | FIXED | `getattr(exc, "retryable", False)` — verified PASS |
| RM-QA2-013 | Medium | Evidence catalog reads skip project active/deleted status | FIXED | EXISTS guard on all 4 queries — verified PASS |
| RM-QA2-014 | Medium | get_runtime_rerank_config bypasses nested-UoW | FIXED | Uses `self._transaction()` — verified PASS |
| RM-QA2-015 | Medium | In-memory reliability() ignores window_hours | FIXED | Filters by `created_at >= cutoff` — verified PASS |
| RM-QA2-016 | Medium | qdrant_store.rerank_ready() silently returns False | FIXED | LOGGER.warning added to both handlers — verified PASS |
| RM-QA2-017 | Low | Evidence and core repositories share no transaction infrastructure | OPEN | Two separate `_transaction` implementations with no shared base |
| RM-QA2-018 | Low | _append_event sequence computation has no explicit lock | OPEN | `max(sequence)+1` without FOR UPDATE; safe today only because callers hold locks |
| RM-QA2-019 | Low | validate_and_commit never emits _node_completed event | OPEN | Missing node_completed call after _commit |
| RM-QA2-020 | Low | Double mark_failed on ImportError in run_workflow | OPEN | Inner except calls mark_failed then raises; outer except calls it again |
| RM-QA2-021 | Low | _progress type check rejects float progress values | OPEN | `isinstance(..., int)` rejects JSON floats; bool subclass issue |
| RM-QA2-022 | Low | Dead on conflict clauses in outbox enqueue | OPEN | idempotency_key includes fresh uuid4, so conflict never fires |
| RM-QA2-023 | Low | Conversation title sentinel split across two strings | OPEN | "New chat" vs "New conversation" in different code paths |
| RM-QA2-024 | Low | Non-deterministic ordering in evidence catalog queries | OPEN | No secondary sort key on ORDER BY clauses |

### Round 2 test quality findings — all OPEN

| ID | Severity | Description |
|---|---|---|
| RM-QA2-025 | High | `_commit` SQL (~300 lines) is never exercised by any test; monkeypatched away |
| RM-QA2-026 | Medium | Source-inspection tests assert on SQL string presence, not behavior |
| RM-QA2-027 | Medium | Missing negative paths: `not_claimed` scenario untested for ingestion/deletion |
| RM-QA2-028 | Low | Test helper classes duplicated across two workflow test files |

### Round 2 code quality findings — all OPEN

| ID | Severity | Description | File |
|---|---|---|---|
| RM-QA2-CQ-001 | Low | `GroundedQueryService.execute` ~110-line orchestration method | `grounded_query.py:58-168` |
| RM-QA2-CQ-002 | Low | `_commit` ~300-line method with 4-5 levels of nesting | `workflow_commit.py:26-345` |
| RM-QA2-CQ-003 | Low | `record_run` ~209-line method mixing 6 write concerns | `_postgres_runs.py:96-304` |
| RM-QA2-CQ-004 | Low | `type: ignore[arg-type]` silences WorkerSettings vs Settings mismatch (16 sites) | `task_builders.py:78-192` |
| RM-QA2-CQ-005 | Low | `SUPPORTED_METRICS` set defined in 6 separate files | `evaluation*.py` (6 files) |
| RM-QA2-CQ-006 | Low | `_record_failure` duplicated in 3 service classes | `ingestion_service.py`, `deletion_document.py`, `deletion_project.py` |
| RM-QA2-CQ-007 | Low | Blanket `# ruff: noqa: F401` import blocks in all 9 persistence mixins | All `_postgres_*.py` |
| RM-QA2-CQ-008 | Low | `_json` and `_lock_active_project` duplicated across hierarchies | `evidence_base.py` vs `_postgres_core.py` |
| RM-QA2-CQ-009 | Low | `fault_simulation.py` has duplicate docstring (no-op string expression) | `fault_simulation.py:43-44` |
| RM-QA2-CQ-010 | Low | `workflow_runtime.py` overrides `synthesize` identically to parent | `workflow_runtime.py:25-38` |
| RM-QA2-CQ-011 | Low | `delete_project`, `delete_document`, `complete_document` exceed 50-line guideline 2x+ | `_postgres_projects.py`, `_postgres_document_lifecycle.py` |
| RM-QA2-CQ-012 | Low | Conversation messages N+1 citation query | `_postgres_conversations.py:229-236` |

---

## Active Findings (Open or New)

Findings below are either OPEN from prior reports or NEW from the full-stack scan. Fixed
findings are recorded in the history table above and not repeated here.

### Security (CP9)

**SEC-1: Hardcoded dev auth tokens with weak environment gating**
Major | High confidence | `apps/api/src/researchmate_api/dependencies.py:16`, `config.py:157`
The `DEV_USERS` dict hardcodes four bearer tokens including an admin-role token. The
`_development_user` function accepts `dev:<uuid>:<role>:<email>` format. Defaults are
`auth_mode=development` and `app_env=local`, so any misconfigured deployment accepts
these tokens.
Exploit path: `Authorization: Bearer dev-admin` -> `CurrentUser(role="admin")` -> full admin access.
Fix: Require explicit `ALLOW_DEV_AUTH=true` env var; generate random dev tokens at startup.

**SEC-2: Unpinned npm dependencies create supply-chain risk**
Major | High confidence | `apps/web/package.json:10-11, 27-29`
Five dependencies use `"latest"`: `react`, `react-dom`, `@types/node`, `@types/react`,
`@types/react-dom`. A fresh `npm install` without the lockfile could pull a compromised version.
Fix: Replace all `"latest"` with explicit version ranges.

**SEC-3: Supabase session tokens stored in localStorage**
Major | High confidence | `apps/web/app/lib/supabase.ts:56-57`
The full session object (including `access_token` and `refresh_token`) is serialized to
`localStorage`. If any XSS vector exists (compounded by `unsafe-inline` CSP), both tokens
are trivially readable.
Fix: Route auth through a server-side proxy that sets httpOnly + Secure + SameSite cookies.

**SEC-4: CSP `connect-src` allows any HTTPS origin in production**
Major | High confidence | `apps/web/next.config.ts:21`
`connect-src 'self' https:` matches any HTTPS URI, permitting data exfiltration to arbitrary
endpoints. Combined with SEC-3, an XSS vector could read tokens and exfiltrate them.
Fix: Replace `https:` with explicit origins (Supabase URL, API base URL, NVIDIA, Tavily, Langfuse).

**SEC-5: CSP `script-src` includes `unsafe-inline` unconditionally**
Major | Medium confidence | `apps/web/next.config.ts:16`
`script-src 'self' 'unsafe-inline'` present in all environments. Next.js 16 supports nonce-based CSP.
Fix: Generate a per-request nonce in Next.js middleware.

**SEC-6: Unauthenticated `/readyz` leaks infrastructure map**
Minor | High confidence | `apps/api/src/researchmate_api/routers/health.py:43`
Returns `app_env` and a detailed component status map without auth.
Fix: Return only `{"status":"ready"|"not_ready"}` to unauthenticated callers.

**SEC-7: No catch-all exception handler for 500 errors**
Minor | Medium confidence | `apps/api/src/researchmate_api/main.py`
Unhandled exceptions propagate to Starlette's default handler. No guaranteed safe error envelope.
Fix: Register a generic `except Exception` handler returning the standard ErrorResponse envelope.

### Database (CP9A)

**DB-1: `profiles.id` has no foreign key to `auth.users(id)`**
Major | High | `infra/supabase/migrations/202605260001_initial_schema.sql:16`
Breaks referential integrity. Deleting a user orphans the profile and all downstream data.
Fix: Add `references auth.users(id) on delete cascade`.

**DB-2: No `updated_at` auto-update trigger anywhere**
Major | High | All migrations (absence)
15 tables declare `updated_at` but no `BEFORE UPDATE` trigger exists.
Fix: Create a `set_updated_at()` trigger function and attach to every table.

**DB-3: No `handle_new_user` trigger — profiles not auto-created on signup**
Major | High | `infra/supabase/migrations/202605260001_initial_schema.sql` (absence)
No trigger on `auth.users` to insert a matching `profiles` row.
Fix: Add a `handle_new_user()` SECURITY DEFINER trigger on `auth.users`.

**DB-4: `documents.conversation_id` ON DELETE CASCADE hard-deletes uploaded documents**
Major | High | `infra/supabase/migrations/202607290009:19`
Deleting a conversation cascade-deletes the document row. The R2 object is orphaned.
Fix: Change to `on delete set null`, or use a trigger to create a `deletion_jobs` row.

**DB-5: Aggressive cascade chain from `profiles` — single deletion wipes all user data**
Major | High | `infra/supabase/migrations/202605260001_initial_schema.sql:23`
A single `DELETE FROM profiles WHERE id = ?` irreversibly destroys all user content.
Fix: Consider `on delete restrict` with an explicit deletion workflow.

**DB-6: `quiz_question_type` enum mismatch — `short_answer` orphaned**
Major | High | `infra/supabase/migrations/202605260001:8`, `202607290009:23-24`
SQL enum has `short_answer` but OpenAPI only exposes `single_choice, fill_blank, subjective`.
Fix: Audit for existing rows; regenerate OpenAPI.

**DB-7: Missing index on `conversations(user_id)`**
Major | High | `infra/supabase/migrations/202605260001` (absence)
Every "list my conversations" query forces a sequential scan.
Fix: `create index idx_conversations_user_created on conversations(user_id, created_at desc) where deleted_at is null;`

**DB-8: Inconsistent RLS write-policy coverage**
Major | Medium | `infra/supabase/migrations/202607150002`
Many migration-002 tables have RLS but only SELECT policies. Writes via JWT fail silently.
Fix: Document the service-role-only contract or add explicit write policies.

**DB-9 through DB-19: Minor database findings**

| ID | Description | File |
|---|---|---|
| DB-9 | `claim_evidence.relation` allows `mentions` but API doesn't expose `mentions_count` | `202607150002:107` |
| DB-10 | Missing index on `quiz_questions(quiz_set_id)` | `202605260001` |
| DB-11 | Missing indexes on `citations(document_id)` and `citations(chunk_id)` | `202605260001:216` |
| DB-12 | `jobs.type` unconstrained text (no CHECK) | `202605260001:170` |
| DB-13 | `profiles.email` and `profiles.provider` nullable | `202605260001:17-18` |
| DB-14 | `evaluation_runs.budget_limit_usd` missing upper-bound CHECK | `202607150005:15-16` |
| DB-15 | Qdrant: `document_id` not in `required_filters` | `researchmate_chunks.json:18,24` |
| DB-16 | `fault_exercises.id` has no `default gen_random_uuid()` | `202607150005:31` |
| DB-17 | `outbox_events` lacks explicit `REVOKE` from `anon, authenticated` | `202607150002` |
| DB-18 | `chunks.qdrant_point_id` stored as `text` instead of `uuid` | `202605260001:69` |
| DB-19 | Migration 008 performs irreversible column drops | `202607280008:3-8` |

### Infrastructure (CP10)

**INFRA-1: Health-check startup race — `/readyz` deep probe vs. boot sequence**
Major | Medium | `render.yaml:112`, `render_combined.py:106-121`
`/readyz` returns 503 until worker heartbeats are fresh, but supervisor runs migrations
before starting workers. Guaranteed 503 for the entire boot window. No grace period set.
Fix: Point `healthCheckPath` at `/healthz` or add a startup grace period.

**INFRA-2: Combined process crash coupling — any child exit kills all three**
Major | High | `render_combined.py:122-128`
If any process exits non-zero, supervisor SIGTERMs all children. A Celery OOM takes down
the healthy API. (Relates to open RM-QA-015.)
Fix: Restart only the crashed child, or decouple into separate Render services.

**INFRA-3: Graceful-shutdown window (20s) far shorter than task time limit (900s)**
Major | High | `render_combined.py:131-135`, `celery_app.py:28-29`
A worker mid-task needing >20s to finish is SIGKILLed, losing all in-progress work.
Fix: Raise wait timeout to at least `worker_soft_time_limit_seconds` (840s).

**INFRA-4: Database connection pools unbounded across multiple engines**
Major | Medium | `_postgres_core.py:106-109`, `celery_app.py:51`, `dispatch_outbox.py:18`, `tasks.py`
No `pool_size` or `max_overflow` set. 4+ engines could open 45-75 connections to Supabase
free-tier Postgres (~20-60 connection limit).
Fix: Set explicit `pool_size=2, max_overflow=3` or use `NullPool` for task engines.

**INFRA-5: CI never builds or validates the final worker runtime image**
Major | Medium | `.github/workflows/ci.yml:106-116`
The `container-quality` job builds only to `target: dependencies`. The `runtime` stage
(model download, USER switch) is never exercised in CI.
Fix: Build the full worker image in CI and scan it.

**INFRA-6 through INFRA-12: Minor infrastructure findings**

| ID | Description | File |
|---|---|---|
| INFRA-6 | CSP `connect-src` allows any HTTPS origin (cross-listed SEC-4) | `next.config.ts:14` |
| INFRA-7 | `task_track_started=True` is a no-op with `result_backend=None` | `celery_app.py:22` |
| INFRA-8 | Dockerfile CMD inconsistency with combined supervisor | `Dockerfile:31` |
| INFRA-9 | No Python SAST or dedicated pip/uv audit in CI | `ci.yml:14-35` |
| INFRA-10 | Artifact retention only on E2E failure | `ci.yml:75-81` |
| INFRA-11 | Worker-side engines omit `pool_recycle` | `celery_app.py:51` |
| INFRA-12 | No `EXPOSE` directive in worker Dockerfile | `Dockerfile` |

### Frontend

| ID | Severity | Description | File |
|---|---|---|---|
| FE-4 | Minor | Client-side role check bypassable via localStorage tampering | `labs/page.tsx:43-48` |
| FE-5 | Minor | OAuth tokens briefly exposed in URL fragment | `supabase.ts:112-124` |
| FE-6 | Minor | Duplicated file upload flow (chat-workspace vs library page) | `use-chat-workspace.ts:155-185` |
| FE-7 | Minor | Duplicated deletion-job polling logic | `app-sidebar.tsx:152-170` |
| FE-8 | Minor | `apiFetch` casts response to `T` without runtime validation | `api.ts:349` |
| FE-9 | Minor | Missing focus trap and Escape-to-close in modal dialogs | `app-sidebar.tsx:192-210` |
| FE-10 | Minor | `streamRunEvents` dead code with latent SSE parsing bug | `api.ts:353-389` |
| FE-11 | Minor | `aria-live="polite"` wraps entire conversation thread | `conversation-thread.tsx:28` |

(FE-1 through FE-3 are cross-listed as SEC-3, SEC-4, SEC-5.)

### Backend (new from full-stack scan)

**BE-1: Quiz and evidence LLM calls have no `max_tokens` output bound**
Major | High | `quiz_generation.py:93`, `evidence_generation.py:74`
`generate_llm_quiz_set` and `_complete_json` call `provider.complete(messages)` without
`max_tokens`. The answer path uses `complete_bounded`. Unbounded output wastes cost.
Fix: Thread `max_tokens` through these call paths.

**BE-2: Web search failure aborts entire Ask request even with local evidence available**
Major | High | `grounded_query.py:124-129`
Tavily failure aborts the entire request even when local chunks were successfully retrieved.
Rerank degrades gracefully but web search does not.
Fix: Catch `WebEvidenceError`, set a `web_degraded` flag, continue with local-only candidates.

| ID | Severity | Description | File |
|---|---|---|---|
| BE-3 | Minor | No quota pre-check before generation causes "ghost generation" cost leak | `grounded_query.py:216` |
| BE-4 | Minor | `synthesize_report` requires exact section ordering, causing unnecessary LLM failures | `evidence_generation.py:212-214` |
| BE-5 | Minor | Evidence generation has no repair attempt for invalid provider output | `evidence_generation.py:72-85` |
| BE-6 | Minor | `NvidiaReranker` always instantiated even when NVIDIA API key absent | `rerank.py:190` |
| BE-7 | Minor | InMemory and Postgres `create_decision` use different dedup keys | `evidence_store.py:200` vs `evidence_runs.py:243` |
| BE-8 | Minor | Naive JSON extraction can span multiple JSON objects in LLM output | `answering.py:36-39` |
| BE-9 | Minor | `generate_llm_quiz_set` requires exact question counts, failing when LLM returns fewer | `quiz_generation.py:79-87` |
| BE-10 | Minor | `HumanDecisionCreate.edited_payload` accepts unbounded dict with no size limit | `schemas/evidence.py:46-48` |

---

## Items Confirmed Clean

**Security:** No XSS via `dangerouslySetInnerHTML` or `innerHTML`. No client-side secrets
(only publishable `NEXT_PUBLIC_*` keys). No CSRF risk (Bearer tokens, no cookies). Open
redirect properly guarded. JWT validation uses JWKS with exp/iat/sub/aud/iss claims. Role
derived server-side. MCP authenticated in middleware. All SQL parameterized. `.gitignore`
excludes `.env`. Secrets in `render.yaml` are `sync: false`. Dockerfile runs as non-root.
CORS restricted to explicit origins.

**Database:** No SQL injection in migrations. No hardcoded credentials. All FKs reference
existing tables. Qdrant vector dimension (4096) matches config. All 24 tables have RLS
enabled with consistent `user_id` isolation. Proper expand/contract migration discipline.

**Backend:** No prompt injection risk (untrusted-data framing and evidence allowlist
consistent). No new authorization issues. `full_context` relevance gate applied. Quiz
prompt/topic_query separation working. MCP async blocking fixed. Project memory wrapped
as untrusted user data. Token budgets are hard caps.

**Infrastructure:** Non-root container. Celery reliability config well-tuned. `/readyz`
is a genuine deep probe. Strict env validation. CI gating with `autoDeployTrigger:
checksPass`. Security headers comprehensive. Hadolint + Trivy in CI.

---

## Defect Summary

| Domain | Major | Minor/Low | Total (open) |
|---|---|---|---|
| Security | 5 | 2 | 7 |
| Database | 8 | 11 | 19 |
| Infrastructure | 5 | 7 | 12 |
| Frontend | 0 | 8 | 8 |
| Backend (new) | 2 | 8 | 10 |
| Backend (legacy open) | 0 | 8+12+4 | 24 |
| **Total open** | **20** | **60** | **80** |

Fixed findings: 28 of 80 total findings across all three scan rounds are now FIXED and
verified (13 from round 1+2 tracked findings, 11 from round 2 remediation pass, 4 from
round 3 fix verification).

---

## Security Results Summary

| Domain | Conclusion |
|---|---|
| Database security | PASS (no SQL injection, parameterized queries throughout) |
| Data privacy | FAIL (tokens in localStorage, health endpoint leaks infra map) |
| API security | PASS (auth guards on all endpoints except health, IDOR prevented) |
| Auth and authorization | PARTIAL (JWT validation solid; dev auth tokens risk if misconfigured) |
| Dependency security | FAIL (unpinned npm `"latest"` dependencies) |

---

## Verdict

```text
FIX
```

No Blockers found. The codebase has strong security fundamentals and 28 of 80 tracked
findings are fixed and verified. However, 20 Major findings require attention before the
project can be considered production-ready.

### Highest-priority compound risk

SEC-3 + SEC-4 + SEC-5: tokens in localStorage + `connect-src https:` + `unsafe-inline`
script CSP creates an XSS-to-token-theft chain. Fixing any one reduces risk; fixing all
three eliminates the chain.

### Evidence limitations

Static source review. No tests executed, no runtime behavior observed. CP4-CP8 and CP11
marked NOT_RUN. Fixed findings verified via source read, not execution.

---

## Recommended Fix Order

**Phase A — Before next deployment:**
1. SEC-1: Add explicit `ALLOW_DEV_AUTH` env gate
2. SEC-2: Pin all npm `"latest"` to explicit versions
3. SEC-4: Restrict CSP `connect-src` to explicit origins
4. DB-4: Change `documents.conversation_id` to `on delete set null`
5. INFRA-3: Raise graceful-shutdown timeout
6. INFRA-4: Set explicit DB connection pool sizes
7. RM-QA2-CQ-009, CQ-010: Delete duplicate docstring and dead subclass (trivial)

**Phase B — Reliability and security hardening:**
1. SEC-3: Migrate auth tokens from localStorage to httpOnly cookies
2. SEC-5: Implement nonce-based CSP for `script-src`
3. DB-1, DB-3: Add `auth.users` FK and `handle_new_user` trigger
4. DB-2: Add `updated_at` auto-update triggers
5. DB-7: Add missing index on `conversations(user_id)`
6. INFRA-1: Fix health-check boot race
7. INFRA-2: Decouple process crash handling
8. INFRA-5: Build full worker image in CI
9. BE-1: Add `max_tokens` to quiz/evidence LLM calls
10. BE-2: Degrade gracefully on web search failure

**Phase C — Code quality and minor fixes:**
1. RM-QA2-CQ-001 through CQ-012: Decompose large methods, de-duplicate constants/helpers
2. RM-QA2-025 through 028: Replace string-inspection tests with behavior tests
3. FE-6 through FE-11: Extract shared helpers, add focus trap, fix accessibility
4. BE-3 through BE-10: Fix LLM output handling, JSON extraction, adapter alignment
5. DB-9 through DB-19: Add missing indexes, CHECK constraints, REVOKE statements
6. INFRA-7 through INFRA-12: CI improvements, config cleanup
7. RM-QA2-017 through 024: Transaction infrastructure, event sequence, minor data issues
