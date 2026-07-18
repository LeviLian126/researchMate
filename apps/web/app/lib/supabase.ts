"use client";

export interface BrowserAuthSession {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: { email?: string } | null;
}

type SessionListener = (session: BrowserAuthSession | null) => void;
const STORAGE_KEY = "researchmate_supabase_session";
const REFRESH_SKEW_MS = 60_000;
const listeners = new Set<SessionListener>();
let currentSession: BrowserAuthSession | null | undefined;
let refreshPromise: Promise<BrowserAuthSession | null> | null = null;
let refreshTimer: number | null = null;

export function isLocalDevelopment(): boolean {
  const configured = process.env.NEXT_PUBLIC_APP_ENV;
  return process.env.NODE_ENV === "development" && (!configured || configured === "local");
}

function configuration(): { url: string; anonKey: string } | null {
  if (isLocalDevelopment()) return null;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return url && anonKey ? { url, anonKey } : null;
}

export function isSupabaseConfigured(): boolean {
  return configuration() !== null;
}

function notify(session: BrowserAuthSession | null) {
  for (const listener of listeners) listener(session);
}

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

function emailFromAccessToken(token: string): string | undefined {
  try {
    const segment = token.split(".")[1];
    const normalized = segment.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
    const decoded = JSON.parse(atob(padded)) as { email?: unknown };
    return typeof decoded.email === "string" ? decoded.email : undefined;
  } catch {
    return undefined;
  }
}

function toSession(payload: Record<string, unknown>): BrowserAuthSession {
  if (typeof payload.access_token !== "string" || typeof payload.refresh_token !== "string") {
    throw new Error("Supabase Auth returned an invalid session payload.");
  }
  const expiresIn = typeof payload.expires_in === "number" ? payload.expires_in : 3600;
  const user = payload.user && typeof payload.user === "object" ? payload.user as { email?: string } : null;
  return {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: Date.now() + expiresIn * 1000,
    user: user?.email ? { email: user.email } : { email: emailFromAccessToken(payload.access_token) },
  };
}

function restoreMagicLinkSession(): BrowserAuthSession | null {
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
    user: { email: emailFromAccessToken(accessToken) },
  };
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return session;
}

function restoreStoredSession(): BrowserAuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<BrowserAuthSession>;
    if (typeof value.access_token !== "string" || typeof value.refresh_token !== "string" || typeof value.expires_at !== "number") return null;
    return { access_token: value.access_token, refresh_token: value.refresh_token, expires_at: value.expires_at, user: value.user ?? null };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

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

export async function getSupabaseSession(): Promise<BrowserAuthSession | null> {
  if (!configuration()) return null;
  if (currentSession === undefined) {
    const restored = restoreMagicLinkSession() ?? restoreStoredSession();
    currentSession = restored;
    if (restored) persist(restored);
  }
  if (!currentSession) return null;
  if (currentSession.expires_at <= Date.now() + REFRESH_SKEW_MS) return refreshSession(currentSession.refresh_token);
  return currentSession;
}

export function onAuthStateChange(listener: SessionListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function signInWithPassword(email: string, password: string): Promise<BrowserAuthSession> {
  const payload = await authRequest("/token?grant_type=password", { method: "POST", body: JSON.stringify({ email, password }) });
  const session = toSession(payload);
  persist(session);
  return session;
}

export async function sendMagicLink(email: string, redirectTo: string): Promise<void> {
  await authRequest(`/otp?redirect_to=${encodeURIComponent(redirectTo)}`, {
    method: "POST",
    body: JSON.stringify({ email, create_user: false }),
  });
}

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
