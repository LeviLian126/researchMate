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
  signInWithGitHub,
  signInWithPassword,
  signUpWithPassword,
  signOut,
} from "../lib/supabase";
import { isPublicDemo } from "../lib/demo";
import { StateNotice } from "./state-notice";

type AuthState = "loading" | "signed_out" | "signed_in" | "misconfigured" | "error";

export function AuthGate({ children }: { children: ReactNode }) {
  const local = isLocalDevelopment();
  const publicDemo = isPublicDemo();
  const [state, setState] = useState<AuthState>(local ? "signed_in" : "loading");
  const [session, setSession] = useState<BrowserAuthSession | null>(null);

  useEffect(() => {
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

function SignInPanel() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"password" | "magic" | "github" | null>(null);
  const [message, setMessage] = useState<{ title: string; detail: string; kind: string } | null>(null);

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("password");
    setMessage(null);
    try {
      if (mode === "signin") {
        await signInWithPassword(email, password);
      } else {
        const result = await signUpWithPassword(email, password);
        if (result === "confirmation_required") {
          setMessage({
            title: "Confirm your email",
            detail: "Open the confirmation link from Supabase, then return here to sign in.",
            kind: "success",
          });
        }
      }
    } catch {
      setMessage({
        title: mode === "signin" ? "Sign-in failed" : "Account could not be created",
        detail: mode === "signin"
          ? "Check the email and password, or use a magic link. No protected request was sent."
          : "Check the email, use at least six password characters, or sign in if the account already exists.",
        kind: "auth",
      });
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

  function submitGitHub() {
    setBusy("github");
    setMessage(null);
    try {
      signInWithGitHub(`${window.location.origin}/app`);
    } catch {
      setMessage({ title: "GitHub sign-in is unavailable", detail: "Retry after checking the GitHub provider and production redirect configuration in Supabase.", kind: "provider" });
      setBusy(null);
    }
  }

  return (
    <main className="auth-shell">
      <form className="glass-panel auth-panel stack" onSubmit={submitPassword}>
        <div className="auth-brand"><span aria-hidden="true">R</span><strong>ResearchMate</strong></div>
        <div>
          <p className="eyebrow">Your research workspace</p>
          <h1>{mode === "signin" ? "Welcome back" : "Create your account"}</h1>
          <p>{mode === "signin" ? "Continue your projects, conversations, sources, and quizzes." : "Create one secure workspace for your research projects and source-backed conversations."}</p>
        </div>
        <div className="auth-mode-switch" role="tablist" aria-label="Authentication mode">
          <button type="button" role="tab" aria-selected={mode === "signin"} onClick={() => { setMode("signin"); setMessage(null); }}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === "signup"} onClick={() => { setMode("signup"); setMessage(null); }}>Sign up</button>
        </div>
        {message && <StateNotice state={message} />}
        <button className="github-auth-button" type="button" onClick={submitGitHub} disabled={busy !== null}>{busy === "github" ? "Opening GitHub…" : "Continue with GitHub"}</button>
        <div className="auth-divider"><span>or use email</span></div>
        <label htmlFor="auth-email">Email</label>
        <input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="auth-password">Password</label>
        <input id="auth-password" type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button className="primary-button" type="submit" disabled={busy !== null}>{busy === "password" ? (mode === "signin" ? "Signing in…" : "Creating account…") : (mode === "signin" ? "Sign in" : "Create account")}</button>
        {mode === "signin" && <button type="button" onClick={() => void submitMagicLink()} disabled={busy !== null}>{busy === "magic" ? "Sending link…" : "Email a magic link"}</button>}
      </form>
      <a className="auth-source-link" href="https://github.com/LeviLian126/researchMate">GitHub ↗</a>
    </main>
  );
}
