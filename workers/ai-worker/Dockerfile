# Builds the CPU-only combined backend runtime for constrained free-tier hosts.
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCLING_ARTIFACTS_PATH=/opt/docling/models \
    HF_HUB_DISABLE_TELEMETRY=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system researchmate \
    && useradd --system --gid researchmate researchmate
WORKDIR /app
COPY apps/api /app/apps/api
COPY workers/ai-worker /app/workers/ai-worker
COPY infra/supabase/migrations /app/infra/supabase/migrations
COPY scripts/apply_migrations.py /app/scripts/apply_migrations.py
COPY scripts/provision_qdrant_rerank.py /app/scripts/provision_qdrant_rerank.py
RUN python -m pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.13.0+cpu \
      torchvision==0.28.0+cpu \
    && python -m pip install --no-cache-dir /app/apps/api /app/workers/ai-worker \
    && docling-tools models download layout tableformer rapidocr -o /opt/docling/models \
    && chown -R researchmate:researchmate /opt/docling

USER researchmate
CMD ["sh", "-c", "if [ \"${RESEARCHMATE_PROCESS_ROLE:-worker}\" = dispatcher ]; then exec researchmate-dispatch-outbox; else exec python -m celery -A researchmate_worker.celery_app:celery_app worker --loglevel=INFO --queues=ingestion,deletion,workflow,evaluation,reliability --concurrency=2; fi"]
