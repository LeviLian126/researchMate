# Builds the CPU-only combined backend runtime for constrained free-tier hosts.
FROM ghcr.io/astral-sh/uv:0.12.1 AS uv
FROM python:3.13-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DOCLING_ARTIFACTS_PATH=/opt/docling/models \
    HF_HUB_DISABLE_TELEMETRY=1

COPY --from=uv /uv /uvx /bin/
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0 libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 researchmate \
    && useradd --uid 10001 --gid researchmate --no-create-home --shell /usr/sbin/nologin researchmate
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY apps/api /app/apps/api
COPY workers/ai-worker /app/workers/ai-worker
COPY infra/supabase/migrations /app/infra/supabase/migrations
COPY scripts/apply_migrations.py /app/scripts/apply_migrations.py
COPY scripts/provision_qdrant_rerank.py /app/scripts/provision_qdrant_rerank.py
COPY scripts/provision_qdrant_hybrid.py /app/scripts/provision_qdrant_hybrid.py
RUN uv sync --frozen --no-dev --all-packages \
    && rm -f /bin/uv /bin/uvx

FROM dependencies AS runtime
RUN docling-tools models download layout tableformer rapidocr -o /opt/docling/models \
    && chown -R researchmate:researchmate /opt/docling

USER 10001:10001
CMD ["sh", "-c", "if [ \"${RESEARCHMATE_PROCESS_ROLE:-worker}\" = dispatcher ]; then exec researchmate-dispatch-outbox; else exec python -m celery -A researchmate_worker.celery_app:celery_app worker --loglevel=INFO --queues=ingestion,deletion,workflow,evaluation,reliability --concurrency=2; fi"]
