// Guards authenticated surfaces and owns browser sign-in and session-recovery presentation.
"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  type BrowserAuthSession,
  SupabaseAuthError,
  getSupabaseSession,
  isLocalDevelopment,
  isSupabaseConfigured,
  onAuthStateChange,
  resendSignupConfirmation,
  sendMagicLink,
  signInWithGitHub,
  signInWithPassword,
  signUpWithPassword,
  signOut,
} from "../lib/supabase";
import { nextEmailCooldown, remainingEmailCooldown } from "../lib/auth-email-rate-limit";
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

/** Presents password, magic-link, and GitHub authentication entry points. */
function SignInPanel() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"password" | "magic" | "resend" | "github" | null>(null);
  const [message, setMessage] = useState<{ title: string; detail: string; kind: string } | null>(null);
  const [confirmationEmail, setConfirmationEmail] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [clock, setClock] = useState(() => Date.now());
  const cooldownSeconds = remainingEmailCooldown(cooldownUntil, clock);

  useEffect(() => {
    if (!confirmationEmail || cooldownSeconds === 0) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [confirmationEmail, cooldownSeconds]);

  /** Submits the current password sign-in or sign-up mode with recoverable feedback. */
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
          setConfirmationEmail(email.trim().toLowerCase());
          const deadline = nextEmailCooldown();
          setCooldownUntil(deadline);
          setClock(Date.now());
          setMessage({
            title: "Check your email",
            detail: "If this address is eligible for confirmation, open the Supabase link and then return here to sign in. Check spam before resending.",
            kind: "success",
          });
        }
      }
    } catch (error) {
      const providerMessage = error instanceof Error ? error.message : "";
      const rateLimited = error instanceof SupabaseAuthError && error.status === 429;
      setMessage({
        title: mode === "signin" ? "Sign-in failed" : "Account could not be created",
        detail: mode === "signin"
          ? "Check the email and password, or use a magic link. No protected request was sent."
          : rateLimited
            ? "Supabase is rate-limiting confirmation emails. Wait at least 60 seconds before retrying."
          : providerMessage.toLowerCase().includes("authorized")
            ? "This project is using Supabase's restricted default email service. Configure custom SMTP before accepting public sign-ups."
            : "The request could not be completed. Use at least eight password characters, wait before retrying, or sign in if the account already exists.",
        kind: "auth",
      });
    }
    setBusy(null);
  }

  /** Requests a passwordless email link without losing the current form state. */
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

  /** Resends a pending confirmation while mirroring Supabase's 60-second user limit. */
  async function resendConfirmation() {
    if (!confirmationEmail || remainingEmailCooldown(cooldownUntil) > 0) return;
    setBusy("resend");
    setMessage(null);
    try {
      await resendSignupConfirmation(confirmationEmail, `${window.location.origin}/app`);
      const deadline = nextEmailCooldown();
      setCooldownUntil(deadline);
      setClock(Date.now());
      setMessage({ title: "Confirmation resent", detail: "Check the inbox and spam folder. Another resend is available in 60 seconds.", kind: "success" });
    } catch (error) {
      const deadline = nextEmailCooldown();
      setCooldownUntil(deadline);
      setClock(Date.now());
      const rateLimited = error instanceof SupabaseAuthError && error.status === 429;
      setMessage({
        title: "Confirmation could not be resent",
        detail: rateLimited
          ? "Supabase allows one confirmation request per address every 60 seconds. Wait for the countdown before retrying."
          : "Supabase rejected the email request. Wait 60 seconds, then retry after the SMTP configuration is healthy.",
        kind: "provider",
      });
    }
    setBusy(null);
  }

  /** Starts GitHub OAuth using the current origin as the return destination. */
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
        <div className="auth-brand"><BrandLogo withName /></div>
        <div>
          <p className="eyebrow">Your research workspace</p>
          <h1>{mode === "signin" ? "Welcome back" : "Create your account"}</h1>
          <p>{mode === "signin" ? "Continue your projects, conversations, sources, and quizzes." : "Create one secure workspace for your research projects and source-backed conversations."}</p>
        </div>
        <div className="auth-mode-switch" role="tablist" aria-label="Authentication mode">
          <button type="button" role="tab" aria-selected={mode === "signin"} onClick={() => { setMode("signin"); setMessage(null); setConfirmationEmail(null); }}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === "signup"} onClick={() => { setMode("signup"); setMessage(null); setConfirmationEmail(null); }}>Sign up</button>
        </div>
        {message && <StateNotice state={message} action={confirmationEmail ? <button type="button" onClick={() => void resendConfirmation()} disabled={busy !== null || cooldownSeconds > 0}>{busy === "resend" ? "Resending…" : cooldownSeconds > 0 ? `Resend in ${cooldownSeconds}s` : "Resend confirmation"}</button> : undefined} />}
        <button className="github-auth-button" type="button" onClick={submitGitHub} disabled={busy !== null}>{busy === "github" ? "Opening GitHub…" : "Continue with GitHub"}</button>
        <div className="auth-divider"><span>or use email</span></div>
        <label htmlFor="auth-email">Email</label>
        <input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="auth-password">Password</label>
        <input id="auth-password" type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} minLength={mode === "signup" ? 8 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button className="primary-button" type="submit" disabled={busy !== null}>{busy === "password" ? (mode === "signin" ? "Signing in…" : "Creating account…") : (mode === "signin" ? "Sign in" : "Create account")}</button>
        {mode === "signin" && <button type="button" onClick={() => void submitMagicLink()} disabled={busy !== null}>{busy === "magic" ? "Sending link…" : "Email a magic link"}</button>}
      </form>
      <a className="auth-source-link" href="https://github.com/LeviLian126/researchMate">GitHub ↗</a>
    </main>
  );
}
