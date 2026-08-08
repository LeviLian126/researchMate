# AGENTS.md

This file orients AI code generation tools (CodeAgentCLI, Cursor, Copilot, Codex, etc.) to the
ResearchMate repository's coding standards. Generated code must comply with these rules.

Repository layout:

- `apps/api/` — FastAPI surface (`researchmate_api` package).
- `workers/ai-worker/` — Celery worker (`researchmate_worker` package).
- `apps/web/` — Next.js frontend (separate TypeScript conventions).
- `tests/` — pytest suite shared across API + worker packages.
- `scripts/` — developer tooling (OpenAPI export, migration application, doc repair).
- `infra/` — Infrastructure manifests (Render).
- `docs/` — HTML-first documentation.

Tooling baseline:

- Python 3.13, `ruff==0.16.0`, `pyright==1.1.390`, `pytest>=9`, `coverage>=7.10`.
- Line length: 100 characters.
- Type checker: `pyright` in `basic` mode (project config in root `pyproject.toml`).
- Pre-commit hooks: see `.pre-commit-config.yaml`.

## Required patterns

### 1. Every Python module starts with `from __future__ import annotations`

The project enforces PEP 563 (string-form annotations) everywhere so that `X | Y` syntax works
in runtime environments where Python's PEP 604 union form on older interpreters would otherwise
matter, and so that ruff/`pyupgrade` rules can rewrite annotation syntax uniformly.

```python
"""Module docstring."""

from __future__ import annotations

import json
from typing import Any
```

The future import goes immediately after the module docstring, before any other code. Ruff's `UP`
rules enforce the corresponding PEP 604 annotation style.

### 2. Type hints are required on every function signature

Both parameters and return types must be annotated. `Any` is only acceptable when genuinely
untyped external data crosses a boundary; in those cases, narrow the type as soon as possible.

```python
# GOOD
def build_grounded_answer(query: str, chunks: list[ChunkEntry]) -> tuple[str, list[Citation]]:
    ...


# BAD – missing return annotation, untyped `chunks`
def build_grounded_answer(query, chunks):
    ...
```

### 3. Naming conventions

- **Functions and variables**: `snake_case` — `build_grounded_answer`, `local_chunks`.
- **Classes** (Pydantic models, services, exceptions): `PascalCase` — `GroundedAnswer`,
  `QuizGenerationError`.
- **Module-level constants**: `SCREAMING_SNAKE_CASE` — `MAX_TEXT_LENGTH`, `MIME_BY_TYPE`.
- **Private helper modules**: leading underscore — `_store_chunks.py`, `_QuizProposalQuestion`.
- **Test functions**: `test_*` prefix. Test file names: `test_*.
.py`.
- Enum members are `SCREAMING_SNAKE_CASE` and inherit from `(str, Enum)` so values serialize.

### 4. Error handling

Fail closed at boundaries. Catch a specific exception class, log it with context, and re-raise a
domain-specific error. Never swallow exceptions silently.

```python
# GOOD
try:
    result = self.client.query_points(...)
except QdrantClientError as exc:
    LOGGER.warning("rerank_query_failed error=%s", type(exc).__name__)
    raise VectorStoreRequestError("rerank") from exc
```

```python
# BAD – bare except with no logging and no re-raise
try:
    result = self.client.query_points(...)
except Exception:
    pass
```

Provider boundaries (LLM, search, retrieval) MAY catch the broadest SDK exception once and wrap it
into a typed domain error, but only at the outermost edge and only with logging.

### 5. Comments are English only

Every code comment, docstring, and commit-message body must be in English. Chinese comments
and bilingual comments are not permitted in source. User-facing string literals may be localized
separately (see `apps/api/src/researchmate_api/services/answering.py` for the Chinese-only
local fallback case).

### 6. No unjustified `typing.Any`

`Any` is reserved for genuine boundary interop (raw JSON, framework payloads). When you see
`Any` in a public signature, add a comment explaining why. Prefer `object` for "any value, no
operations" and `object[UnknownType]` for opaque framework data.

### 7. Use domain constants instead of magic numbers

Centralize tunable values and length bounds in `apps/api/src/researchmate_api/schemas/common.py`
(or a domain-relevant module) and import them. Don't hard-code numbers like `1200` in pydantic
validators, MCP payload trims, or rerank query truncations.

```python
# GOOD
from researchmate_api.schemas.common import MAX_TEXT_LENGTH
text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

# BAD
text: str = Field(min_length=1, max_length=1200)
```

## Prohibited patterns

| Pattern | Reason | Replacement |
|---|---|---|
| `except Exception:` (bare) without logging | Swallows real failures, hides outages | Catch specific exception types; log with context; raise a typed domain error |
| `except Exception: pass` | Silent failure | Convert to explicit fallback or re-raise |
| `# ...` Chinese comments | Breaks review and grep across contributors | Translate to English |
| `typing.Any` in public signatures without a comment | Untyped contracts | Narrow at boundary; prefer `object`, `Protocol`, or specific `TypedDict` |
| `import *` (wildcard imports) | Hides provenance, breaks ruff `F401` tracking | Import the names you use |
| Mutable default arguments (`def f(x=[]):`) | State leak across calls | Use `default_factory=list` (Pydantic) or `None` sentinel |
| String-existence tests for behavior | Brittle against refactor | Assert on observable API behavior (status code, JSON shape) |
| Hard-coded magic numbers in validators | Drift across schema/storage | Import a shared constant |

## Examples

### Good pydantic schema

```python
"""Define the public status record for owner-scoped asynchronous jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from researchmate_api.schemas.common import JobStatus


# Define the asynchronous job response.
class JobRecord(BaseModel):
    """Represent an asynchronous job without exposing worker internals."""

    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    document_id: UUID | None = None
    type: str = Field(min_length=2, max_length=80)
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(use_enum_values=True)
```

### Bad schema (do not generate)

```python
import typing  # noqa: TID252 - typing.Any
from pydantic import BaseModel

def make_job():  # missing types, magic number, Chinese docstring
    pass

class Job(BaseModel):
    type: typing.Any  # unjustified Any
    status: str = "pending"
    progress: int = 0
    # 校验进度范围 0-100  ← Chinese comment not allowed
```

## Running the gates

- Lint: `npm run check:lint` (ruff across `apps/api/src`, `workers/ai-worker/src`, `tests/`).
- Format check: `uv run ruff format --check apps/api/src workers/ai-worker/src tests/`.
- Types: `npm run check:types` (pyright via root `pyproject.toml`).
- Tests + coverage: `npm run test:python` (threshold: 69%).
- All: `npm run check:all`.

Pre-commit hooks (configured in `.pre-commit-config.yaml`) run ruff, ruff-format, and pyright
locally before each commit. Install them once with `uv run pre-commit install`.

## Reviewer notes for generated diffs

When you generate code, double-check:

1. The file starts with `from __future__ import annotations` after the module docstring.
2. Every new function signature is fully type-annotated.
3. No new `except Exception:` blocks without logging.
4. No new Chinese comments.
5. No bare `typing.Any` in the public API.
6. Any new numeric bound references a domain constant rather than a literal.
7. Tests assert on observable behavior, not on internal string contents.
