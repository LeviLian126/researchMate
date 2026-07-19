# Cloudflare Workers Deployment Lessons

Scope: ResearchMate public-demo deployment work observed on 19 July 2026. This is an operational learning note, not a credential record. It intentionally contains no account identifier, endpoint, token, access key, or browser-exported value.

## Decision boundary

- Cloudflare Workers plus OpenNext is a suitable free public surface for the Next.js portfolio walkthrough.
- It is not a substitute for the repository's Python FastAPI API, Celery worker, or transactional-outbox dispatcher. A Worker deployment must not be described as a successful deployment of those processes.
- The first public release therefore uses an explicit browser-only deterministic-demo adapter. It makes no authenticated session, storage, database, Redis, Qdrant, model-provider, or telemetry request.

## Package compatibility

- The OpenNext Cloudflare package rejected the repository's Next.js canary through npm peer-dependency resolution. Moving the web workspace to the supported stable Next.js release allowed dependency installation and Worker bundle generation.
- Run both the ordinary Next.js production build and the OpenNext build. A successful Next build alone does not prove that the Worker artifact exists.
- OpenNext emitted a Windows compatibility warning. The bundle completed, but local Wrangler preview could not be accepted as proof: the restricted Windows environment attempted to create an XDG configuration directory and a later isolated retry did not produce a usable preview. Treat this as a local-preview limitation until a public Worker smoke succeeds.

## Release controls

- Use a protected GitHub environment and a short-lived `CLOUDFLARE_API_TOKEN` scoped to the selected Worker deployment template; do not put it in a repository file, `.env` committed to Git, shell history, log output, screenshot, or this note. Revisit the provider template when Cloudflare offers a narrower compatible permission set.
- The release workflow should build with `NEXT_PUBLIC_DEMO_MODE=true` explicitly. Relying on an implicit production default makes the public-runtime boundary easy to accidentally change.
- The workflow should have one manual target until public smoke evidence exists. It should not apply migrations, publish backend images, or configure paid providers as a side effect of releasing the static demo.

## Verification checklist

1. Confirm the protected workflow completed and record its generated `workers.dev` URL in the current-state HTML only after observing it.
2. Open the public URL in a fresh browser session; check the visible static-demo banner, root navigation, workspace creation, document lifecycle simulation, Ask, report refresh, quiz, evaluation, and reliability pages.
3. Confirm browser network activity has no calls to managed API, Supabase, storage, Redis, Qdrant, LLM, Tavily, or Langfuse endpoints.
4. If the release fails, keep the current documentation status as `bundle built; deployment failed or unverified`; never infer a live URL from local build output.

## Windows validation pitfall

- Repository npm scripts can resolve to the system Python rather than the project environment. In this workspace that caused test collection to fail with a missing `qdrant_client`, although the dedicated environment at `D:\software\env\researchmate` contains the required dependency.
- Run Python quality checks with that environment explicitly (or activate it first). Do not report this environment-selection failure as a product-code regression.
- OpenNext also creates an `apps/web/.wrangler` transient directory during local tooling runs. Ignore it and remove it before source-level secret scans; generated Worker output may contain provider-shaped fixture text and is not source evidence.

## Cost and rollback

- Keep Cloudflare R2 unactivated for this slice because object storage is not required by the deterministic public demo and activation can introduce billing exposure.
- On a failed or unsafe public demo, roll back or delete only the Worker deployment; this does not require database restoration because the demo owns no persistent managed state.
