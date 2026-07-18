# Cloud Provisioning Lessons

Scope: ResearchMate no-card deployment preparation, observed on 18 July 2026. This is an operational learning note, not a deployment plan and contains no endpoint, project identifier, access key, password, token, or user data.

## Supabase project creation

- The create-project form can default to exposing new public-schema tables while automatic RLS is off. Before creating a project, explicitly disable automatic public-table exposure and enable automatic RLS; do not rely on the defaults.
- Record the chosen region before creation. The target application should use the same region when a free provider makes that practical, but correctness and isolation matter more than a cosmetic region match.
- A private Storage bucket can enforce a maximum file size and a MIME allowlist at the provider boundary. For this demo, the allowed inputs are PDF, DOCX, and PPTX and the maximum is 25 MB.

## One-time credentials

- Supabase S3 access keys are shown once. Create one only when a protected target secret store is ready, copy it directly into that store in the same browser session, then close the confirmation screen.
- Never place connection strings, object-storage keys, API keys, project references, or copied browser content in the repository, HTML documentation, CI logs, screenshots, shell history, or chat output.
- Public browser client keys are still release inputs. Store them in the deployment environment when the workflow expects them there, even though they are not privileged secrets.

## GitHub Environments

- GitHub Environment display names are case-sensitive workflow inputs. This repository uses `Production` for the protected GitHub environment and maps it to lower-case application environment `production`; keep that conversion explicit in release automation.
- Environment secrets and variables are deployment configuration, not evidence that an integration works. Documentation must separately state whether migrations, requests, authentication, queue delivery, and readiness smoke have run.

## Free-tier isolation limit

- The observed Qdrant account already had a Free development cluster. Its new-cluster flow offered a paid configuration and requested payment information; do not add a card or create a paid cluster merely to complete a portfolio checklist.
- Do not silently reuse a development vector cluster as production. Mark production Qdrant as unconfigured, keep runtime release blocked, and revisit only when a separate no-card resource or an approved alternative is available.

## Human-in-the-loop boundary

- Azure portal login alone does not create a subscription. Azure for Students requires the account owner to complete the academic-identity enrollment; do not attempt to invent or bypass that verification.
- After enrollment, configure Azure OIDC before running a release. The release reconciler is additive, but the first run still creates cloud resources and must be followed by managed health/readiness evidence.
