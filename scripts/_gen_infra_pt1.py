import json
from pathlib import Path

OUT = Path(r"D:\software\researchMate\docs\learn")
VENV = r"D:\software\env\researchmate"

MIGRATIONS = [
    ("202605260001_initial_schema.sql","202605260001","15 tables: profiles, projects, documents, document_pages, chunks, conversations, messages, ask_runs, tool_calls, citations, quiz_sets, quiz_questions, jobs, deletion_jobs, api_usage","8 enums, 12 indexes, owner_user_id() helper","RLS on all 15 tables. Owner-scoped auth.uid() policies. Gaps on document_pages/tool_calls/citations/quiz_questions closed in 002.","Creates full core data model. Documents capped at 25 MB, chunks reference Qdrant by qdrant_point_id."),
    ("202607150002_evidence_review_schema.sql","202607150002","15 tables: pipeline_versions, workflow_runs, run_events, research_questions, claims, claim_evidence, claim_relations, reports, report_sections, human_decisions, outbox_events, evaluation_datasets, evaluation_cases, evaluation_runs, evaluation_scores","17 indexes incl GIN on labels; composite PKs; idempotency_key uniqueness","RLS on all 15. Closes 4 gaps from 001. pipeline_versions: dev/admin I/U/D. outbox_events: NO auth policy (service-role).","Adds evidence-review + evaluation subsystem. PostgreSQL = source of truth."),
    ("202607150003_job_delivery_lease.sql","202607150003","No new tables (alters jobs)","Adds attempts, lease_owner, lease_expires_at, started_at, completed_at; idx_jobs_dispatch_lease","No RLS changes.","Safe at-least-once Celery execution with lease concurrency control."),
    ("202607150004_evaluation_delivery_lease.sql","202607150004","No new tables (alters evaluation_runs)","Adds attempts, lease_owner, lease_expires_at; idx_evaluation_runs_dispatch_lease","No RLS changes.","Resumable evaluation-run ownership for bounded parallel case execution."),
    ("202607150005_evaluation_budget_and_fault_exercises.sql","202607150005","fault_exercises (1 new table)","budget_limit_usd (default 1.0 fail-closed), budget_reserved_usd, last_error_code on evaluation_runs; fault_exercises: scenario enum, lease, request_hash","RLS on fault_exercises: owner SELECT + INSERT only.","Fail-closed cost budgets and auditable non-destructive reliability simulations."),
    ("202607160006_runtime_readiness_and_workflow_budget.sql","202607160006","runtime_heartbeats (1 coordination table)","delivery_attempts, lease, budget_limit_usd (default 1.0 max 25), budget_reserved_usd, actual_cost_usd on workflow_runs; runtime_heartbeats: component enum (worker/dispatcher)","RLS on runtime_heartbeats, REVOKE from anon/authenticated. Updated pipeline_versions SELECT for accepted discovery.","Operational readiness monitoring and fail-closed research budgets."),
    ("202607280007_unified_chat_and_runtime_rerank.sql","202607280007","runtime_ai_config (1 coordination table)","summary cols on conversations; ask_run_id on messages; web_enabled, context_strategy (6 values), rerank_provider, rerank_degraded on ask_runs; seeds runtime_ai_config","RLS on runtime_ai_config: admin/dev SELECT + UPDATE. source_mode defaults to local_only (expand phase).","Migrates source_mode to unified context_strategy + rerank. Two-phase expand-then-contract."),
    ("202607280008_remove_source_modes.sql","202607280008","No new tables (contract phase drops columns)","Drops source_mode + resolved_mode from ask_runs; drops source_mode from quiz_sets","No RLS changes.","Contract phase: unified runtime is live before retired columns are removed."),
    ("202607290009_personal_chat_project_memory_and_quiz.sql","202607290009","No new tables (alters projects, documents, enum)","kind (personal/workspace), memory cols on projects with unique partial index; conversation_id on documents; fill_blank + subjective quiz types","No RLS changes.","Personal chat workspace, project memory summaries, expanded quiz types."),
    ("202608010010_api_idempotency.sql","202608010010","api_idempotency (1 coordination table)","Composite PK (user_id, operation, idempotency_key); request_hash SHA-256; state (pending/succeeded); CHECK constraint","RLS on api_idempotency: owner ALL (user_id = auth.uid()).","Persists replay-safe request identities for cost-bearing Ask and Quiz operations."),
]

SCRIPTS_DATA = [
    ("apply_migrations.py","Python","96","Validates and applies ordered additive PostgreSQL migrations. Enforces unique version prefixes, rejects empty files and DROP DATABASE, acquires pg_advisory_xact_lock, tracks with SHA-256 checksums. Requires ALLOW_SCHEMA_APPLY=1.","Two modes: --check-files (validation) and --apply (execution). Advisory lock key 726334129. Single transaction per run."),
    ("bootstrap_demo_catalog.py","Python","150","Bootstraps an accepted demo pipeline version and frozen evaluation dataset from ready project chunks. Requires ALLOW_DEMO_BOOTSTRAP=1.","Reads up to --case-limit (default 10, max 50) ready chunks, generates evaluation cases, freezes dataset, returns JSON with pipeline_version_id + dataset_id."),
    ("check_contracts.ps1","PowerShell","14","Validates core repository contracts via pytest (test_project_scaffold, test_api_workflow, test_frontend_contracts) with pinned venv at " + VENV + ".","Creates venv if missing; optional -InstallDependencies runs uv sync --frozen --all-packages --group dev."),
    ("dev_api.ps1","PowerShell","13","Starts local reloadable uvicorn API on 127.0.0.1:8000 with pinned venv at " + VENV + ".","Creates venv if missing; optional -InstallDependencies. Runs: python -m uvicorn researchmate_api.main:app --reload --host 127.0.0.1 --port 8000"),
    ("export_openapi.py","Python","36","Renders FastAPI OpenAPI schema as deterministic YAML, writes or verifies infra/openapi/openapi.yaml. Uses Settings(app_env=test, llm_provider=fake).","Default writes file; --check fails if tracked copy is stale. Inserts apps/api/src for module resolution."),
    ("provision_qdrant_rerank.py","Python","152","Provisions and verifies Qdrant rerank backfill. Creates researchmate_chunks_v2 with multivector embeddings, payload indexes, batch backfill. Requires ALLOW_QDRANT_RERANK_BACKFILL=1 and QDRANT_RERANK_MODEL_IS_FREE=true.","Backfill version 20260728_answerai_colbert_small_v1. Creates researchmate_vector_migrations, verifies point count + tenant-filter sample, stores SHA-256 digest."),
    ("repair_docs_html_encoding.py","Python","83","Repairs HTML documentation encoding damage. Restores corrupted nav labels, fixes summary tags, restores lead paragraphs, replaces inline styles with shared site.css.","Two passes: repair_common_wrappers (regex) and unify_shared_styles (relative path calculation)."),
    ("setup_langgraph_checkpoint.py","Python","26","Creates LangGraph checkpoint tables during approved schema phase. Converts DATABASE_URL and calls PostgresSaver.setup(). Requires ALLOW_SCHEMA_APPLY=1.","LangGraph owns/checkpoints its DDL. Run only during protected release migration phase, never during task delivery."),
]

TABLES_DATA = [
    ("profiles","001","identity","id (PK), email, provider, role (user/developer/admin)","auth.uid() = id (SELECT)"),
    ("projects","001","identity","id (PK), user_id, name, status, kind, memory_summary_text","auth.uid() = user_id (ALL)"),
    ("documents","001","documents","id (PK), user_id, project_id, filename, file_type, status, r2_object_key","auth.uid() = user_id (ALL)"),
    ("document_pages","001","documents","id (PK), document_id, page_no, slide_no, text, metadata","Inherited via documents (SELECT, 002)"),
    ("chunks","001","documents","id (PK), user_id, project_id, document_id, source_type, text, qdrant_point_id","auth.uid() = user_id (ALL)"),
    ("conversations","001","chat","id (PK), user_id, project_id, title, summary_text, summary_token_count","auth.uid() = user_id (ALL)"),
    ("messages","001","chat","id (PK), user_id, project_id, conversation_id, role, content, ask_run_id","auth.uid() = user_id (ALL)"),
    ("ask_runs","001","chat","id (PK), user_id, project_id, conversation_id, message, task_type, context_strategy, rerank_provider, web_enabled","auth.uid() = user_id (ALL)"),
    ("tool_calls","001","chat","id (PK), ask_run_id, tool_name, input, output_summary, status, latency_ms","Inherited via ask_runs (SELECT, 002)"),
    ("citations","001","chat","id (PK), ask_run_id, chunk_id, document_id, source_type, quote, claim_id","Inherited via ask_runs (SELECT, 002)"),
    ("quiz_sets","001","quiz","id (PK), user_id, project_id, ask_run_id, title, sources_summary","auth.uid() = user_id (ALL)"),
    ("quiz_questions","001","quiz","id (PK), quiz_set_id, type, question, options, answer, explanation, difficulty","Inherited via quiz_sets (SELECT, 002)"),
    ("jobs","001","ops","id (PK), user_id, project_id, document_id, type, status, progress, attempts, lease_owner","auth.uid() = user_id (ALL)"),
    ("deletion_jobs","001","ops","id (PK), user_id, project_id, document_id, status, target_types","auth.uid() = user_id (ALL)"),
    ("api_usage","001","ops","id (PK), user_id, usage_date, kind, count, unique(user_id, usage_date, kind)","auth.uid() = user_id (ALL)"),
    ("pipeline_versions","002","evidence","id (PK), name, version, status, configuration, prompt_hash, code_sha, created_by","Accepted=public; draft/candidate=creator+admin; dev/admin I/U/D"),
    ("workflow_runs","002","evidence","id (PK), user_id, project_id, pipeline_version_id, kind, status, idempotency_key, budget_limit_usd, lease_owner","auth.uid() = user_id (SELECT + INSERT)"),
    ("run_events","002","evidence","id (bigint PK), run_id, sequence, node_key, event_type, attempt, status, cost_usd","Inherited via workflow_runs (SELECT)"),
    ("research_questions","002","evidence","id (PK), user_id, project_id, parent_id, source_run_id, question, status, priority, plan_order","auth.uid() = user_id (SELECT)"),
    ("claims","002","evidence","id (PK), user_id, project_id, question_id, source_run_id, text, normalized_key, stance, confidence, review_status","auth.uid() = user_id (SELECT)"),
    ("claim_evidence","002","evidence","claim_id + citation_id + relation (PK), extraction_score, extractor_version","Dual inherited via claims + citations (SELECT)"),
    ("claim_relations","002","evidence","source_claim_id + target_claim_id + relation (PK), confidence, rationale_summary","Dual inherited via source + target claims (SELECT)"),
    ("reports","002","evidence","id (PK), user_id, project_id, source_run_id, title, status, revision, validation_status","auth.uid() = user_id (SELECT)"),
    ("report_sections","002","evidence","id (PK), report_id, parent_section_id, section_key, position, heading, body_markdown, evidence_snapshot","Inherited via reports (SELECT)"),
    ("human_decisions","002","evidence","id (PK), run_id, event_id, user_id, interrupt_key, decision, proposed_payload, final_payload","Inherited via workflow_runs (SELECT); INSERT owner or dev/admin"),
    ("outbox_events","002","evidence","id (PK), aggregate_type, aggregate_id, event_type, payload, idempotency_key, status, attempts","NO auth-user policy (service-role only)"),
    ("evaluation_datasets","002","evaluation","id (PK), user_id, project_id, name, version, status, description","Owner SELECT + I/U/D (draft only)"),
    ("evaluation_cases","002","evaluation","id (PK), dataset_id, case_key, input, expected_output, expected_evidence, labels","Inherited via evaluation_datasets (draft-only writes)"),
    ("evaluation_runs","002","evaluation","id (PK), user_id, project_id, dataset_id, pipeline_version_id, status, idempotency_key, budget_limit_usd, lease_owner","Owner SELECT + INSERT (frozen dataset required)"),
    ("evaluation_scores","002","evaluation","id (PK), evaluation_run_id, case_id, metric_name, metric_version, value, passed, judge_model","Inherited via evaluation_runs (SELECT)"),
    ("fault_exercises","005","evaluation","id (PK), requested_by, target_run_id, scenario, duration_seconds, status, request_hash, idempotency_key, lease_owner","Owner SELECT + INSERT (requested_by = auth.uid())"),
    ("runtime_heartbeats","006","coordination","component (PK: worker/dispatcher), instance_id, status, safe_metadata, updated_at","RLS enabled, REVOKE from anon/authenticated"),
    ("runtime_ai_config","007","coordination","config_key (PK), provider, version, updated_at, updated_by","Admin/developer SELECT + UPDATE only"),
    ("api_idempotency","010","coordination","user_id + operation + idempotency_key (PK), request_hash, state, response","Owner ALL (user_id = auth.uid())"),
]
TAG_DATA = [
    ("health",2,["GET /api/v1/healthz","GET /api/v1/readyz"]),
    ("auth",1,["GET /api/v1/me"]),
    ("projects",5,["POST /api/v1/projects","GET /api/v1/projects","GET /api/v1/projects/{project_id}","PATCH /api/v1/projects/{project_id}","DELETE /api/v1/projects/{project_id}"]),
    ("documents",7,["POST /api/v1/documents/upload-url","POST /api/v1/documents","GET /api/v1/documents","GET /api/v1/projects/{project_id}/documents","GET /api/v1/conversations/{conversation_id}/documents","GET /api/v1/documents/{document_id}","POST /api/v1/documents/{document_id}/complete","DELETE /api/v1/documents/{document_id}"]),
    ("jobs",1,["GET /api/v1/jobs/{job_id}"]),
    ("conversations",8,["POST /api/v1/conversations","GET /api/v1/conversations","GET /api/v1/projects/{project_id}/conversations","GET /api/v1/conversations/{conversation_id}/messages","POST /api/v1/conversations/{conversation_id}/messages","GET /api/v1/conversations/{conversation_id}","PATCH /api/v1/conversations/{conversation_id}","DELETE /api/v1/conversations/{conversation_id}"]),
    ("ask",1,["POST /api/v1/ask"]),
    ("quiz",2,["POST /api/v1/quiz","GET /api/v1/projects/{project_id}/quiz"]),
    ("sources",1,["GET /api/v1/runs/{run_id}/sources"]),
    ("developer-trace",1,["GET /api/v1/dev/traces/{trace_id}"]),
    ("evidence-review",16,["POST /api/v1/research-runs","GET /api/v1/runs/{run_id}","GET /api/v1/runs/{run_id}/events","POST /api/v1/runs/{run_id}/decisions","GET /api/v1/projects/{project_id}/claims","GET /api/v1/projects/{project_id}/claim-relations","GET /api/v1/projects/{project_id}/reports","GET /api/v1/reports/{report_id}","GET /api/v1/pipeline-versions","GET /api/v1/evaluation-datasets","POST /api/v1/reports/{report_id}/refresh","POST /api/v1/evaluation-runs","GET /api/v1/evaluation-runs/{evaluation_run_id}","POST /api/v1/dev/reliability","POST /api/v1/dev/fault-scenarios","DELETE /api/v1/dev/fault-scenarios/{exercise_id}"]),
]

ALL_SCHEMAS = ["AskRequest","AskResponse","Citation","ClaimListResponse","ClaimRelationListResponse","ClaimRelationSummary","ClaimSummary","ConversationCreate","ConversationListResponse","ConversationMessage","ConversationMessagesResponse","ConversationSummary","ConversationUpdate","CurrentUser","DeveloperTrace","Difficulty","DocumentRecord","DocumentStatus","ErrorDetail","ErrorResponse","EvaluationDatasetListResponse","EvaluationDatasetSummary","EvaluationRunAccepted","EvaluationRunCreate","EvaluationRunRecord","ExecutionPlan","FaultScenarioAccepted","FaultScenarioCreate","FaultScenarioRecord","HumanDecisionAccepted","HumanDecisionCreate","JobRecord","JobStatus","PipelineVersionListResponse","PipelineVersionSummary","ProjectCreate","ProjectRecord","QuizCoverage","QuizHistoryResponse","QuizQuestion","QuizRequest","QuizResponse","QuizSet","ReliabilityResponse","ReportDetail","ReportListResponse","ReportRefreshAccepted","ReportRefreshCreate","ReportSectionRecord","ReportSummary","ResearchRunAccepted","ResearchRunCreate","RunSourcesResponse","RuntimeRerankConfig","RuntimeRerankConfigUpdate","SourceScope","SourceSummary","SourceType","TaskType","ToolCallTrace","UploadCompleteRequest","UploadUrlRequest","UploadUrlResponse","WorkflowRunRecord"]

PROOF_STEPS = [
    ("Enforce unique prefixes","migration_files() sorts all .sql files and verifies version prefixes (YYYYMMDDNNN before first underscore) are unique."),
    ("Reject destructive content","validate_files() strips each file, rejects empty migrations, blocks any file containing DROP DATABASE (case-insensitive)."),
    ("Approval gate","The apply path requires ALLOW_SCHEMA_APPLY=1. Without it the script exits immediately before touching the database."),
    ("Advisory transaction lock","pg_advisory_xact_lock(726334129) serializes migration execution within the current transaction, preventing concurrent runners."),
    ("Tracking table bootstrap","Creates researchmate_schema_migrations (version PK, checksum_sha256, applied_at) if not exists, reads all applied rows."),
    ("Checksum verification","For each file already applied, recomputes SHA-256 and compares. Any drift raises RuntimeError, halting the run."),
    ("Apply and record","Unapplied migrations are executed in order inside the transaction, then inserted with SHA-256 digest. Transaction commits once."),
]

RELATIONS = [
    ("profiles","projects","cascade","user_id"),
    ("projects","documents","cascade","project_id"),
    ("documents","document_pages","cascade","document_id"),
    ("projects","chunks","cascade","project_id"),
    ("documents","chunks","cascade","document_id"),
    ("projects","conversations","cascade","project_id"),
    ("conversations","messages","cascade","conversation_id"),
    ("conversations","documents","cascade","conversation_id (009)"),
    ("projects","ask_runs","cascade","project_id"),
    ("ask_runs","tool_calls","cascade","ask_run_id"),
    ("ask_runs","citations","cascade","ask_run_id"),
    ("ask_runs","quiz_sets","set null","ask_run_id"),
    ("quiz_sets","quiz_questions","cascade","quiz_set_id"),
    ("pipeline_versions","workflow_runs","restrict","pipeline_version_id"),
    ("workflow_runs","run_events","cascade","run_id"),
    ("workflow_runs","research_questions","cascade","source_run_id"),
    ("research_questions","claims","set null","question_id"),
    ("claims","claim_evidence","cascade","claim_id"),
    ("citations","claim_evidence","cascade","citation_id"),
    ("claims","claim_relations","cascade","source/target_claim_id"),
    ("workflow_runs","reports","restrict","source_run_id"),
    ("reports","report_sections","cascade","report_id"),
    ("workflow_runs","human_decisions","cascade","run_id"),
    ("evaluation_datasets","evaluation_cases","cascade","dataset_id"),
    ("pipeline_versions","evaluation_runs","restrict","pipeline_version_id"),
    ("evaluation_runs","evaluation_scores","cascade","evaluation_run_id"),
    ("workflow_runs","fault_exercises","set null","target_run_id"),
]
NAV_ITEMS = [("../index.html","Overview"),("../product/index.html","Product & roadmap"),("../architecture/index.html","Architecture & stack"),("../contracts/data/index.html","Database"),("../contracts/api/index.html","API"),("index.html","Learn")]
MODULES = [("frontend","Frontend"),("backend","Backend"),("worker","Worker"),("infra","Infrastructure"),("cicd","CI/CD"),("contracts-tests","Contracts & Tests")]
TOC_ITEMS = [("#stack","Tech stack"),("#tree","Directory tree"),("#migrations","SQL migrations"),("#tables","Table inventory"),("#qdrant","Qdrant"),("#openapi","OpenAPI"),("#scripts","Scripts"),("#proof-chain","Proof chain"),("#relationships","Relationships"),("#further","Further reading")]
LINKS = [("../contracts/data/index.html","Database contracts","Full table definitions, RLS policies, and data lifecycle."),("../contracts/api/index.html","API contracts","Request/response specs and auth flow for 45 endpoints."),("../architecture/index.html","Architecture & stack","System layers, data flow, and security boundaries."),("backend.html","Backend guide","File-by-file source analysis of the FastAPI app."),("worker.html","Worker guide","Celery worker task delivery and lease mechanism."),("cicd.html","CI/CD","Continuous integration and deployment pipeline.")]

def build(lang):
    zh = lang == "zh"
    h = []
    h.append("<!DOCTYPE html>")
    h.append('<html lang="' + ("zh-CN" if zh else "en") + '">')
    h.append("<head>")
    h.append('  <meta charset="utf-8"/>')
    h.append("  <title>Infrastructure . infra &amp; scripts</title>")
    h.append('  <meta name="viewport" content="width=device-width, initial-scale=1"/>')
    h.append('  <link href="../assets/site.css" rel="stylesheet"/>')
    h.append("</head>")
    h.append("<body>")
    stamp = "Infrastructure . 6 August 2026"
    lang_label = "Chinese" if not zh else "English"
    lang_href = "infra.zh.html" if not zh else "infra.html"
    lang_hreflang = "zh" if not zh else "en"
    lang_lang = "zh" if not zh else "en"
    h.append('  <header class="mast"><div class="shell mast-row"><a class="brand" href="../index.html">ResearchMate documentation</a><div class="mast-right"><span class="stamp">' + stamp + '</span><a class="lang-toggle" href="' + lang_href + '" hreflang="' + lang_hreflang + '" lang="' + lang_lang + '">' + lang_label + '</a></div></div></header>')
    h.append('  <nav aria-label="Documentation" class="global"><div class="shell">')
    for href,label in NAV_ITEMS:
        ac = ' aria-current="page"' if label == "Learn" else ""
        h.append('    <a' + ac + ' href="' + href + '">' + label + '</a>')
    h.append("  </div></nav>")
    h.append('  <nav aria-label="Learning modules" class="global module-nav"><div class="shell">')
    for key,label in MODULES:
        ac = ' aria-current="page"' if key == "infra" else ""
        h.append('    <a' + ac + ' href="' + key + '.html">' + label + '</a>')
    h.append("  </div></nav>")
    h.append('  <main class="shell">')
    h.append('    <div class="hero">')
    h.append('      <p class="eyebrow">Supabase / PostgreSQL RLS / Qdrant / 10 migrations / 45 endpoints</p>')
    h.append("      <h1>Infrastructure . infra &amp; scripts</h1>")
    lede = "The ResearchMate infrastructure layer defines all persistence and coordination infrastructure: Supabase/PostgreSQL as the single source of truth, Qdrant for vector retrieval, and an OpenAPI spec locking down 45 endpoints. This page walks through every file in infra/ (10 SQL migrations, 2 Qdrant collection configs, 1 OpenAPI spec) and scripts/ (8 operational scripts)."
    h.append('      <p class="lede">' + lede + '</p>')
    h.append('      <div class="meta">')
    for text in ["34 tables (31 business + 3 coordination)","10 SQL migrations","2 Qdrant collections","45 endpoints / 11 tags","65 schemas","8 scripts"]:
        h.append('        <span class="status local">' + text + '</span>')
    h.append("      </div>")
    h.append("    </div>")
    h.append('    <div class="layout"><div class="content">')
    h.append('      <section id="stack">')
    h.append('        <p class="eyebrow">Technology stack fundamentals</p>')
    h.append("        <h2>5 infrastructure components</h2>")
    h.append('        <p class="sub">Each card explains what the component does in general and how ResearchMate uses it specifically.</p>')
    h.append('        <div class="grid">')
    facts = [
        ("Supabase","Managed PostgreSQL platform providing database, auth (auth.uid()), storage, and Edge Functions. ResearchMate uses its PostgreSQL instance as the single source of truth; all business and coordination tables live here. RLS policies enforce multi-tenant isolation at the database layer."),
        ("PostgreSQL RLS","Row Level Security enforces per-row access control in the database. All 31 business tables have RLS enabled, using auth.uid() for user-scoped isolation. pipeline_versions supports developer/admin role policies; outbox_events has no authenticated-user policy (service-role only)."),
        ("Database migrations","10 additive SQL migrations ordered by YYYYMMDDNNN version prefix. apply_migrations.py executes under an advisory lock, tracks applied migrations with SHA-256 checksums, and rejects DROP DATABASE and empty files."),
        ("Qdrant collections","Two vector collections: researchmate_chunks (v1, dense 4096-dim + sparse, RRF fusion) and researchmate_chunks_v2 (multivector 96-dim, MAX_SIM, late-interaction rerank). Both enforce user_id + project_id + source_type triple filtering."),
        ("OpenAPI spec","45 endpoints across 11 tags, 65 schemas (including HTTPBearer security scheme). openapi.yaml is deterministically rendered from the FastAPI app by export_openapi.py, with a --check mode to verify the tracked artifact is not stale."),
    ]
    for title,body in facts:
        h.append('          <article class="fact"><b>' + title + '</b><p>' + body + '</p></article>')
    h.append("        </div>")
    h.append("      </section>")
    h.append('      <section id="tree">')
    h.append('        <p class="eyebrow">Complete directory tree</p>')
    h.append("        <h2>infra/ and scripts/ file structure</h2>")
    h.append('        <p class="sub">infra/ contains 3 subdirectories (openapi, qdrant, supabase); scripts/ contains 8 script files.</p>')
    tree = "infra/\n  openapi/\n    openapi.yaml              168 KB  45 endpoints / 11 tags / 65 schemas\n  qdrant/\n    researchmate_chunks.json  676 B   v1 collection config (dense + sparse + RRF)\n  supabase/\n    migrations/\n      202605260001_initial_schema.sql                   11.9 KB\n      202607150002_evidence_review_schema.sql           22.2 KB\n      202607150003_job_delivery_lease.sql                499 B\n      202607150004_evaluation_delivery_lease.sql          422 B\n      202607150005_evaluation_budget_and_fault_exercises.sql  2.7 KB\n      202607160006_runtime_readiness_and_workflow_budget.sql  2.4 KB\n      202607280007_unified_chat_and_runtime_rerank.sql   3.3 KB\n      202607280008_remove_source_modes.sql                253 B\n      202607290009_personal_chat_project_memory_and_quiz.sql  1.1 KB\n      202608010010_api_idempotency.sql                   1.1 KB\n\nscripts/\n  apply_migrations.py            3.6 KB  Validate &amp; apply ordered migrations\n  bootstrap_demo_catalog.py      5.8 KB  Bootstrap demo pipeline + eval dataset\n  check_contracts.ps1              524 B  Run pytest contract tests\n  dev_api.ps1                      491 B  Start uvicorn dev server\n  export_openapi.py              1.2 KB  Render/verify OpenAPI artifact\n  provision_qdrant_rerank.py     6.3 KB  Provision Qdrant v2 backfill\n  repair_docs_html_encoding.py   3.3 KB  Repair corrupted HTML docs\n  setup_langgraph_checkpoint.py    979 B  Create LangGraph checkpoint tables"
    h.append('        <pre class="command-block"><code>' + tree + '</code></pre>')
    h.append("      </section>")
    h.append('      <section id="migrations">')
    h.append('        <p class="eyebrow">SQL migration file-by-file analysis</p>')
    h.append("        <h2>10 migrations in execution order</h2>")
    h.append('        <p class="sub">Each migration is additive (never destructive to existing data), ordered by the YYYYMMDDNNN version prefix.</p>')
    for i,m in enumerate(MIGRATIONS,1):
        mid = "migration-%02d" % i
        h.append('        <details id="' + mid + '"><summary>' + str(i) + '. ' + m[0] + '</summary>')
        h.append('          <dl class="kv">')
        h.append('            <dt>Version</dt><dd><code>' + m[1] + '</code></dd>')
        h.append('            <dt>Tables</dt><dd>' + m[2] + '</dd>')
        h.append('            <dt>Fields &amp; indexes</dt><dd>' + m[3] + '</dd>')
        h.append('            <dt>RLS</dt><dd>' + m[4] + '</dd>')
        h.append('            <dt>Incremental change</dt><dd>' + m[5] + '</dd>')
        h.append('          </dl>')
        h.append('        </details>')
    h.append("      </section>")
    h.append('      <section id="tables">')
    h.append('        <p class="eyebrow">Database table inventory</p>')
    h.append("        <h2>34 tables (31 business + 3 coordination)</h2>")
    h.append('        <p class="sub">31 business tables support user data, documents, chat, evidence review, and evaluation. 3 coordination tables (runtime_heartbeats, runtime_ai_config, api_idempotency) serve backend operations.</p>')
    h.append('        <div class="scroll"><table class="dense">')
    h.append('          <thead><tr>')
    for hdr in ["#","Table","Migration","Group","Key columns","RLS policy"]:
        h.append('            <th>' + hdr + '</th>')
    h.append('          </tr></thead>')
    h.append('          <tbody>')
    for idx,t in enumerate(TABLES_DATA,1):
        name,mig,group,cols,rls = t
        coord = ' <span class="tag warn">coord</span>' if group == "coordination" else ""
        h.append('            <tr id="table-' + name + '">')
        h.append('              <td>' + str(idx) + '</td>')
        h.append('              <td><code>' + name + '</code>' + coord + '</td>')
        h.append('              <td><code>' + mig + '</code></td>')
        h.append('              <td>' + group + '</td>')
        h.append('              <td>' + cols + '</td>')
        h.append('              <td>' + rls + '</td>')
        h.append('            </tr>')
    h.append('          </tbody>')
    h.append('        </table></div>')
    h.append("      </section>")
    h.append('      <section id="qdrant">')
    h.append('        <p class="eyebrow">Qdrant configuration</p>')
    h.append("        <h2>Two vector collections</h2>")
    h.append('        <p class="sub">researchmate_chunks is the primary retrieval collection (dense + sparse + RRF fusion); researchmate_chunks_v2 is the rerank backfill collection (multivector late-interaction). Both enforce tenant filtering.</p>')
    h.append("        <h3>researchmate_chunks (v1)</h3>")
    h.append('        <p>Primary retrieval collection, defined in <code>infra/qdrant/researchmate_chunks.json</code>. Supports hybrid retrieval: dense vectors (4096 dimensions, Cosine distance) + sparse vectors (IDF modifier), fused with RRF (Relative Reciprocal Fusion).</p>')
    h.append('        <dl class="kv">')
    for k,v in [("collection","researchmate_chunks"),("dense.size","4096"),("dense.distance","Cosine"),("sparse.modifier","idf"),("fusion","rrf")]:
        h.append('          <dt>' + k + '</dt><dd><code>' + v + '</code></dd>')
    payload = ["user_id (keyword)","project_id (keyword)","document_id (keyword)","chunk_id (keyword)","source_type (keyword)","page_no (integer)","slide_no (integer)","title (text)","url (keyword)","content_hash (keyword)","pipeline_version (keyword)","expires_at (datetime)"]
    h.append('          <dt>Payload schema</dt><dd>' + "<br/>".join(payload) + '</dd>')
    h.append('          <dt>Required filters</dt><dd><code>user_id</code> + <code>project_id</code> + <code>source_type</code> (triple tenant filter)</dd>')
    h.append('        </dl>')
    h.append("        <h3>researchmate_chunks_v2 (rerank)</h3>")
    h.append('        <p>Rerank backfill collection, created programmatically by <code>scripts/provision_qdrant_rerank.py</code>. Uses multivector (late-interaction) embeddings, 96 dimensions, Cosine distance, MAX_SIM comparator. HNSW m=0 (brute-force). Backfill version <code>20260728_answerai_colbert_small_v1</code>.</p>')
    h.append('        <dl class="kv">')
    for k,v in [("collection","researchmate_chunks_v2"),("vector name","multi"),("multivector.size","96"),("multivector.distance","Cosine"),("multivector.comparator","MAX_SIM"),("hnsw.m","0 (brute-force)"),("payload indexes","user_id, project_id, document_id, source_type (all keyword)")]:
        h.append('          <dt>' + k + '</dt><dd><code>' + v + '</code></dd>')
    h.append('          <dt>Verification</dt><dd>Point count check + tenant-filter sample query; SHA-256 digest of chunk IDs stored in researchmate_vector_migrations</dd>')
    h.append('        </dl>')
    h.append("      </section>")
    h.append('      <section id="openapi">')
    h.append('        <p class="eyebrow">OpenAPI specification</p>')
    h.append("        <h2>45 endpoints / 11 tags / 65 schemas</h2>")
    h.append('        <p class="sub">openapi.yaml (168 KB) is deterministically rendered from the FastAPI app by export_openapi.py. 39 paths carry 45 endpoints (method x path combinations), grouped into 11 tags. 65 schemas include 64 component schemas and the HTTPBearer security scheme.</p>')
    h.append("        <h3>Tag distribution</h3>")
    h.append('        <div class="scroll"><table class="dense">')
    h.append('          <thead><tr>')
    for hdr in ["Tag","Endpoints","Paths"]:
        h.append('            <th>' + hdr + '</th>')
    h.append('          </tr></thead><tbody>')
    for tag,count,paths in TAG_DATA:
        paths_html = "<br/>".join('<code>' + p + '</code>' for p in paths)
        h.append('            <tr>')
        h.append('              <td><code>' + tag + '</code></td>')
        h.append('              <td>' + str(count) + '</td>')
        h.append('              <td>' + paths_html + '</td>')
        h.append('            </tr>')
    h.append('            <tr><td><strong>Total</strong></td><td><strong>45</strong></td><td><strong>39 paths / 11 tags</strong></td></tr>')
    h.append('          </tbody></table></div>')
    h.append("        <h3>65 schemas (including HTTPBearer)</h3>")
    h.append('        <p>64 component schemas + 1 HTTPBearer security scheme = 65. Sorted alphabetically:</p>')
    h.append('        <div class="grid">')
    for s in ALL_SCHEMAS:
        h.append('          <article class="fact"><b>' + s + '</b></article>')
    h.append('          <article class="fact"><b>HTTPBearer</b><p>Security scheme (securitySchemes), not a component schema</p></article>')
    h.append('        </div>')
    h.append("      </section>")
    h.append('      <section id="scripts">')
    h.append('        <p class="eyebrow">scripts/ file-by-file analysis</p>')
    h.append("        <h2>8 operational scripts</h2>")
    h.append('        <p class="sub">5 Python scripts + 2 PowerShell scripts + 1 encoding repair script. All scripts use environment-variable gates or approval flags.</p>')
    for i,s in enumerate(SCRIPTS_DATA,1):
        sid = "script-%02d" % i
        h.append('        <details id="' + sid + '"><summary>' + str(i) + '. ' + s[0] + '</summary>')
        h.append('          <dl class="kv">')
        h.append('            <dt>Language</dt><dd><code>' + s[1] + '</code></dd>')
        h.append('            <dt>Lines</dt><dd>' + s[2] + '</dd>')
        h.append('            <dt>Purpose</dt><dd>' + s[3] + '</dd>')
        h.append('            <dt>Details</dt><dd>' + s[4] + '</dd>')
        h.append('          </dl>')
        h.append('        </details>')
    h.append("      </section>")
    h.append('      <section id="proof-chain">')
    h.append('        <p class="eyebrow">Migration execution flow</p>')
    h.append("        <h2>apply_migrations.py proof chain</h2>")
    h.append('        <p class="sub">A 7-step verification chain ensures migrations are applied safely, ordered, and auditable.</p>')
    h.append('        <div class="proof-chain">')
    for i,(title,desc) in enumerate(PROOF_STEPS,1):
        h.append('          <div class="proof-step"><b>' + str(i) + '. ' + title + '</b><small>' + desc + '</small></div>')
    h.append('        </div>')
    h.append("      </section>")
    h.append('      <section id="relationships">')
    h.append('        <p class="eyebrow">Table relationship diagram</p>')
    h.append("        <h2>27 foreign-key edges</h2>")
    h.append('        <p class="sub">cascade means cascading delete; set null means nullify; restrict means blocking delete.</p>')
    h.append('        <div class="relation-ledger">')
    for from_t,to_t,action,label in RELATIONS:
        cls = "cascade" if action == "cascade" else ("set-null" if action == "set null" else "")
        h.append('          <div class="relation-edge ' + cls + '"><code>' + from_t + ' &rarr; ' + to_t + '</code><small>' + action + ' &middot; ' + label + '</small></div>')
    h.append('        </div>')
    h.append("      </section>")
    h.append('      <section id="further">')
    h.append('        <p class="eyebrow">Further reading</p>')
    h.append("        <h2>Related documentation</h2>")
    h.append('        <div class="doc-index">')
    for href,title,desc in LINKS:
        h.append('          <a class="doc-link" href="' + href + '"><b>' + title + '</b><span>' + desc + '</span></a>')
    h.append('        </div>')
    h.append("      </section>")
    h.append("    </div>")
    h.append('    <aside class="toc"><b>Contents</b>')
    for href,label in TOC_ITEMS:
        h.append('      <a href="' + href + '">' + label + '</a>')
    h.append('    </aside></div>')
    h.append("  </main>")
    h.append('  <footer class="shell footer">ResearchMate infrastructure learning guide . written 6 August 2026</footer>')
    h.append('  <script src="../assets/site.js"></script>')
    h.append("</body>")
    h.append("</html>")
    return "\n".join(h) + "\n"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in ("en","zh"):
        html = build(lang)
        suffix = ".zh.html" if lang == "zh" else ".html"
        path = OUT / ("infra" + suffix)
        path.write_text(html, encoding="utf-8", newline="\n")
        print("Wrote " + str(path) + " (" + str(len(html)) + " bytes)")

main()
