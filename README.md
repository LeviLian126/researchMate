# ResearchMate

ResearchMate is a personal AI engineering portfolio: a production-oriented Agentic RAG system for multi-source evidence review. It is designed to demonstrate engineering depth for recruiting and technical interviews, not customer acquisition, subscriptions, billing, or revenue growth.

The central scenario is deliberately complex enough to justify the stack: ingest a collection of PDF, DOCX, PPTX, and web sources; decompose a research question; retrieve and rerank evidence; extract claims and relationships; pause uncertain or unsafe work for human review; generate a page-cited report; incrementally refresh affected sections; and compare pipeline versions under evaluation and reliability experiments.

## Current status

| Area | Repository state | Remaining external proof |
|---|---|---|
| Public demo | A browser-only, deterministic evidence-review walkthrough now covers the workspace, library, Ask, reports, quizzes, evaluation, and reliability surfaces without authentication or cloud-provider calls. | First Cloudflare Workers deployment and browser smoke. |
| Web application | The production-capable Next.js UI and typed client contracts are implemented. Local development uses explicit development identities; non-local API mode uses Supabase Auth REST. | Browser smoke against a deployed API and Supabase session. |
| FastAPI contract | 35 typed REST operations with ownership/role checks, executable catalogs, complete report reads, idempotency boundaries, unified errors, liveness, and dependency readiness. OpenAPI is generated and drift-checked. | Managed-service readiness and preview smoke. |
| Durable state | PostgreSQL repositories, ordered/checksummed migrations, RLS design, transactional outbox, leases, retries, and resumable workflow state are implemented. | Apply migrations to isolated development/preview projects and run integration tests. |
| Retrieval and agents | NVIDIA-compatible chat/embedding adapters, Tavily search, Qdrant hybrid retrieval, reranking, LangGraph checkpoint/interrupt workflow, and grounded synthesis are implemented behind explicit runtime configuration. | Provider credentials, quality evaluation, and failure/recovery evidence. |
| Evaluation and reliability | Budget-bounded evaluation runs, baseline comparison, trace-safe telemetry, fault exercises, and reliability summaries are implemented. | RAGAS/Langfuse/OTLP and worker execution in managed environments. |
| Delivery | CI and a protected manual Cloudflare Workers release for the browser-only demo are configured. The earlier Azure/GHCR runtime-release path is retained as non-executable source history, not a deployment target. | Cloudflare token configuration, first public deployment, and browser smoke. |

The exact implemented, scaffolded, committed, failed, and not-yet-validated states are maintained in the [HTML documentation](docs/index.html). A feature is not presented as production-proven merely because its adapter or contract exists.

## Architecture

- Next.js on Cloudflare Workers via OpenNext for the public demo.
- FastAPI, Celery, and the outbox dispatcher remain repository-implemented but are not deployed to Cloudflare Workers; they require a future container-capable runtime.
- Separate Celery worker and transactional-outbox dispatcher processes with Upstash Redis for bounded asynchronous work.
- Supabase PostgreSQL/Auth as the business source of truth and identity boundary.
- S3-compatible object storage for original files and parsed artifacts; Supabase Storage is the no-card development target and Cloudflare R2 remains an optional legacy-compatible provider.
- Qdrant for filtered dense/sparse retrieval projections.
- LangGraph for checkpointed workflow state and human interrupts.
- NVIDIA's OpenAI-compatible endpoint for chat and embeddings; Tavily for bounded web retrieval.
- OpenTelemetry and Langfuse for privacy-safe operational and LLM observations.

PostgreSQL is authoritative. Object storage and Qdrant are rebuildable projections; Redis never stores irrecoverable business truth.

## Local development

Local infrastructure does not require Docker. The application runs with the existing Node/Python environment and explicit in-memory/fake providers; managed development projects are used only for opt-in integration testing.

```powershell
# Install repository dependencies when they are not already available.
npm ci
uv pip install --python D:\software\env\researchmate\Scripts\python.exe -r requirements-dev.txt

# Use the project environment for repository scripts in this shell.
& D:\software\env\researchmate\Scripts\Activate.ps1

# Terminal 1: deterministic local API; no paid provider calls.
$env:APP_ENV="local"
$env:LLM_PROVIDER="fake"
$env:EMBEDDING_PROVIDER="fake"
$env:WEB_SEARCH_PROVIDER="disabled"
python -m uvicorn researchmate_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000

# Terminal 2
npm run web:dev
```

Open `http://localhost:3000/app`. The development identity selector is available only when both the browser and API are running in local development. Preview and production fail closed and require a valid Supabase session.

Copy `.env.example` to `.env` for local-only credentials. Never commit provider keys; preview and production values belong in their platform secret stores and must use different projects, databases, buckets, and API keys.

## Quality gates

```powershell
npm run check:all
```

The aggregate gate runs Python tests, Ruff, OpenAPI drift, migration-file validation, the production Next.js build, and the production dependency audit. Provider and cloud integration tests remain opt-in so unit tests do not depend on network access or consume paid quotas.

## Release boundary

`.github/workflows/release.yml` is intentionally manual and protected. It builds the Next.js/OpenNext bundle and deploys the explicitly flagged browser-only demo to Cloudflare Workers using only the GitHub `Production` environment's `CLOUDFLARE_API_TOKEN`. It does not apply database migrations, upload files, start an API, start Celery, contact a model provider, or make a paid resource. Cloudflare R2 stays disabled: Supabase Storage remains the selected future storage provider and no credit-card-backed object-storage plan is required for this release.

The repository is connected to the public `main` branch. GitHub Actions CI #18 passed on 18 July 2026. The Vercel Hobby URL is a legacy frontend deployment, not the release target. Production Supabase configuration exists but is deliberately unused by the public demo. Development Supabase, Upstash, and Qdrant resources are likewise unconnected. The old Azure deployment design is retired because no Azure student subscription is available; its scripts and container definitions remain as future-runtime reference code only. No migration, authenticated session, database/broker connection, provider call, worker heartbeat, OCI publication, or full backend release is claimed.

Free tiers are treated as demo infrastructure, not an SLA. If student/free quotas are exhausted, background computation is paused and only the precomputed read-only demonstration should remain available.

## Repository map

```text
apps/api/                 FastAPI contracts and provider adapters
apps/web/                 Next.js portfolio and evidence-review UI
workers/ai-worker/        ingestion, outbox, workflow, evaluation, fault workers
infra/openapi/            generated machine-readable API contract
infra/supabase/migrations ordered PostgreSQL/RLS migrations
infra/qdrant/             vector collection contract
packages/shared/          shared frontend contracts
docs/                     five authoritative English HTML pages
scripts/                  contract, migration, and documentation tooling
tests/                    unit, contract, security, and release gates
```

Start with the [portfolio overview](docs/index.html), then follow its deep links to Product, Architecture, Database, and API sections. Those HTML pages are the authoritative source for feature status and unresolved validation work.
