// Exposes the per-request CSP nonce to client components so any first-party
// inline script can be signed with the same nonce middleware produced.
"use client";
import { createContext, useContext } from "react";

// Empty-string default means "no nonce available"; inline scripts without a
// nonce will be blocked by the browser and silently dropped at runtime.
export const NONCE_CONTEXT_DEFAULT = "";

export const SessionNonceContext = createContext<string>(NONCE_CONTEXT_DEFAULT);

/** Returns the active CSP nonce or an empty string when middleware omitted one. */
export function useSessionNonce(): string {
  return useContext(SessionNonceContext);
}
