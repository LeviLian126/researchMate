FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

RUN groupadd --system researchmate && useradd --system --gid researchmate researchmate
WORKDIR /app
COPY apps/api /app/apps/api
RUN python -m pip install --no-cache-dir /app/apps/api

USER researchmate
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/healthz', timeout=3)"
CMD ["sh", "-c", "python -m uvicorn researchmate_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers"]
