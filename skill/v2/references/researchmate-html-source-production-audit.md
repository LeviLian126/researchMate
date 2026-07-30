# ResearchMate HTML / source / production audit

Audit date: 30 July 2026.

## Result

The maintained HTML describes the current unified chat, project/conversation model, project Quiz, Hybrid RAG, Web option, dual rerank strategy, combined Render topology, and explicit validation boundaries. The public API contract is aligned: repository and deployed OpenAPI each expose 39 paths and 45 operations.

The only material drift found was release identity. The pages still called `96cbcf0` and GitHub Actions run `30512614637` current after the sidebar brand crop/layout CSS release moved the checked application ref to `66c31a8` with successful run `30514995551`. That commit does not replace the underlying image asset.

## Evidence checked

- Repository `main` and `origin/main`: `66c31a8a5dfd937ba2e5aefc71ef922d64ba6ae4`.
- GitHub Actions: run `30514995551`, success, same head SHA.
- Vercel application: `https://research-mate-web.vercel.app/app`, HTTP 200; platform deployment status for the checked ref was inspected separately.
- Render liveness: `https://researchmate-backend-dev-jkza.onrender.com/api/v1/healthz`, status `ok`; platform deployment status for the checked ref was inspected separately.
- Render combined readiness: `https://researchmate-backend-dev-jkza.onrender.com/api/v1/readyz`, status `ready`; database, Redis, worker, dispatcher, outbox, checkpoint, and Qdrant ready.
- Production OpenAPI: 39 paths / 45 operations.
- Repository `infra/openapi/openapi.yaml`: 39 paths / 45 operations.

The Vercel/Render same-ref statement comes from a manual platform deployment-status check during this audit. This repository snapshot does not contain immutable platform deployment receipts, and public health endpoints alone do not prove a particular Git SHA.

## Evidence semantics retained

The bounded model comparison, 9.1-second warm ordinary turn, 13.4-second Web turn, and full authenticated browser journey were collected on the earlier performance release. Those references remain historical evidence rather than being relabeled as tests executed on the later CSS-only sidebar brand release.

## Remaining unverified boundaries

Authenticated Qdrant/NVIDIA provider hot switching, NVIDIA Ranking availability, direct database RLS, scanned-PDF OCR, telemetry export, large-corpus quality, recovery under failure, responsive/accessibility coverage, and production latency distributions remain unclaimed.
