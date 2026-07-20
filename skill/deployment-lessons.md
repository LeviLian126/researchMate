# Deployment Lessons

Scope: ResearchMate free-tier public-demo preparation, observed on 18–19 July 2026. This operational note records reusable delivery lessons. It contains no account identifier, endpoint, project reference, access key, password, token, or user data.

## Keep the deployment boundary explicit

- Cloudflare Workers plus OpenNext is a suitable free public surface for a Next.js portfolio walkthrough.
- It is not a substitute for a Python FastAPI API, Celery worker, or transactional-outbox dispatcher. A Worker deployment must never be described as proof that those processes run in production.
- The first public release therefore uses an explicit browser-only deterministic-demo adapter. It makes no authenticated session, storage, database, Redis, Qdrant, model-provider, or telemetry request.

## Keep free resources isolated and bounded

- Configure new Supabase projects deliberately: disable automatic public-schema exposure, enable automatic RLS, and record the selected region.
- A private Storage bucket can enforce a MIME allowlist and maximum object size. ResearchMate accepts PDF, DOCX, and PPTX files up to 25 MB.
- Do not silently reuse a development Qdrant cluster as production. If creating an isolated free cluster requests payment information, leave production unconfigured rather than adding a card for a checklist item.
- Keep Cloudflare R2 inactive while the deterministic demo does not require object storage. Its activation can create billing exposure without improving the public walkthrough.

## Handle credentials as one-time, platform-only values

- One-time provider credentials should be created only after a protected deployment secret store is ready, then copied directly into that store in the same session.
- Never place connection strings, object-storage keys, API tokens, project references, or copied browser content in repository files, HTML documentation, CI logs, screenshots, shell history, or chat output.
- GitHub Environment names are case-sensitive. Deployment configuration is not integration evidence: documentation must separately state whether migrations, requests, authentication, queue delivery, and readiness smoke have actually run.
- Use a short-lived `CLOUDFLARE_API_TOKEN` scoped to the selected Worker deployment template. Revisit provider templates when a narrower compatible permission set becomes available.

## Validate the correct build artifact

- The OpenNext Cloudflare package rejected the repository's Next.js canary through npm peer-dependency resolution. Moving to a supported stable Next.js release allowed installation and Worker bundle generation.
- Run both the ordinary Next.js production build and the OpenNext build. A successful Next.js build alone does not prove the Worker artifact exists.
- Build public-demo releases with `NEXT_PUBLIC_DEMO_MODE=true` explicitly. Do not rely on implicit production defaults for a public-runtime safety boundary.
- Keep the release workflow manual and protected until public smoke evidence exists. It must not apply migrations, publish backend images, or configure paid providers as a side effect of releasing a static demo.

## Treat local tool behavior as evidence, not a substitute for release proof

- OpenNext emitted a Windows compatibility warning. The bundle completed, but local Wrangler preview could not be accepted as public-runtime proof: the restricted Windows environment attempted to create an XDG configuration directory and a later isolated retry did not produce a usable preview.
- Repository npm scripts can resolve to the system Python rather than the project environment. In this workspace that caused test collection to fail with a missing `qdrant_client`, although the dedicated environment at `D:\software\env\researchmate` contains the required dependency. Activate that environment or invoke it explicitly before judging Python failures.
- OpenNext can create an `apps/web/.wrangler` transient directory. Ignore and remove it before source-level secret scans; generated Worker output is not source evidence.

## Release and recovery checklist

1. Confirm the protected workflow completed and record the generated `workers.dev` URL in current-state HTML only after observing it.
2. Open the public URL in a fresh browser session; check the static-demo banner, root navigation, workspace creation, document lifecycle simulation, Ask, report refresh, quiz, evaluation, and reliability pages.
3. Confirm browser network activity has no calls to managed API, Supabase, storage, Redis, Qdrant, LLM, Tavily, or Langfuse endpoints.
4. On a failed or unsafe public demo, roll back or delete only the Worker deployment. The static demo owns no managed persistent state, so no database restoration is required.
