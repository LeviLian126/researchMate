# -*- coding: utf-8 -*-
from pathlib import Path

OUT = Path(r"D:\software\researchMate\docs\learn")
VENV = r"D:\software\env\researchmate"

MIGRATIONS = [
    ("202605260001_initial_schema.sql","202605260001","profiles, projects, documents, document_pages, chunks, conversations, messages, ask_runs, tool_calls, citations, quiz_sets, quiz_questions, jobs, deletion_jobs, api_usage(15 张表)","8 个 enum、12 个索引、owner_user_id() 辅助函数","全部 15 张表启用 RLS。使用 auth.uid() 实现按 owner 限定的 SELECT/INSERT/UPDATE/DELETE。document_pages、tool_calls、citations、quiz_questions 无独立策略(在迁移 002 中补齐)。","单次 additive 迁移创建完整核心数据模型。文档上限 25 MB,chunks 通过 qdrant_point_id 引用 Qdrant。"),
    ("202607150002_evidence_review_schema.sql","202607150002","pipeline_versions, workflow_runs, run_events, research_questions, claims, claim_evidence, claim_relations, reports, report_sections, human_decisions, outbox_events, evaluation_datasets, evaluation_cases, evaluation_runs, evaluation_scores(15 张表)","17 个索引(含 evaluation_cases.labels 的 GIN 索引);claim_evidence、claim_relations 使用复合主键;idempotency_key 唯一约束","全部 15 张新表启用 RLS。补齐迁移 001 的 4 个继承式所有权缺口。pipeline_versions 设置 developer/admin 的 INSERT/UPDATE/DELETE 策略。outbox_events 不设认证用户策略(仅 service-role)。","新增完整的 evidence-review 与 evaluation 子系统。PostgreSQL 保持为唯一真相源;R2、Qdrant、Redis 均为外部投影或协调服务。"),
    ("202607150003_job_delivery_lease.sql","202607150003","无新表(修改 jobs)","为 jobs 增加 attempts、lease_owner、lease_expires_at、started_at、completed_at 列;新增 idx_jobs_dispatch_lease","无 RLS 变更。","支持基于 lease 的安全至少一次 Celery 执行与并发控制。"),
    ("202607150004_evaluation_delivery_lease.sql","202607150004","无新表(修改 evaluation_runs)","为 evaluation_runs 增加 attempts、lease_owner、lease_expires_at 列;新增 idx_evaluation_runs_dispatch_lease","无 RLS 变更。","支持可恢复的 evaluation-run 所有权,实现有界并行用例执行。"),
    ("202607150005_evaluation_budget_and_fault_exercises.sql","202607150005","fault_exercises(1 张新表)","为 evaluation_runs 增加 budget_limit_usd(默认 1.0,fail-closed)、budget_reserved_usd、last_error_code;fault_exercises 含 scenario 枚举、lease 列、request_hash 唯一约束","fault_exercises 启用 RLS:owner SELECT + INSERT(requested_by = auth.uid())。无 UPDATE/DELETE 策略。","引入 fail-closed 成本预算与可审计、非破坏性的可靠性演练。"),
    ("202607160006_runtime_readiness_and_workflow_budget.sql","202607160006","runtime_heartbeats(1 张协调表)","为 workflow_runs 增加 delivery_attempts、lease_owner、lease_expires_at、budget_limit_usd(默认 1.0,上限 25)、budget_reserved_usd、actual_cost_usd 列及预算约束;runtime_heartbeats 含 component 枚举(worker/dispatcher)","runtime_heartbeats 启用 RLS 但不设浏览器策略;REVOKE all from anon, authenticated。更新 pipeline_versions SELECT 策略以允许发现 accepted 版本。","运维就绪监控与 fail-closed 研究预算(含成本上限)。"),
    ("202607280007_unified_chat_and_runtime_rerank.sql","202607280007","runtime_ai_config(1 张协调表)","为 conversations 增加 summary 系列列;为 messages 增加 ask_run_id;为 ask_runs 增加 web_enabled、context_strategy(6 个值)、rerank_provider、rerank_degraded、fallback_reason;向 runtime_ai_config 插入初始记录('rerank','auto')","runtime_ai_config 启用 RLS:仅 admin/developer 可 SELECT + UPDATE。expand 阶段将 source_mode 默认值设为 'local_only'。","从 source_mode 迁移到统一的 context_strategy + rerank provider。两阶段 expand-then-contract 迁移。"),
    ("202607280008_remove_source_modes.sql","202607280008","无新表(contract 阶段删除列)","从 ask_runs 删除 source_mode 和 resolved_mode;从 quiz_sets 删除 source_mode","无 RLS 变更。","Contract 阶段:统一 runtime 已上线,之后才删除这些退役列。"),
    ("202607290009_personal_chat_project_memory_and_quiz.sql","202607290009","无新表(修改 projects、documents、enum)","为 projects 增加 kind(personal/workspace)、memory 系列列及每用户一个 personal 项目的唯一偏索引;为 documents 增加 conversation_id;向 quiz_question_type 枚举增加 fill_blank 和 subjective","无 RLS 变更。","个人聊天工作区、项目级记忆摘要,以及扩展的 quiz 题型。"),
    ("202608010010_api_idempotency.sql","202608010010","api_idempotency(1 张协调表)","复合主键(user_id, operation, idempotency_key);request_hash 为 SHA-256(64 位十六进制);state(pending/succeeded);CHECK 约束确保 pending+null response 或 succeeded","api_idempotency 启用 RLS:owner ALL 策略(user_id = auth.uid())。","为高成本的 Ask 和 Quiz 操作持久化防重放请求标识。"),
]

SCRIPTS_DATA = [
    ("apply_migrations.py","Python","96","校验并显式应用有序 additive PostgreSQL 迁移。强制唯一版本前缀、拒绝空文件和 DROP DATABASE、获取 pg_advisory_xact_lock、用 SHA-256 校验和追踪已应用迁移,校验和不匹配时报错。需要 ALLOW_SCHEMA_APPLY=1。","两种模式:--check-files(仅校验)和 --apply(完整执行)。Advisory lock key 726334129。单事务执行。"),
    ("bootstrap_demo_catalog.py","Python","150","从已就绪的项目 chunks 引导创建 accepted demo pipeline version 和 frozen evaluation dataset。为明确批准的 developer/admin 用户和项目创建幂等目录记录。需要 ALLOW_DEMO_BOOTSTRAP=1。","读取最多 --case-limit(默认 10,上限 50)个已就绪 chunks,生成具有确定性 case_key 的 evaluation cases,冻结数据集,以 JSON 返回 pipeline_version_id + dataset_id。"),
    ("check_contracts.ps1","PowerShell","14","使用固定本地 Python 环境(" + VENV + ")运行 pytest,校验 test_project_scaffold、test_api_workflow 和 test_frontend_contracts 核心仓库契约。","venv 不存在时自动创建;可选 -InstallDependencies 参数运行 uv sync --frozen --all-packages --group dev。"),
    ("dev_api.ps1","PowerShell","13","使用固定 venv(" + VENV + ")在 127.0.0.1:8000 启动本地可重载 uvicorn API 服务器。","venv 不存在时自动创建;可选 -InstallDependencies 运行 uv sync。执行:python -m uvicorn researchmate_api.main:app --reload --host 127.0.0.1 --port 8000"),
    ("export_openapi.py","Python","36","将 FastAPI OpenAPI schema 渲染为确定性 YAML,写入或校验 infra/openapi/openapi.yaml 跟踪文件。使用 Settings(app_env='test', llm_provider='fake') 生成稳定 schema。","默认写入文件;--check 在跟踪文件过期时报错。import 路径插入 apps/api/src 用于模块解析。"),
    ("provision_qdrant_rerank.py","Python","152","引导并验证经明确批准的 Qdrant rerank 回填。创建 researchmate_chunks_v2 集合(多向量/late-interaction 嵌入),创建 payload 索引,以 32 条为一批回填向量,并记录验证元数据。需要 ALLOW_QDRANT_RERANK_BACKFILL=1 和 QDRANT_RERANK_MODEL_IS_FREE=true。","回填版本 20260728_answerai_colbert_small_v1。创建 researchmate_vector_migrations 追踪表,验证点数和租户过滤样本查询,存储 chunk ID 的 SHA-256 摘要。"),
    ("repair_docs_html_encoding.py","Python","83","修复已知的 HTML 文档编码损坏。恢复被乱码替换的导航标签,修复 summary 标签,恢复 7 个文档页的 lead 段落,将每页内联样式替换为共享 site.css 链接。","两个阶段:repair_common_wrappers(正则修复)和 unify_shared_styles(共享样式表的相对路径计算)。"),
    ("setup_langgraph_checkpoint.py","Python","26","在经批准的 schema 阶段创建 LangGraph 拥有的 checkpoint 表。将 DATABASE_URL 从 postgresql+psycopg:// 转换为 postgresql:// 并调用 PostgresSaver.setup()。需要 ALLOW_SCHEMA_APPLY=1。","LangGraph 拥有并版本化其 checkpoint DDL。仅在受保护的发布迁移阶段运行,切勿在任务交付期间并发运行。"),
]

TABLES_DATA = [
    ("profiles","001","identity","id (PK), email, provider, role (user/developer/admin)","auth.uid() = id (SELECT)"),
    ("projects","001","identity","id (PK), user_id, name, status, kind, memory_summary_text","auth.uid() = user_id (ALL)"),
    ("documents","001","documents","id (PK), user_id, project_id, filename, file_type, status, r2_object_key","auth.uid() = user_id (ALL)"),
    ("document_pages","001","documents","id (PK), document_id, page_no, slide_no, text, metadata","通过 documents 继承(SELECT,002 补齐)"),
    ("chunks","001","documents","id (PK), user_id, project_id, document_id, source_type, text, qdrant_point_id","auth.uid() = user_id (ALL)"),
    ("conversations","001","chat","id (PK), user_id, project_id, title, summary_text, summary_token_count","auth.uid() = user_id (ALL)"),
    ("messages","001","chat","id (PK), user_id, project_id, conversation_id, role, content, ask_run_id","auth.uid() = user_id (ALL)"),
    ("ask_runs","001","chat","id (PK), user_id, project_id, conversation_id, message, task_type, context_strategy, rerank_provider, web_enabled","auth.uid() = user_id (ALL)"),
    ("tool_calls","001","chat","id (PK), ask_run_id, tool_name, input, output_summary, status, latency_ms","通过 ask_runs 继承(SELECT,002 补齐)"),
    ("citations","001","chat","id (PK), ask_run_id, chunk_id, document_id, source_type, quote, claim_id","通过 ask_runs 继承(SELECT,002 补齐)"),
    ("quiz_sets","001","quiz","id (PK), user_id, project_id, ask_run_id, title, sources_summary","auth.uid() = user_id (ALL)"),
    ("quiz_questions","001","quiz","id (PK), quiz_set_id, type, question, options, answer, explanation, difficulty","通过 quiz_sets 继承(SELECT,002 补齐)"),
    ("jobs","001","ops","id (PK), user_id, project_id, document_id, type, status, progress, attempts, lease_owner","auth.uid() = user_id (ALL)"),
    ("deletion_jobs","001","ops","id (PK), user_id, project_id, document_id, status, target_types","auth.uid() = user_id (ALL)"),
    ("api_usage","001","ops","id (PK), user_id, usage_date, kind, count, unique(user_id, usage_date, kind)","auth.uid() = user_id (ALL)"),
    ("pipeline_versions","002","evidence","id (PK), name, version, status, configuration, prompt_hash, code_sha, created_by","Accepted=公开;draft/candidate=创建者+admin;dev/admin I/U/D"),
    ("workflow_runs","002","evidence","id (PK), user_id, project_id, pipeline_version_id, kind, status, idempotency_key, budget_limit_usd, lease_owner","auth.uid() = user_id (SELECT + INSERT)"),
    ("run_events","002","evidence","id (bigint PK), run_id, sequence, node_key, event_type, attempt, status, cost_usd","通过 workflow_runs 继承(SELECT)"),
    ("research_questions","002","evidence","id (PK), user_id, project_id, parent_id, source_run_id, question, status, priority, plan_order","auth.uid() = user_id (SELECT)"),
    ("claims","002","evidence","id (PK), user_id, project_id, question_id, source_run_id, text, normalized_key, stance, confidence, review_status","auth.uid() = user_id (SELECT)"),
    ("claim_evidence","002","evidence","claim_id + citation_id + relation (PK), extraction_score, extractor_version","通过 claims + citations 双重继承(SELECT)"),
    ("claim_relations","002","evidence","source_claim_id + target_claim_id + relation (PK), confidence, rationale_summary","通过 source + target claims 双重继承(SELECT)"),
    ("reports","002","evidence","id (PK), user_id, project_id, source_run_id, title, status, revision, validation_status","auth.uid() = user_id (SELECT)"),
    ("report_sections","002","evidence","id (PK), report_id, parent_section_id, section_key, position, heading, body_markdown, evidence_snapshot","通过 reports 继承(SELECT)"),
    ("human_decisions","002","evidence","id (PK), run_id, event_id, user_id, interrupt_key, decision, proposed_payload, final_payload","通过 workflow_runs 继承(SELECT);INSERT 需 owner 或 dev/admin"),
    ("outbox_events","002","evidence","id (PK), aggregate_type, aggregate_id, event_type, payload, idempotency_key, status, attempts","无认证用户策略(仅 service-role)"),
    ("evaluation_datasets","002","evaluation","id (PK), user_id, project_id, name, version, status, description","Owner SELECT + I/U/D(仅 draft)"),
    ("evaluation_cases","002","evaluation","id (PK), dataset_id, case_key, input, expected_output, expected_evidence, labels","通过 evaluation_datasets 继承(仅 draft 可写)"),
    ("evaluation_runs","002","evaluation","id (PK), user_id, project_id, dataset_id, pipeline_version_id, status, idempotency_key, budget_limit_usd, lease_owner","Owner SELECT + INSERT(需 frozen 数据集)"),
    ("evaluation_scores","002","evaluation","id (PK), evaluation_run_id, case_id, metric_name, metric_version, value, passed, judge_model","通过 evaluation_runs 继承(SELECT)"),
    ("fault_exercises","005","evaluation","id (PK), requested_by, target_run_id, scenario, duration_seconds, status, request_hash, idempotency_key, lease_owner","Owner SELECT + INSERT(requested_by = auth.uid())"),
    ("runtime_heartbeats","006","coordination","component (PK: worker/dispatcher), instance_id, status, safe_metadata, updated_at","启用 RLS,REVOKE from anon/authenticated(仅后端)"),
    ("runtime_ai_config","007","coordination","config_key (PK), provider, version, updated_at, updated_by","仅 admin/developer SELECT + UPDATE"),
    ("api_idempotency","010","coordination","user_id + operation + idempotency_key (PK), request_hash, state, response","Owner ALL(user_id = auth.uid())"),
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
    ("Enforce unique prefixes","migration_files() 排序所有 .sql 文件,校验版本前缀(第一个下划线前的 YYYYMMDDNNN 部分)在整个集合中唯一。"),
    ("Reject destructive content","validate_files() 对每个文件去空白,拒绝空迁移,阻止包含 DROP DATABASE 的文件(不区分大小写)。"),
    ("Approval gate","apply 路径需要环境变量 ALLOW_SCHEMA_APPLY=1。未设置时脚本立即退出,不触碰数据库。"),
    ("Advisory transaction lock","pg_advisory_xact_lock(726334129) 在当前事务内串行化迁移执行,防止并发运行。"),
    ("Tracking table bootstrap","如不存在则创建 researchmate_schema_migrations(version PK, checksum_sha256, applied_at),随后读取所有已应用记录。"),
    ("Checksum verification","对追踪表中已有的每个文件重新计算 SHA-256 并比较。任何漂移触发 RuntimeError,中止执行。"),
    ("Apply and record","未应用的迁移按序在事务内执行,然后连同 SHA-256 摘要插入追踪表。事务仅提交一次。"),
]

RELATIONS = [
    ("profiles","projects","cascade","user_id"),
    ("projects","documents","cascade","project_id"),
    ("documents","document_pages","cascade","document_id"),
    ("projects","chunks","cascade","project_id"),
    ("documents","chunks","cascade","document_id"),
    ("projects","conversations","cascade","project_id"),
    ("conversations","messages","cascade","conversation_id"),
    ("conversations","documents","cascade","conversation_id(009 新增)"),
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
NAV_ITEMS_ZH = [("../index.html","概览"),("../product/index.html","产品与路线图"),("../architecture/index.html","架构与技术栈"),("../contracts/data/index.html","数据库"),("../contracts/api/index.html","API"),("index.html","学习")]
MODULES_ZH = [("frontend","Frontend"),("backend","Backend"),("worker","Worker"),("infra","基础设施"),("cicd","CI/CD"),("contracts-tests","Contracts & Tests")]
TOC_ITEMS_ZH = [("#stack","技术栈基础"),("#tree","目录树"),("#migrations","SQL 迁移"),("#tables","表清单"),("#qdrant","Qdrant"),("#openapi","OpenAPI"),("#scripts","脚本"),("#proof-chain","迁移流程"),("#relationships","表关系"),("#further","延伸阅读")]
LINKS_ZH = [("../contracts/data/index.html","数据库契约","完整的表定义、RLS 策略与数据生命周期。"),("../contracts/api/index.html","API 契约","45 个端点的请求/响应规范与认证流程。"),("../architecture/index.html","架构与技术栈","系统分层、数据流与安全边界。"),("backend.html","后端学习","FastAPI 应用的逐文件源码解析。"),("worker.html","Worker 学习","Celery worker 的任务交付与 lease 机制。"),("cicd.html","CI/CD","持续集成与部署流程。")]

def build_zh():
    h = []
    h.append('<!DOCTYPE html>')
    h.append('<html lang="zh-CN">')
    h.append('<head>')
    h.append('  <meta charset="utf-8"/>')
    h.append('  <title>基础设施 . infra &amp; scripts</title>')
    h.append('  <meta name="viewport" content="width=device-width, initial-scale=1"/>')
    h.append('  <link href="../assets/site.css" rel="stylesheet"/>')
    h.append('</head>')
    h.append('<body>')
    h.append('  <header class="mast"><div class="shell mast-row"><a class="brand" href="../index.html">ResearchMate documentation</a><div class="mast-right"><span class="stamp">基础设施 . 2026 年 8 月 6 日</span><a class="lang-toggle" href="infra.html" hreflang="en" lang="en">English</a></div></div></header>')
    h.append('  <nav aria-label="Documentation" class="global"><div class="shell">')
    for href,label in NAV_ITEMS_ZH:
        ac = ' aria-current="page"' if label == "学习" else ""
        h.append('    <a' + ac + ' href="' + href + '">' + label + '</a>')
    h.append('  </div></nav>')
    h.append('  <nav aria-label="Learning modules" class="global module-nav"><div class="shell">')
    for key,label in MODULES_ZH:
        ac = ' aria-current="page"' if key == "infra" else ""
        h.append('    <a' + ac + ' href="' + key + '.html">' + label + '</a>')
    h.append('  </div></nav>')
    h.append('  <main class="shell">')
    h.append('    <div class="hero">')
    h.append('      <p class="eyebrow">Supabase / PostgreSQL RLS / Qdrant / 10 个迁移 / 45 个端点</p>')
    h.append('      <h1>基础设施 . infra &amp; scripts</h1>')
    h.append('      <p class="lede">ResearchMate 基础设施层定义了全部持久化与协调基础设施:Supabase/PostgreSQL 作为唯一真相源,Qdrant 提供向量检索,OpenAPI 规范锁定 45 个端点的 API 契约。本页逐文件解析 infra/ 目录下的 10 个 SQL 迁移、2 个 Qdrant 集合配置、1 个 OpenAPI 规范,以及 scripts/ 目录下的 8 个运维脚本。</p>')
    h.append('      <div class="meta">')
    for text in ["34 张表(31 业务 + 3 协调)","10 个 SQL 迁移","2 个 Qdrant 集合","45 个端点 / 11 个 tag","65 个 schema","8 个脚本"]:
        h.append('        <span class="status local">' + text + '</span>')
    h.append('      </div>')
    h.append('    </div>')
    h.append('    <div class="layout"><div class="content">')
    h.append('      <section id="stack">')
    h.append('        <p class="eyebrow">技术栈基础</p>')
    h.append('        <h2>5 个基础设施组件</h2>')
    h.append('        <p class="sub">每张卡片说明该组件的通用职责,以及 ResearchMate 中的具体用法。</p>')
    h.append('        <div class="grid">')
    facts = [
        ("Supabase","PostgreSQL 托管平台,提供数据库、认证(auth.uid())、存储和 Edge Functions。ResearchMate 使用其 PostgreSQL 实例作为唯一真相源,所有业务表和协调表均在此创建。RLS 策略直接在数据库层强制多租户隔离。"),
        ("PostgreSQL RLS","Row Level Security 在数据库层强制每行数据的访问控制。全部 31 张业务表均启用 RLS,通过 auth.uid() 实现按用户隔离。pipeline_versions 支持 developer/admin 角色策略,outbox_events 不设认证用户策略(仅 service-role)。"),
        ("Database migrations","10 个 additive SQL 迁移,按 YYYYMMDDNNN 版本前缀排序。apply_migrations.py 在 advisory lock 下执行,用 SHA-256 校验和追踪已应用迁移,拒绝 DROP DATABASE 和空文件。"),
        ("Qdrant collections","两个向量集合:researchmate_chunks(v1,dense 4096 维 + sparse,RRF 融合)和 researchmate_chunks_v2(multivector 96 维,MAX_SIM,late-interaction rerank)。两者均强制 user_id + project_id + source_type 三重过滤。"),
        ("OpenAPI spec","45 个端点分布在 11 个 tag 下,65 个 schema(含 HTTPBearer 安全方案)。openapi.yaml 由 export_openapi.py 从 FastAPI 应用确定性渲染,支持 --check 模式校验跟踪文件是否过期。"),
    ]
    for title,body in facts:
        h.append('          <article class="fact"><b>' + title + '</b><p>' + body + '</p></article>')
    h.append('        </div>')
    h.append('      </section>')
    h.append('      <section id="tree">')
    h.append('        <p class="eyebrow">完整目录树</p>')
    h.append('        <h2>infra/ 与 scripts/ 文件结构</h2>')
    h.append('        <p class="sub">infra/ 包含 3 个子目录(openapi、qdrant、supabase),scripts/ 包含 8 个脚本文件。</p>')
    tree = "infra/\n  openapi/\n    openapi.yaml              168 KB  45 endpoints / 11 tags / 65 schemas\n  qdrant/\n    researchmate_chunks.json  676 B   v1 collection config (dense + sparse + RRF)\n  supabase/\n    migrations/\n      202605260001_initial_schema.sql                   11.9 KB\n      202607150002_evidence_review_schema.sql           22.2 KB\n      202607150003_job_delivery_lease.sql                499 B\n      202607150004_evaluation_delivery_lease.sql          422 B\n      202607150005_evaluation_budget_and_fault_exercises.sql  2.7 KB\n      202607160006_runtime_readiness_and_workflow_budget.sql  2.4 KB\n      202607280007_unified_chat_and_runtime_rerank.sql   3.3 KB\n      202607280008_remove_source_modes.sql                253 B\n      202607290009_personal_chat_project_memory_and_quiz.sql  1.1 KB\n      202608010010_api_idempotency.sql                   1.1 KB\n\nscripts/\n  apply_migrations.py            3.6 KB  Validate &amp; apply ordered migrations\n  bootstrap_demo_catalog.py      5.8 KB  Bootstrap demo pipeline + eval dataset\n  check_contracts.ps1              524 B  Run pytest contract tests\n  dev_api.ps1                      491 B  Start uvicorn dev server\n  export_openapi.py              1.2 KB  Render/verify OpenAPI artifact\n  provision_qdrant_rerank.py     6.3 KB  Provision Qdrant v2 backfill\n  repair_docs_html_encoding.py   3.3 KB  Repair corrupted HTML docs\n  setup_langgraph_checkpoint.py    979 B  Create LangGraph checkpoint tables"
    h.append('        <pre class="command-block"><code>' + tree + '</code></pre>')
    h.append('      </section>')
    h.append('      <section id="migrations">')
    h.append('        <p class="eyebrow">SQL 迁移逐文件详解</p>')
    h.append('        <h2>10 个迁移按顺序解析</h2>')
    h.append('        <p class="sub">每个迁移均为 additive(仅添加,不破坏已有数据),按版本号前缀 YYYYMMDDNNN 排序执行。</p>')
    for i,m in enumerate(MIGRATIONS,1):
        mid = "migration-%02d" % i
        h.append('        <details id="' + mid + '"><summary>' + str(i) + '. ' + m[0] + '</summary>')
        h.append('          <dl class="kv">')
        h.append('            <dt>Version</dt><dd><code>' + m[1] + '</code></dd>')
        h.append('            <dt>表</dt><dd>' + m[2] + '</dd>')
        h.append('            <dt>字段与索引</dt><dd>' + m[3] + '</dd>')
        h.append('            <dt>RLS</dt><dd>' + m[4] + '</dd>')
        h.append('            <dt>增量说明</dt><dd>' + m[5] + '</dd>')
        h.append('          </dl>')
        h.append('        </details>')
    h.append('      </section>')
    h.append('      <section id="tables">')
    h.append('        <p class="eyebrow">数据库表清单</p>')
    h.append('        <h2>34 张表(31 业务 + 3 协调)</h2>')
    h.append('        <p class="sub">31 张业务表支撑用户数据、文档、聊天、证据审查与评估;3 张协调表(runtime_heartbeats、runtime_ai_config、api_idempotency)服务于后端运维。</p>')
    h.append('        <div class="scroll"><table class="dense">')
    h.append('          <thead><tr>')
    for hdr in ["#","表名","来源迁移","分组","关键列","RLS 策略"]:
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
    h.append('      </section>')
    h.append('      <section id="qdrant">')
    h.append('        <p class="eyebrow">Qdrant 配置详解</p>')
    h.append('        <h2>两个向量集合</h2>')
    h.append('        <p class="sub">researchmate_chunks 是主检索集合(dense + sparse + RRF 融合);researchmate_chunks_v2 是 rerank 回填集合(multivector late-interaction)。两者均强制 tenant 过滤。</p>')
    h.append('        <h3>researchmate_chunks (v1)</h3>')
    h.append('        <p>主检索集合,定义在 <code>infra/qdrant/researchmate_chunks.json</code>。支持 hybrid retrieval:dense 向量(4096 维,Cosine 距离)+ sparse 向量(IDF modifier),使用 RRF(Relative Reciprocal Fusion)融合排序。</p>')
    h.append('        <dl class="kv">')
    for k,v in [("collection","researchmate_chunks"),("dense.size","4096"),("dense.distance","Cosine"),("sparse.modifier","idf"),("fusion","rrf")]:
        h.append('          <dt>' + k + '</dt><dd><code>' + v + '</code></dd>')
    payload = ["user_id (keyword)","project_id (keyword)","document_id (keyword)","chunk_id (keyword)","source_type (keyword)","page_no (integer)","slide_no (integer)","title (text)","url (keyword)","content_hash (keyword)","pipeline_version (keyword)","expires_at (datetime)"]
    h.append('          <dt>Payload schema</dt><dd>' + "<br/>".join(payload) + '</dd>')
    h.append('          <dt>Required filters</dt><dd><code>user_id</code> + <code>project_id</code> + <code>source_type</code>(三重 tenant 过滤)</dd>')
    h.append('        </dl>')
    h.append('        <h3>researchmate_chunks_v2 (rerank)</h3>')
    h.append('        <p>Rerank 回填集合,由 <code>scripts/provision_qdrant_rerank.py</code> 程序化创建。使用 multivector(late-interaction)嵌入,96 维,Cosine 距离,MAX_SIM 比较器。HNSW m=0(暴力搜索,适合小集合)。回填版本 <code>20260728_answerai_colbert_small_v1</code>。</p>')
    h.append('        <dl class="kv">')
    for k,v in [("collection","researchmate_chunks_v2"),("vector name","multi"),("multivector.size","96"),("multivector.distance","Cosine"),("multivector.comparator","MAX_SIM"),("hnsw.m","0 (brute-force)"),("payload indexes","user_id, project_id, document_id, source_type (all keyword)")]:
        h.append('          <dt>' + k + '</dt><dd><code>' + v + '</code></dd>')
    h.append('          <dt>验证</dt><dd>点数校验 + 租户过滤样本查询校验;chunk ID 的 SHA-256 摘要存入 researchmate_vector_migrations</dd>')
    h.append('        </dl>')
    h.append('      </section>')
    h.append('      <section id="openapi">')
    h.append('        <p class="eyebrow">OpenAPI 规范详解</p>')
    h.append('        <h2>45 个端点 / 11 个 tag / 65 个 schema</h2>')
    h.append('        <p class="sub">openapi.yaml(168 KB)由 export_openapi.py 从 FastAPI 应用确定性渲染。39 个 path 上承载 45 个端点(method x path 组合),按 11 个 tag 分组。65 个 schema 含 64 个 component schema 和 HTTPBearer 安全方案。</p>')
    h.append('        <h3>Tag 分布</h3>')
    h.append('        <div class="scroll"><table class="dense">')
    h.append('          <thead><tr>')
    for hdr in ["Tag","端点数","路径列表"]:
        h.append('            <th>' + hdr + '</th>')
    h.append('          </tr></thead><tbody>')
    for tag,count,paths in TAG_DATA:
        paths_html = "<br/>".join('<code>' + p + '</code>' for p in paths)
        h.append('            <tr>')
        h.append('              <td><code>' + tag + '</code></td>')
        h.append('              <td>' + str(count) + '</td>')
        h.append('              <td>' + paths_html + '</td>')
        h.append('            </tr>')
    h.append('            <tr><td><strong>合计</strong></td><td><strong>45</strong></td><td><strong>39 个 path / 11 个 tag</strong></td></tr>')
    h.append('          </tbody></table></div>')
    h.append('        <h3>65 个 schema(含 HTTPBearer)</h3>')
    h.append('        <p>64 个 component schema + 1 个 HTTPBearer 安全方案 = 65。按字母排序:</p>')
    h.append('        <div class="grid">')
    for s in ALL_SCHEMAS:
        h.append('          <article class="fact"><b>' + s + '</b></article>')
    h.append('          <article class="fact"><b>HTTPBearer</b><p>安全方案(securitySchemes),非 component schema</p></article>')
    h.append('        </div>')
    h.append('      </section>')
    h.append('      <section id="scripts">')
    h.append('        <p class="eyebrow">scripts/ 逐文件详解</p>')
    h.append('        <h2>8 个运维脚本</h2>')
    h.append('        <p class="sub">5 个 Python 脚本 + 2 个 PowerShell 脚本 + 1 个编码修复脚本。所有脚本均使用环境变量门控或审批标志。</p>')
    for i,s in enumerate(SCRIPTS_DATA,1):
        sid = "script-%02d" % i
        h.append('        <details id="' + sid + '"><summary>' + str(i) + '. ' + s[0] + '</summary>')
        h.append('          <dl class="kv">')
        h.append('            <dt>Language</dt><dd><code>' + s[1] + '</code></dd>')
        h.append('            <dt>行数</dt><dd>' + s[2] + '</dd>')
        h.append('            <dt>职责</dt><dd>' + s[3] + '</dd>')
        h.append('            <dt>细节</dt><dd>' + s[4] + '</dd>')
        h.append('          </dl>')
        h.append('        </details>')
    h.append('      </section>')
    h.append('      <section id="proof-chain">')
    h.append('        <p class="eyebrow">迁移执行流程</p>')
    h.append('        <h2>apply_migrations.py proof chain</h2>')
    h.append('        <p class="sub">7 步验证链确保迁移安全、有序、可审计地应用。</p>')
    h.append('        <div class="proof-chain">')
    for i,(title,desc) in enumerate(PROOF_STEPS,1):
        h.append('          <div class="proof-step"><b>' + str(i) + '. ' + title + '</b><small>' + desc + '</small></div>')
    h.append('        </div>')
    h.append('      </section>')
    h.append('      <section id="relationships">')
    h.append('        <p class="eyebrow">表关系图</p>')
    h.append('        <h2>27 条外键关系</h2>')
    h.append('        <p class="sub">cascade 表示级联删除,set null 表示置空,restrict 表示禁止删除。</p>')
    h.append('        <div class="relation-ledger">')
    for from_t,to_t,action,label in RELATIONS:
        cls = "cascade" if action == "cascade" else ("set-null" if action == "set null" else "")
        h.append('          <div class="relation-edge ' + cls + '"><code>' + from_t + ' &rarr; ' + to_t + '</code><small>' + action + ' &middot; ' + label + '</small></div>')
    h.append('        </div>')
    h.append('      </section>')
    h.append('      <section id="further">')
    h.append('        <p class="eyebrow">延伸阅读</p>')
    h.append('        <h2>相关文档</h2>')
    h.append('        <div class="doc-index">')
    for href,title,desc in LINKS_ZH:
        h.append('          <a class="doc-link" href="' + href + '"><b>' + title + '</b><span>' + desc + '</span></a>')
    h.append('        </div>')
    h.append('      </section>')
    h.append('    </div>')
    h.append('    <aside class="toc"><b>目录</b>')
    for href,label in TOC_ITEMS_ZH:
        h.append('      <a href="' + href + '">' + label + '</a>')
    h.append('    </aside></div>')
    h.append('  </main>')
    h.append('  <footer class="shell footer">ResearchMate 基础设施学习指南 . 2026 年 8 月 6 日</footer>')
    h.append('  <script src="../assets/site.js"></script>')
    h.append('</body>')
    h.append('</html>')
    return "\n".join(h) + "\n"

OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "infra.zh.html"
html = build_zh()
path.write_text(html, encoding="utf-8", newline="\n")
print("Wrote " + str(path) + " (" + str(len(html)) + " bytes)")
