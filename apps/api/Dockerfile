FROM ghcr.io/astral-sh/uv:0.12.1 AS uv
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

COPY --from=uv /uv /uvx /bin/
RUN groupadd --gid 10001 researchmate \
    && useradd --uid 10001 --gid researchmate --no-create-home --shell /usr/sbin/nologin researchmate
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY workers/ai-worker/pyproject.toml /app/workers/ai-worker/pyproject.toml
COPY apps/api /app/apps/api
RUN uv sync --frozen --no-dev --package researchmate-api

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/healthz', timeout=3)"]
# Shell form is required so Render's runtime PORT value is expanded safely.
CMD ["sh", "-c", "exec python -m uvicorn researchmate_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers"]
