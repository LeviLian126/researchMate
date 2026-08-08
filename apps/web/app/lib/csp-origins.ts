// Centralizes the CSP origin allow-list so next.config.ts and middleware.ts
// assemble the same connect-src without duplicating the source of truth.
// SEC-4: explicit origins replace the earlier permissive `https:` wildcard.
// The browser never calls provider endpoints (NVIDIA, Tavily, Langfuse)
// directly — those calls live on the FastAPI backend, server-to-server, so
// they intentionally stay out of the client CSP allow-list.

/** Returns the protocol + host + port of `url`, or null when invalid. */
export function safeOrigin(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    // Strip any trailing path so only scheme + host + port remain.
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return null;
  }
}

// Backend base URL is what the browser actually calls for /api/v1 rewrites.
const BACKEND_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/**
 * Static list of every cross-origin host the browser may connect to.
 * Backend-only provider endpoints are deliberately omitted: the browser only
 * ever talks to its own origin, the Supabase auth host, and the proxied API
 * backend. All LLM/search/telemetry calls happen server-to-server on the
 * FastAPI worker, where CSP does not apply.
 */
export const allowedConnectOrigins: readonly string[] = [
  safeOrigin(process.env.NEXT_PUBLIC_SUPABASE_URL),
  safeOrigin(BACKEND_API_BASE),
].filter((origin): origin is string => Boolean(origin));

/** Local-development loopback allowances for live reload + dev server ports. */
export function developmentConnections(): string {
  return process.env.NODE_ENV === "development"
    ? " http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*"
    : "";
}

/** Local-development allowance for eval-based HMR tooling. */
export function developmentScripts(): string {
  return process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : "";
}

/** Builds the static CSP string used by both next.config headers and middleware. */
export function buildStaticCsp(): string {
  return [
    "default-src 'self'",
    `script-src 'self'${developmentScripts()}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    `connect-src 'self' ${allowedConnectOrigins.join(" ")}${developmentConnections()}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "worker-src 'self' blob:",
  ].join("; ");
}

/** Returns the CSP with `script-src 'self'` augmented by a per-request nonce. */
export function buildNonceCsp(nonce: string): string {
  return buildStaticCsp().replace(
    /script-src 'self'([^;]*)/,
    `script-src 'self' 'nonce-${nonce}'$1`,
  );
}
