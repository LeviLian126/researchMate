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
| Delivery | CI, immutable GHCR image builds, protected manual release, migration gate, Azure Container Apps updates, Vercel deployment, and readiness smoke are configured. | Human configuration of GitHub environments, OIDC, cloud resources, secrets, and the first release. |

The exact implemented, scaffolded, committed, failed, and not-yet-validated states are maintained in the [HTML documentation](docs/index.html). A feature is not presented as production-proven merely because its adapter or contract exists.

## Architecture

- Next.js on Vercel for the portfolio and evidence-review UI.
- FastAPI on Azure Container Apps for authenticated contracts and orchestration.
- Separate Celery worker and transactional-outbox dispatcher processes with Upstash Redis for bounded asynchronous work.
- Supabase PostgreSQL/Auth as the business source of truth and identity boundary.
- Cloudflare R2 for original files and parsed artifacts.
- Qdrant for filtered dense/sparse retrieval projections.
- LangGraph for checkpointed workflow state and human interrupts.
- NVIDIA's OpenAI-compatible endpoint for chat and embeddings; Tavily for bounded web retrieval.
- OpenTelemetry and Langfuse for privacy-safe operational and LLM observations.

PostgreSQL is authoritative. R2 and Qdrant are rebuildable projections; Redis never stores irrecoverable business truth.

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

`.github/workflows/release.yml` is intentionally manual and protected. Before the first deployment, a human must configure GitHub Environments, Azure OIDC and separate API/worker/dispatcher Container Apps, GHCR image access, Vercel project credentials, Supabase, Upstash, Qdrant, R2, Tavily, NVIDIA token prices, and observability secrets. The workflow then applies checksummed domain migrations plus SDK-owned LangGraph checkpoint migrations, deploys immutable commit-SHA images and the prebuilt web application, and requires liveness plus full dependency readiness smoke. After the first ready document is ingested, run guarded `scripts/bootstrap_demo_catalog.py` once to provision the accepted pipeline and frozen evaluation dataset shown by the UI.

The repository is connected to the public `main` branch. After CI #4 exposed a case-sensitive documentation-path omission, the repair commit `c65aff3` completed GitHub Actions CI #5 successfully. The Vercel Hobby frontend is live at `https://research-mate-web.vercel.app`; developer HTML documentation remains repository-only and is excluded from the public build. Separate Supabase Free and Upstash Redis Free development resources are healthy in the same region; automatic public-table exposure is disabled and automatic RLS is enabled for the database, while Redis uses TLS and has zero use. A separate Qdrant Cloud Free development cluster is Healthy in its selected region; no collection, application credential, or query has been configured. No application deployment secret has been stored, migration applied, session/API/database/broker connection made, RLS query run, or queue message delivered. GitHub Environments, R2 and the remaining managed providers, OCI publication, API/worker smoke checks, rollback, and the complete runtime release remain unvalidated.

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
