# ResearchMate

Production-oriented agentic RAG research workspace: FastAPI surface, Celery worker, and a Next.js
web client. See `docs/` for the HTML-first product and architecture documentation.

## Repository layout

```
apps/api/         researchmate_api  — FastAPI REST + MCP application surface
apps/web/         @researchmate/web — Next.js frontend
workers/ai-worker researchmate_worker — Celery ingestion, evaluation, and reliability workers
packages/shared/  shared TypeScript helpers
tests/            pytest suite (API + worker contracts)
scripts/          OpenAPI export, migration application, doc repair
infra/            Render deployment manifest
docs/             HTML documentation (architecture, API, DB schema, PRD)
```

## Requirements

- Python 3.13
- Node 22 (frontend)
- [uv](https://docs.astral.sh/uv/) 0.12.1+ for locked Python dependencies
- npm 11.6.0+ (workspaces)

## Setup

```bash
# Python environment (locked), including dev tooling (ruff, pyright, pre-commit)
uv sync --frozen --all-packages --group dev

# Frontend dependencies
npm install --no-audit --no-fund
```

## Common commands

| Command | Description |
|---|---|
| `npm run api:dev` | Run the FastAPI dev server on `127.0.0.1:8000` |
| `npm run web:dev` | Run the Next.js dev server |
| `npm run test` | Run Python + web tests |
| `npm run test:python` | Run pytest with coverage (threshold: 70%) |
| `npm run test:web` | Run vitest with coverage (threshold: 60%) |
| `npm run check:lint` | Run `ruff check` across API/worker/tests |
| `npm run check:types` | Run `pyright` (basic mode, Python 3.13 target) |
| `npm run check:openapi` | Verify the exported OpenAPI matches the source |
| `npm run check:migrations` | Verify migration file contracts |
| `npm run check:web` | Build the web application |
| `npm run check:audit` | Audit production dependencies |
| `npm run check:all` | Run every gate above in sequence |

## Pre-commit hooks

The repository ships a `.pre-commit-config.yaml` that runs `pre-commit-hooks`, `ruff`,
`ruff-format`, and `pyright` before each commit. Hooks reuse the locked `uv` environment so
there is no second virtualenv to maintain.

Install once after cloning:

```bash
uv sync --frozen --all-packages --group dev
uv run pre-commit install
```

After install, hooks run automatically on `git commit`. To run all hooks manually across the
full tree (slow on first run as pyright warms up):

```bash
uv run pre-commit run --all-files
```

To skip pre-commit on a one-off commit (not recommended for shared branches):

```bash
git commit --no-verify ...
```

The pre-commit configuration references versions pinned in `uv.lock` (`ruff==0.16.0`,
`pyright==1.1.390`, `pre-commit>=4.2.0,<5`). When the `pyproject.toml` dev dependency list
changes (e.g., adding pyright or pre-commit for the first time, or bumping a version), refresh
the lockfile once before pushing:

```bash
uv lock
uv sync --frozen --all-packages --group dev   # verify
```

CI's `uv sync --frozen` step will fail until the lockfile is committed in sync with
`pyproject.toml`. Bump the version in `pyproject.toml` and run `uv lock` to upgrade both
the CI gate and the hook simultaneously.

## Code conventions

See [`AGENTS.md`](./AGENTS.md) for the project's full AI-facing coding standards. Highlights:

- Every Python module starts with `from __future__ import annotations` after the docstring.
- Type hints required on every function signature.
- `snake_case` functions/variables, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants.
- No bare `except Exception` without logging.
- English-only comments and commit messages.
- Use shared constants (e.g., `MAX_TEXT_LENGTH`) instead of magic numbers in validators.
- Line length: 100 characters.

## CI

See `.github/workflows/ci.yml`. The `python-quality` job runs tests, type checks, lint, and
contract verification; the `web-quality` job runs vitest + build + audit; the `browser-e2e` job
runs Playwright; the `container-quality` job lints Dockerfiles and scans images.
