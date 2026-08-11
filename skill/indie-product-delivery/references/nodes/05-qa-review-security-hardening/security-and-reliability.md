# Security and Reliability

Security review calibrated to indie-product risk. An indie product typically has a
database, user authentication, API endpoints, optional file upload, third-party
integrations (payment, email), and environment variables. This file covers the real
security surface, not an enterprise audit.

Use the Node05 risk classification to select the domains that can change the verdict. Tables are
attention maps: inspect every applicable row deeply, but do not claim assurance for an unrelated
domain merely because its table exists.

## Sections

- [Security and abuse review](#security-and-abuse-review)
- [Reliability and resource boundaries](#reliability-and-resource-boundaries)
- [Security verification](#security-verification)

## Security and abuse review

### Review method

Check each domain by tracing attacker-controlled input to the sink it reaches, not by
pattern-matching alone. For each candidate, identify the source (attacker-controlled
input), the broken or missing control, the sink (dangerous operation or protected
action), and the impact. A pattern without a reachable source-to-sink path is not a
finding.

Suppress a candidate only with concrete counterevidence: framework auto-escaping
verified for the exact output context, an equivalent guard on every path to the sink,
or code that is not shipped or reachable in scope. A safe sibling path does not clear
a distinct path. Do not suppress because an endpoint is intended to perform a risky
action or appears internal by name.

Pair the source-control-sink trace with the smallest safe executable negative proof whenever the
risk is reachable. Prefer an existing focused test, a minimal regression test, or a local
non-destructive reproduction. Use a complete static trace alone only when execution is genuinely
unavailable, and record that limitation as a proof gap rather than PASS-equivalent evidence.

### Quick threat model

Before the domain checklist, identify this project's concrete risk profile in 3-5 lines:

- assets: user data, secrets, payment authority, or admin actions this project has;
- trust boundaries: where unauthenticated, authenticated, tenant, and admin meet;
- high-impact paths: account takeover, cross-tenant access, payment bypass, secret
  exposure, or RCE this architecture makes plausible.

Use this to weight the domains: a multi-tenant SaaS must prioritize 9D authorization;
a webhook-heavy service must prioritize 9G SSRF; a payment product must prioritize 9H.
This step focuses the checklist; it does not replace it.

### 9A Database security

| Check | What to find | Severity |
| --- | --- | --- |
| SQL injection | string-concatenated SQL instead of parameterized queries; ORM raw queries containing user input | Blocker |
| Connection string | database password hardcoded in source; connection string appears in logs or error messages | Blocker |
| DB permissions | app connects as root or superuser instead of a least-privilege user | Major |
| Database file exposure | SQLite file in a web-accessible directory; database backup on a public path | Blocker |
| Migration safety | migration script is irreversible with no backup plan; migration locks tables and causes downtime | Major |
| Query safety | unbounded queries (list or export without LIMIT); N+1 queries that leak data | Major |
| Transaction safety | multi-write operations without a transaction wrapper; partial failure causes inconsistent state | Major |

### 9B Data privacy security

| Check | What to find | Severity |
| --- | --- | --- |
| PII logging | sensitive data (email, phone, address, ID number) appears in logs, console, error messages, or URL parameters | Blocker |
| PII in API response | API returns unnecessary sensitive fields (e.g. user list response includes password hashes) | Blocker |
| HTTPS | HTTPS not enforced; API endpoints allow HTTP; mixed content (HTTP resources on an HTTPS page) | Blocker |
| Data in transit | password or token sent over plain HTTP; API calls without TLS | Blocker |
| Password storage | passwords stored in plaintext or with weak hash (MD5, SHA1); should use bcrypt or argon2 | Blocker |
| Cookie security | session cookie missing HttpOnly, Secure, or SameSite attribute | Blocker |
| localStorage misuse | token or sensitive data stored in localStorage (readable by XSS) instead of httpOnly cookie | Major |
| Data minimization | collecting user data the feature does not need; fields gathered but never used | Major |
| Data retention | no retention or deletion policy; no handling logic for user deletion requests | Major |
| Log injection | attacker input with newlines or control chars written to logs, forging entries or hiding attack trails | Major |

### 9C API security

| Check | What to find | Severity |
| --- | --- | --- |
| Endpoint auth | API endpoint missing auth guard (except explicitly public ones) | Blocker |
| IDOR | resource access by ID without owner or tenant check (e.g. `/api/users/123` does not verify 123 belongs to the current user) | Blocker |
| Input validation | API body, query, or params without type, schema, or size validation | Major |
| Rate limiting | high-risk endpoints (auth, password reset, registration) without rate limit | Major |
| CORS | `Access-Control-Allow-Origin: *` combined with `credentials: true`; or allowing arbitrary origins | Blocker |
| Error disclosure | API error response includes stack trace, SQL, internal path, or database structure | Major |
| File upload validation | no file type or size check; upload path can be traversed; filename not sanitized or renamed | Blocker |
| File upload storage | uploaded files stored in a web-accessible path and are executable (e.g. `.php`, `.js`) | Blocker |
| Batch operation safety | bulk delete or update without confirmation or secondary permission check | Major |
| Path traversal | file access path from user input not canonicalized; `../` or absolute path escapes the intended directory in download, import, or static-serving paths | Blocker |
| Archive extraction | zip/tar extraction without path containment; symlink in archive overwrites trusted files | Blocker |
| Mass assignment | request body auto-bound to model; user can set `role`, `isAdmin`, or `tenantId` | Blocker |

### 9D Authentication and authorization

| Check | What to find | Severity |
| --- | --- | --- |
| Password security | plaintext storage; weak hash; no minimum complexity requirement | Blocker |
| Token security | JWT without expiry; JWT secret hardcoded; refresh token not rotated | Blocker |
| Session security | session not invalidated on logout; session fixation (session ID not rotated after login) | Blocker |
| Privilege escalation | regular user can reach admin routes; role field can be tampered by client | Blocker |
| Brute force | login endpoint has no failure count limit, lockout, or captcha | Major |
| Password reset | reset token has no expiry; reset token is predictable; old sessions not invalidated after reset | Blocker |
| OAuth | OAuth state parameter missing or not checked (CSRF); redirect URI not validated | Blocker |

### 9E Dependencies and environment

| Check | What to find | Severity |
| --- | --- | --- |
| Secret in repo | `.env` or config file containing secrets but not in `.gitignore`; secret already committed to git history | Blocker |
| Dependency vulnerability | `npm audit`, `pip audit`, `cargo audit`, or `yarn audit` reports high-risk vulnerability | Blocker (high) / Major (medium) |
| Fabricated dependency | installed package does not exist (LLM hallucination); installed package is deprecated or known-malicious | Blocker |
| Lockfile | lockfile inconsistent or missing (causes dependency drift) | Major |
| Environment config | production using development config (debug=True, verbose error output); required env variable missing with no fallback handling | Major |
| Container | container runs as root; image contains secrets; unnecessary ports exposed | Major |

### 9F Frontend security

| Check | What to find | Severity |
| --- | --- | --- |
| XSS | `innerHTML`, `dangerouslySetInnerHTML`, or `v-html` rendering user input; output not encoded | Blocker |
| CSP | no Content-Security-Policy header, or header allows `unsafe-inline` or `unsafe-eval` | Major |
| CSRF | state-changing request without CSRF token; or using GET to trigger a write operation | Blocker |
| Open redirect | redirect URL comes from user input and is not validated against a whitelist | Major |
| Client-side secret | API key or secret hardcoded in frontend code (viewable by users) | Blocker |
| postMessage | `window.postMessage` receiver does not validate origin | Major |

### 9G Server-side request forgery (SSRF)

Run when the project has outbound URL features: webhooks, URL previews, image or
document fetchers, callback URLs, or proxy endpoints.

| Check | What to find | Severity |
| --- | --- | --- |
| Outbound URL from user input | webhook, preview, image fetch, or callback URL accepts a user-supplied destination without scheme and host validation | Blocker |
| Internal reach | user URL can reach loopback, link-local, private ranges, or cloud metadata (169.254.169.254) | Blocker |
| Redirect following | HTTP client follows redirects without re-validating the final destination | Major |
| DNS rebinding | first DNS resolution passes validation but second resolves to internal IP | Major |
| URL scheme | scheme not restricted; `file://`, `gopher://`, or `dict://` reaches an unexpected handler | Blocker |

### 9H Business logic and payment security

Run when the project has payment, coupon, quota, or multi-step workflow logic. Mark
NOT_APPLICABLE otherwise.

The reliability section covers idempotency and concurrency as engineering properties; this domain
covers the same mechanisms from an attacker perspective: can a user exploit them to
bypass payment, quota, or workflow constraints.

| Check | What to find | Severity |
| --- | --- | --- |
| Payment bypass | price, quantity, or currency computed client-side and trusted by backend | Blocker |
| Coupon abuse | coupon reusable beyond intended limit; coupon applied to ineligible items | Major |
| Quota bypass | rate limit or usage quota checked client-side or bypassable via race condition | Major |
| Duplicate payment | retry or concurrent submission creates a duplicate charge; verify idempotency and reconciliation | Blocker |
| Workflow bypass | multi-step approval or verification skipped by direct API call to a later step | Blocker |
| Race condition | TOCTOU on balance, inventory, or quota; concurrent requests exploit a check-then-act gap | Major |

### 9I AI and LLM security

Run only when the project has AI or LLM features: prompt construction, tool or
function calling, RAG or retrieval, agent workflows, or model-generated output.
Mark NOT_APPLICABLE otherwise.

| Check | What to find | Severity |
| --- | --- | --- |
| Prompt injection | user or retrieved content can override system instructions or escape the intended task | Blocker |
| Tool authorization | model-generated tool calls executed without capability or permission checks outside the model | Blocker |
| Data exfiltration | model output sent to external endpoints, or tool arguments leak secrets or other-tenant data | Blocker |
| Retrieval poisoning | untrusted documents in the RAG corpus can inject instructions or override safety rules | Major |
| Model output as code | model-generated code, shell, SQL, or config executed without validation | Blocker |
| Secret in context | API keys, tokens, or PII passed into model prompts or context windows | Major |

### STANDARD baseline

No change may introduce a secret leak, reachable XSS, known high-risk dependency, or insecure
transport. Run the corresponding repository scan or executable check when the changed files,
dependency graph, generated bundle, deployment configuration, or release claim can affect that
boundary. Run the SSRF, payment/quota, and AI tables when the change touches their inputs, controls,
or sinks. Otherwise preserve the invariant through source inspection without manufacturing an
unrelated scan.

## Reliability and resource boundaries

Only check items triggered by the change. Mark genuinely irrelevant items as
NOT_APPLICABLE with a one-line reason.

| Check | When to check | What to find |
| --- | --- | --- |
| Error handling | all changes | errors are caught, mapped to user-visible messages, and not silently swallowed |
| Retry and timeout | network or external service calls | bounded timeout, no infinite retry, backoff strategy exists |
| Idempotency | writes, payments, callbacks | duplicate requests do not create duplicate data or double charges |
| Concurrency | shared state or async operations | no race condition, no deadlock, locks released correctly |
| Data consistency | multi-write or transactional operations | transaction atomicity, partial failure does not break invariants, rollback is correct |
| Resource leak | file, connection, or process handling | resources closed on exception paths; no connection pool exhaustion risk |

When one of these rows applies, pair the source review with the smallest deterministic failure proof
that can exercise it—for example a timeout, malformed or partial dependency response, duplicate
delivery, controlled concurrent transition, cleanup assertion, or enforced input/fan-out limit. Do
not run disruptive load, fuzz, chaos, or denial-of-service experiments against production or a
third-party system. If no safe executable boundary exists, record the missing proof and the seam or
environment needed to obtain it.

## Security verification

### Non-destructive negative checks

Use local or staging test accounts. Do not access other users' real data, brute force
credentials, run DoS, make real payments, or run third-party scanners.

| Verification | How | Expected result |
| --- | --- | --- |
| Unauthenticated access | call an auth-required endpoint without a token | 401 or 403, no data returned |
| Unauthorized access | use user A token to access user B resource | 403, no data returned |
| Invalid input | send malformed, oversized, or unexpected-type data | 400 with a meaningful error, no crash |
| SQL injection | send `' OR 1=1 --` in an input field | no extra data returned, no SQL error exposed |
| XSS | send `<script>alert(1)</script>` in an input field | not executed when stored and viewed |
| Expired token | use an expired token to access an endpoint | 401, no data returned |
| File upload | upload an executable, oversized, or no-type file | rejected |
| Password reset | use an expired or already-used reset token | rejected |
| SSRF | submit a webhook or fetch URL pointing to 127.0.0.1 or 169.254.169.254 | rejected or sanitized |
| Payment idempotency | submit a duplicate payment request with the same idempotency key | no duplicate charge |

### Tool scans

Run the repository's existing security tooling.

- Dependency audit: `npm audit`, `pip audit`, `cargo audit`, `yarn audit` (whichever
  applies).
- Lint and static analysis: many linters detect XSS and injection patterns. Run
  whatever the repo already configures.
- SAST: if the repo has CodeQL, Semgrep, or similar configured, run it.

When a tool is not available, mark NOT_RUN and state what is missing. Do not report
a scan result that was not actually executed.

### Findings to record

For each confirmed security finding, state the exploit path: the attacker-controlled
input, the data or control path it follows, the missing or bypassed control, and the
resulting impact. Cite the exact file, line, or configuration. Name the remediation
owner and the retest required after the fix.
