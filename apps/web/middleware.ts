// Injects a per-request nonce into the response so the Content-Security-Policy
// can drop the static 'unsafe-inline' for script-src. Nonces make inline
// scripts signed by the server the only acceptable ones at any moment.
import { NextResponse, type NextRequest } from "next/server";
import { randomUUID } from "node:crypto";
import { buildNonceCsp } from "./app/lib/csp-origins";

const NONCE_HEADER = "x-researchmate-nonce";

/** Generate a cryptographically strong random nonce (32 hex chars). */
function makeNonce(): string {
  // randomUUID() gives 128 bits of entropy; strip dashes for a clean CSP value.
  return randomUUID().replaceAll("-", "");
}

/** Adds a nonce + nonce-aware CSP to every response so inline scripts are signed. */
export function middleware(request: NextRequest): NextResponse {
  const nonce = makeNonce();
  const csp = buildNonceCsp(nonce);
  // Forward the nonce to the React tree via request headers so layout/components
  // can pass it to next/script's `nonce` prop or inline <script> tags.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  // Run on every page + API route so the nonce and CSP are consistent. Skip
  // Next-internal static assets so the dev server can stream them untouched.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg).*)"],
};
