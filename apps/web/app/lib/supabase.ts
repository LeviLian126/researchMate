// Owns browser Supabase authentication, session restoration, refresh, persistence, and notifications.
"use client";

export interface BrowserAuthSession {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: { email?: string; role?: string } | null;
}

type SessionListener = (session: BrowserAuthSession | null) => void;
const STORAGE_KEY = "researchmate_supabase_session";
const REFRESH_SKEW_MS = 60_000;
const listeners = new Set<SessionListener>();
let currentSession: BrowserAuthSession | null | undefined;
let refreshPromise: Promise<BrowserAuthSession | null> | null = null;
let refreshTimer: number | null = null;

/** Detects the explicit local mode where a development identity is allowed. */
export function isLocalDevelopment(): boolean {
  const configured = process.env.NEXT_PUBLIC_APP_ENV;
  return process.env.NODE_ENV === "development" && (!configured || configured === "local");
}

/** Reads the public Supabase browser configuration only when both values are present. */
function configuration(): { url: string; anonKey: string } | null {
  if (isLocalDevelopment()) return null;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return url && anonKey ? { url, anonKey } : null;
}

/** Reports whether this deployment can offer Supabase authentication. */
export function isSupabaseConfigured(): boolean {
  return configuration() !== null;
}

/** Broadcasts canonical authentication changes to active UI subscribers. */
function notify(session: BrowserAuthSession | null) {
  for (const listener of listeners) listener(session);
}

/** Stores or clears the browser session and then notifies subscribers. */
function persist(session: BrowserAuthSession | null) {
  currentSession = session;
  if (typeof window !== "undefined") {
    if (refreshTimer !== null) window.clearTimeout(refreshTimer);
    refreshTimer = null;
    try {
      if (session) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // The in-memory session still works for this tab when storage is unavailable.
    }
    if (session) {
      const delay = Math.max(0, session.expires_at - Date.now() - REFRESH_SKEW_MS);
      refreshTimer = window.setTimeout(() => void refreshSession(session.refresh_token), delay);
    }
  }
  notify(session);
}

/** Extracts display-only identity claims without treating them as authorization. */
function identityFromAccessToken(token: string): { email?: string; role?: string } {
  try {
    const segment = token.split(".")[1];
    const normalized = segment.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
    const decoded = JSON.parse(atob(padded)) as {
      email?: unknown;
      app_metadata?: { role?: unknown };
    };
    const role = decoded.app_metadata?.role;
    return {
      email: typeof decoded.email === "string" ? decoded.email : undefined,
      role: typeof role === "string" ? role : undefined,
    };
  } catch {
    return {};
  }
}

/** Validates and normalizes the provider token response into browser session state. */
function toSession(payload: Record<string, unknown>): BrowserAuthSession {
  if (typeof payload.access_token !== "string" || typeof payload.refresh_token !== "string") {
    throw new Error("Supabase Auth returned an invalid session payload.");
  }
  const expiresIn = typeof payload.expires_in === "number" ? payload.expires_in : 3600;
  const tokenIdentity = identityFromAccessToken(payload.access_token);
  const user = payload.user && typeof payload.user === "object"
    ? payload.user as { email?: string; app_metadata?: { role?: string } }
    : null;
  return {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: Date.now() + expiresIn * 1000,
    user: {
      email: user?.email ?? tokenIdentity.email,
      role: user?.app_metadata?.role ?? tokenIdentity.role,
    },
  };
}

/** Consumes an OAuth redirect fragment and removes tokens from the visible URL. */
function restoreRedirectSession(): BrowserAuthSession | null {
  if (typeof window === "undefined" || !window.location.hash) return null;
  const values = new URLSearchParams(window.location.hash.slice(1));
  const accessToken = values.get("access_token");
  const refreshToken = values.get("refresh_token");
  if (!accessToken || !refreshToken) return null;
  const expiresIn = Number(values.get("expires_in") || 3600);
  const session: BrowserAuthSession = {
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_at: Date.now() + (Number.isFinite(expiresIn) ? expiresIn : 3600) * 1000,
    user: identityFromAccessToken(accessToken),
  };
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return session;
}

/** Restores a structurally valid persisted session from browser storage. */
function restoreStoredSession(): BrowserAuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<BrowserAuthSession>;
    if (typeof value.access_token !== "string" || typeof value.refresh_token !== "string" || typeof value.expires_at !== "number") return null;
    const tokenIdentity = identityFromAccessToken(value.access_token);
    return {
      access_token: value.access_token,
      refresh_token: value.refresh_token,
      expires_at: value.expires_at,
      user: {
        email: value.user?.email ?? tokenIdentity.email,
        role: tokenIdentity.role,
      },
    };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

/** Sends a configured Supabase Auth request and normalizes provider failures. */
async function authRequest(path: string, init: RequestInit): Promise<Record<string, unknown>> {
  const config = configuration();
  if (!config) throw new Error("Supabase Auth is not configured.");
  const headers = new Headers(init.headers);
  headers.set("apikey", config.anonKey);
  headers.set("Content-Type", "application/json");
  if (!headers.has("Authorization")) headers.set("Authorization", `Bearer ${config.anonKey}`);
  const response = await fetch(`${config.url}/auth/v1${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(typeof body.msg === "string" ? body.msg : "Supabase Auth request failed.");
  return body;
}

/** Refreshes an expiring session and clears invalid refresh credentials. */
async function refreshSession(refreshToken: string): Promise<BrowserAuthSession | null> {
  if (!refreshPromise) {
    refreshPromise = authRequest("/token?grant_type=refresh_token", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then((payload) => {
      const session = toSession(payload);
      persist(session);
      return session;
    }).catch(() => {
      persist(null);
      return null;
    }).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/** Returns a usable session, refreshing it when it approaches expiry. */
export async function getSupabaseSession(): Promise<BrowserAuthSession | null> {
  if (!configuration()) return null;
  if (currentSession === undefined) {
    const restored = restoreRedirectSession() ?? restoreStoredSession();
    currentSession = restored;
    if (restored) persist(restored);
  }
  if (!currentSession) return null;
  if (currentSession.expires_at <= Date.now() + REFRESH_SKEW_MS) return refreshSession(currentSession.refresh_token);
  return currentSession;
}

/** Subscribes to browser authentication state and returns an unsubscribe callback. */
export function onAuthStateChange(listener: SessionListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Signs in with email and password and persists the resulting session. */
export async function signInWithPassword(email: string, password: string): Promise<BrowserAuthSession> {
  const payload = await authRequest("/token?grant_type=password", { method: "POST", body: JSON.stringify({ email, password }) });
  const session = toSession(payload);
  persist(session);
  return session;
}

/** Creates an email/password identity and persists a session when email confirmation is disabled. */
/** Creates an account and reports whether email confirmation is still required. */
export async function signUpWithPassword(
  email: string,
  password: string,
): Promise<"signed_in" | "confirmation_required"> {
  const payload = await authRequest("/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (typeof payload.access_token !== "string" || typeof payload.refresh_token !== "string") {
    return "confirmation_required";
  }
  persist(toSession(payload));
  return "signed_in";
}

/** Requests a passwordless sign-in link for the supplied browser destination. */
export async function sendMagicLink(email: string, redirectTo: string): Promise<void> {
  await authRequest(`/otp?redirect_to=${encodeURIComponent(redirectTo)}`, {
    method: "POST",
    body: JSON.stringify({ email, create_user: false }),
  });
}

/** Builds the configured GitHub OAuth authorization URL. */
export function getGitHubOAuthUrl(redirectTo: string): string {
  const config = configuration();
  if (!config) throw new Error("Supabase Auth is not configured.");
  if (typeof window === "undefined") throw new Error("GitHub sign-in requires a browser.");
  const redirect = new URL(redirectTo, window.location.origin);
  const isWorkspacePath = redirect.pathname === "/app" || redirect.pathname.startsWith("/app/");
  if (redirect.origin !== window.location.origin || !isWorkspacePath) {
    throw new Error("GitHub sign-in redirect must remain inside this application's /app workspace.");
  }
  redirect.hash = "";
  const authorize = new URL(`${config.url}/auth/v1/authorize`);
  authorize.searchParams.set("provider", "github");
  authorize.searchParams.set("redirect_to", redirect.toString());
  return authorize.toString();
}

/** Navigates the browser to the Supabase GitHub OAuth flow. */
export function signInWithGitHub(redirectTo: string): void {
  window.location.assign(getGitHubOAuthUrl(redirectTo));
}

/** Revokes the current provider session when possible and always clears local state. */
export async function signOut(): Promise<void> {
  const session = await getSupabaseSession();
  try {
    if (session) {
      await authRequest("/logout?scope=local", {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: "{}",
      });
    }
  } finally {
    persist(null);
  }
}
