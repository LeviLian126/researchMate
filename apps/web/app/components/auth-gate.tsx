// Guards authenticated surfaces and owns browser sign-in and session-recovery presentation.
"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  type BrowserAuthSession,
  getSupabaseSession,
  isLocalDevelopment,
  isSupabaseConfigured,
  onAuthStateChange,
  signInWithGitHub,
  signOut,
} from "../lib/supabase";
import { isPublicDemo } from "../lib/demo";
import { StateNotice } from "./state-notice";
import { BrandLogo } from "./brand-logo";
import { warmApi } from "../lib/api";

type AuthState = "loading" | "signed_out" | "signed_in" | "misconfigured" | "error";

/** Resolves local, demo, and Supabase session states before rendering protected children. */
export function AuthGate({ children }: { children: ReactNode }) {
  const local = isLocalDevelopment();
  const publicDemo = isPublicDemo();
  const [state, setState] = useState<AuthState>(local ? "signed_in" : "loading");
  const [session, setSession] = useState<BrowserAuthSession | null>(null);

  useEffect(() => {
    void warmApi();
    if (local || publicDemo) return;
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
  }, [local, publicDemo]);

  if (local) return <>{children}</>;
  if (publicDemo) {
    return <>
      <div className="demo-mode-banner" role="status"><strong>Interactive static demo</strong><span>Sample evidence is stored only in this browser session. No login, provider call, upload, or managed workflow is running.</span></div>
      {children}
    </>;
  }
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

/** Presents the single supported GitHub authentication entry point. */
function SignInPanel() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ title: string; detail: string; kind: string } | null>(null);

  /** Starts GitHub OAuth using the current origin as the return destination. */
  function submitGitHub() {
    setBusy(true);
    setMessage(null);
    try {
      signInWithGitHub(`${window.location.origin}/app`);
    } catch {
      setMessage({ title: "GitHub sign-in is unavailable", detail: "Retry after checking the GitHub provider and production redirect configuration in Supabase.", kind: "provider" });
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="glass-panel auth-panel stack">
        <div className="auth-brand"><BrandLogo withName /></div>
        <div>
          <p className="eyebrow">Your research workspace</p>
          <h1>Welcome back</h1>
          <p>Continue your projects, conversations, sources, and quizzes with your GitHub account.</p>
        </div>
        {message && <StateNotice state={message} />}
        <button className="github-auth-button" type="button" onClick={submitGitHub} disabled={busy}>{busy ? "Opening GitHub…" : "Continue with GitHub"}</button>
      </section>
      <a className="auth-source-link" href="https://github.com/LeviLian126/researchMate">GitHub ↗</a>
    </main>
  );
}
