# ResearchMate

ResearchMate is a personal AI engineering portfolio: a production-oriented Agentic RAG system for multi-source evidence review. It is designed to demonstrate engineering depth for recruiting and technical interviews, not customer acquisition, subscriptions, billing, or revenue growth.

The central scenario is deliberately complex enough to justify the stack: ingest a collection of PDF, DOCX, PPTX, and web sources; decompose a research question; retrieve and rerank evidence; extract claims and relationships; pause uncertain or unsafe work for human review; generate a page-cited report; incrementally refresh affected sections; and compare pipeline versions under evaluation and reliability experiments.

## Current status

| Area | Repository state | Remaining external proof |
|---|---|---|
| Web application | Evidence workspace, ingestion, grounded Ask, human decisions, reports, Evaluation Lab, and Reliability Lab are implemented. Local development uses explicit development identities; non-local builds use Supabase Auth REST. | Browser smoke against deployed API and Supabase session. |
| FastAPI contract | 35 typed REST operations with ownership/role checks, executable catalogs, complete report reads, idempotency boundaries, unified errors, liveness, and dependency readiness. OpenAPI is generated and drift-checked. | Managed-service readiness and preview smoke. |
| Durable state | PostgreSQL repositories, ordered/checksummed migrations, RLS design, transactional outbox, leases, retries, and resumable workflow state are implemented. | Apply migrations to isolated development/preview projects and run integration tests. |
| Retrieval and agents | NVIDIA-compatible chat/embedding adapters, Tavily search, Qdrant hybrid retrieval, reranking, LangGraph checkpoint/interrupt workflow, and grounded synthesis are implemented behind explicit runtime configuration. | Provider credentials, quality evaluation, and failure/recovery evidence. |
| Evaluation and reliability | Budget-bounded evaluation runs, baseline comparison, trace-safe telemetry, fault exercises, and reliability summaries are implemented. | RAGAS/Langfuse/OTLP and worker execution in managed environments. |
| Delivery | CI, immutable GHCR image builds, protected manual release, migration gate, Azure Container Apps updates, Vercel deployment, and readiness smoke are configured. Production Supabase database, private S3-compatible storage, and GitHub release settings are provisioned. | Azure student subscription/OIDC, production Redis/Qdrant/providers, migration, and the first release. |

The exact implemented, scaffolded, committed, failed, and not-yet-validated states are maintained in the [HTML documentation](docs/index.html). A feature is not presented as production-proven merely because its adapter or contract exists.

## Architecture

- Next.js on Vercel for the portfolio and evidence-review UI.
- FastAPI on Azure Container Apps for authenticated contracts and orchestration.
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

`.github/workflows/release.yml` is intentionally manual and protected. Before the first deployment, a human must configure GitHub Environments, Azure OIDC, public GHCR image access, Vercel project credentials, Supabase Postgres/Auth plus its S3-compatible Storage endpoint, Upstash, Qdrant, Tavily, NVIDIA token prices, and observability secrets. Cloudflare R2 remains optional and is not activated because its subscription can bill overages. The release first performs a no-mutation configuration preflight, then `scripts/provision_azure_container_apps.sh` idempotently creates or reconciles the Azure resource group, no-log Container Apps environment, and separate API/worker/dispatcher apps with Azure `secretref` values. It applies checksummed domain migrations plus SDK-owned LangGraph checkpoint migrations, deploys immutable commit-SHA images and the prebuilt web application, captures the Vercel deployment URL from that same command, and requires liveness plus full dependency readiness smoke. The reconciler uses one small replica for each background role in the first student-credit deployment; queue autoscaling is not claimed. After the first ready document is ingested, run guarded `scripts/bootstrap_demo_catalog.py` once to provision the accepted pipeline and frozen evaluation dataset shown by the UI.

The repository is connected to the public `main` branch. GitHub Actions CI #18 passed on 18 July 2026. The Vercel Hobby frontend is live at `https://research-mate-web.vercel.app`; developer HTML documentation remains repository-only and is excluded from the public build. GitHub `preview` and `Production` environments hold non-sensitive Azure naming variables (`AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `AZURE_CONTAINERAPPS_ENVIRONMENT`, `AZURE_API_APP`, `AZURE_WORKER_APP`, and `AZURE_DISPATCHER_APP`); `Production` additionally has the public CORS origin, is limited to `main`, and holds its Supabase database, storage, and public-client configuration in GitHub Environment secrets/variables. An isolated production Supabase Free project is Healthy in Canada Central with automatic public-table exposure disabled, automatic RLS enabled, and a private `researchmate-production` bucket enforcing 25 MB PDF/DOCX/PPTX limits over S3 compatibility. Its runtime-only S3 credential is in GitHub Production secrets; no application request has used it. Separate development Supabase and Upstash Redis resources are healthy; the Qdrant Cloud Free development cluster is Healthy but the account's production-cluster flow required payment information for a paid plan, so production Qdrant remains deliberately unconfigured. A Cloudflare account exists, but R2 is intentionally not activated because its subscription can bill overages. Azure has no student subscription. No migration, session/API/database/broker connection, RLS query, queue message, OCI publication, API/worker smoke check, rollback, or complete runtime release has run.

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
