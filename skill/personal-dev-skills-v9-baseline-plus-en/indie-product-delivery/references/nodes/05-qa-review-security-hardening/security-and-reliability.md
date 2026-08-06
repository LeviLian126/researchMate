# Security and Reliability

Security review calibrated to indie-product risk. An indie product typically has a
database, user authentication, API endpoints, optional file upload, third-party
integrations (payment, email), and environment variables. This file covers the real
security surface, not an enterprise audit.

STANDARD changes run CP9 baseline items plus CP11 basic scan. HIGH_RISK changes run
CP9 in full, CP10, and CP11 full scan.

## CP9: Full security review

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

### STANDARD baseline

For STANDARD changes, run at minimum: secret-in-repo check (9E), XSS check (9F),
dependency vulnerability scan (9E), and HTTPS check (9B). These four are indie-product
baselines regardless of risk level.

## CP10: Reliability

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

## CP11: Security verification

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

### Tool scans

Run the repository's existing security tooling. Do not install new tools unless the
user agrees.

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
