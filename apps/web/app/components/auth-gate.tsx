"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  type BrowserAuthSession,
  getSupabaseSession,
  isLocalDevelopment,
  isSupabaseConfigured,
  onAuthStateChange,
  sendMagicLink,
  signInWithPassword,
  signOut,
} from "../lib/supabase";
import { StateNotice } from "./state-notice";

type AuthState = "loading" | "signed_out" | "signed_in" | "misconfigured" | "error";

export function AuthGate({ children }: { children: ReactNode }) {
  const local = isLocalDevelopment();
  const [state, setState] = useState<AuthState>(local ? "signed_in" : "loading");
  const [session, setSession] = useState<BrowserAuthSession | null>(null);

  useEffect(() => {
    if (local) return;
    if (!isSupabaseConfigured()) {
      setState("misconfigured");
      return;
    }
    let active = true;
    const unsubscribe = onAuthStateChange((nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setState(nextSession ? "signed_in" : "signed_out");
    });
    void getSupabaseSession().then((nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setState(nextSession ? "signed_in" : "signed_out");
    }).catch(() => setState("error"));
    return () => {
      active = false;
      unsubscribe();
    };
  }, [local]);

  if (local) return <>{children}</>;
  if (state === "loading") {
    return <main className="auth-shell"><div className="glass-panel auth-panel" role="status"><p className="eyebrow">Secure workspace</p><h1>Restoring your session…</h1><p>Supabase is refreshing the browser session before any protected API request is sent.</p></div></main>;
  }
  if (state === "misconfigured") {
    return <main className="auth-shell"><StateNotice state={{ title: "Authentication is not configured", detail: "Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY for this deployment. The app will not fall back to a development identity.", kind: "provider" }} /></main>;
  }
  if (state === "error") {
    return <main className="auth-shell"><StateNotice state={{ title: "Session recovery failed", detail: "Supabase Auth could not restore this browser session. Reload the page or sign in again after the provider recovers.", kind: "provider" }} action={<button type="button" onClick={() => window.location.reload()}>Reload</button>} /></main>;
  }
  if (state === "signed_out") return <SignInPanel />;

  return (
    <>
      <div className="session-bar" role="status">
        <span>Signed in as <strong>{session?.user?.email ?? "verified Supabase user"}</strong></span>
        <button type="button" onClick={() => void signOut().catch(() => undefined)}>Sign out</button>
      </div>
      {children}
    </>
  );
}

function SignInPanel() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"password" | "magic" | null>(null);
  const [message, setMessage] = useState<{ title: string; detail: string; kind: string } | null>(null);

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("password");
    setMessage(null);
    try {
      await signInWithPassword(email, password);
    } catch {
      setMessage({ title: "Sign-in failed", detail: "Check the email and password, or use a magic link. No protected request was sent.", kind: "auth" });
    }
    setBusy(null);
  }

  async function submitMagicLink() {
    if (!email) {
      setMessage({ title: "Email is required", detail: "Enter the email address that should receive the one-time sign-in link.", kind: "validation" });
      return;
    }
    setBusy("magic");
    setMessage(null);
    try {
      await sendMagicLink(email, `${window.location.origin}/app`);
      setMessage({ title: "Check your email", detail: "Open the one-time link in this browser to restore the protected workspace session.", kind: "success" });
    } catch {
      setMessage({ title: "Magic link could not be sent", detail: "Retry after checking the Supabase email provider and redirect allow-list.", kind: "provider" });
    }
    setBusy(null);
  }

  return (
    <main className="auth-shell">
      <form className="glass-panel auth-panel stack" onSubmit={submitPassword}>
        <div><p className="eyebrow">ResearchMate portfolio demo</p><h1>Sign in to the workspace</h1><p>Preview and production require a verified Supabase session. Development identities are never used here.</p></div>
        {message && <StateNotice state={message} />}
        <label htmlFor="auth-email">Email</label>
        <input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="auth-password">Password</label>
        <input id="auth-password" type="password" autoComplete="current-password" minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button className="primary-button" type="submit" disabled={busy !== null}>{busy === "password" ? "Signing in…" : "Sign in with password"}</button>
        <div className="auth-divider"><span>or</span></div>
        <button type="button" onClick={() => void submitMagicLink()} disabled={busy !== null}>{busy === "magic" ? "Sending link…" : "Email a magic link"}</button>
      </form>
    </main>
  );
}
