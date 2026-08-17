# ResearchMate

> A citation-first research workspace for multi-document evidence review, hybrid retrieval, and resumable Agent workflows.  

[中文](./README.zh-CN.md) · [Documentation](./docs/index.html) · [GitHub](https://github.com/LeviLian126/researchMate)

### What is ResearchMate?

ResearchMate turns a bounded research question and a set of source documents into an auditable, citation-backed result. It is designed as an engineering portfolio project and an experimental research workspace—not as a commercial SaaS product.

The system combines:

- a ChatGPT-style workspace for projects, conversations, sources, and research runs;
- Wiki-assisted local context plus dense/sparse hybrid retrieval;
- evidence extraction, claim reconciliation, citation-aware report synthesis, and incremental refresh;
- LangGraph orchestration with PostgreSQL checkpoints and human approval at risk-sensitive stages;
- versioned RAG evaluation, Bad Case regression, and operational traceability.

### Why it exists

Long-running research jobs fail in ways that a single synchronous LLM call cannot safely handle: provider timeouts, partial evidence, contradictory claims, process restarts, and changing source documents. ResearchMate treats those states as explicit domain state. Evidence, decisions, reports, and recovery checkpoints are persisted so that a run can be reviewed, resumed, or rejected instead of silently producing an answer.

### Core workflow

```text
Question + source scope
        │
        ▼
  Plan bounded sub-questions
        │
        ├── Retrieve local/Web evidence in parallel
        ├── Extract claims and exact citations
        ├── Reconcile support / contradiction / duplicate relations
        ├── Pause for human review when policy requires it
        ├── Synthesize validated report sections
        └── Persist run, evidence, costs, trace, and checkpoint state
```

### Technical highlights

- **Wiki + Hybrid RAG** — document-level Wiki/overview context helps locate relevant material; BM25 and Qdrant dense/sparse retrieval produce candidates; reciprocal-rank fusion, bounded reranking, and token budgets control the final evidence set.
- **Resumable Agent execution** — LangGraph splits research into bounded stages and PostgreSQL-backed checkpoints. The workflow supports interruption, approval, rejection, retry, and process recovery.
- **Evidence-grounded outputs** — claims, relations, evidence snapshots, section revisions, and citations are validated through typed schemas and server-owned allowlists.
- **Bad Case regression** — negative feedback can be promoted into a frozen evaluation set. PostgreSQL advisory locking serializes dataset version creation and repeatable evaluation.
- **Tenant and data boundaries** — API ownership checks, PostgreSQL RLS, project-scoped Qdrant filters, private object keys, short-lived signed URLs, and redacted observability events protect cross-project data.
- **Explicit degradation** — unavailable reranking, provider failures, unsupported scanned-PDF OCR, and other boundaries are surfaced as states or typed errors rather than hidden as successful answers.

### Technology stack

| Layer | Technologies |
| --- | --- |
| Web | Next.js, React, TypeScript, Tailwind CSS, Radix UI, Vitest, Playwright |
| API | FastAPI, Pydantic, SQLAlchemy, PostgreSQL, OpenAPI |
| Workflow | LangGraph, Celery, Redis, PostgreSQL checkpoints, outbox/dispatcher |
| Retrieval | Qdrant dense/sparse vectors, BM25, hybrid fusion, reranking adapters |
| Documents | S3-compatible object storage, bounded text-layer PDF extraction, Office/document parsers |
| Evaluation | RAGAS adapters, Recall/Citation/Faithfulness metrics, frozen Bad Case datasets |
| Operations | Render, Vercel, GitHub Actions, Langfuse-compatible redacted tracing |

### Repository layout

```text
apps/api/             FastAPI application and domain services
apps/web/             Next.js application and browser workflows
workers/ai-worker/    Celery worker, ingestion, retrieval, and LangGraph runtime
tests/                Python contracts, service tests, and integration-shaped tests
infra/                Supabase migrations, Qdrant configuration, and deployment assets
docs/                 Product, architecture, API, database, frontend, backend, and worker guides
```

### Quick start

#### Prerequisites

- Python 3.13 and `uv`
- Node.js and npm 11+
- PostgreSQL, Redis, Qdrant, and an S3-compatible object store for the full runtime
- Provider credentials only when running real ingestion/retrieval/generation paths

The repository also contains a deterministic public/demo mode for frontend development and Playwright browser tests. It does not require cloud credentials or a local database.

#### Install

```powershell
uv sync --frozen
npm install
```

#### Run the API and web app

```powershell
# Terminal 1
npm run api:dev

# Terminal 2
npm run web:dev
```

Open `http://localhost:3000`. Configure local values from [`.env.example`](./.env.example); never commit secrets.

#### Run the deterministic browser demo

```powershell
npm run test:e2e
```

The Playwright suite starts the web app in explicit demo mode and verifies the core workspace journey without calling external providers.

### Quality gates

```powershell
npm run test
npm run check:lint
npm run check:types
npm run check:openapi
npm run check:migrations
npm run check:web
npm run check:audit
```

The combined gate is available as `npm run check:all`. CI runs Python quality, web quality, browser E2E, container validation, and the required success gate before release.

### Documentation

- [Product scope and capability ledger](./docs/product/index.html)
- [Architecture and technology decisions](./docs/architecture/index.html)
- [API contracts](./docs/contracts/api/index.html)
- [Database contracts](./docs/contracts/data/index.html)
- [Frontend guide](./docs/learn/frontend.html)
- [Backend guide](./docs/learn/backend.html)
- [Worker and ingestion guide](./docs/learn/worker.html)
- [Chinese documentation index](./docs/index.zh.html)

### License

ResearchMate is licensed under the Apache License 2.0. See [LICENSE](./LICENSE) for the full text.
