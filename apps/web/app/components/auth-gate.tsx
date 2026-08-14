// Guards authenticated surfaces and owns browser sign-in and session-recovery presentation.
"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { GitBranch, Loader2 } from "lucide-react";
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
import { Button } from "@/components/ui/button";

type AuthState = "loading" | "signed_out" | "signed_in" | "misconfigured" | "error";

/** Shared glass auth surface sitting on the cobalt gradient background. */
function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-[100dvh] place-items-center bg-gradient-to-br from-accent via-background to-background p-6">
      {children}
    </main>
  );
}

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
    void getSupabaseSession()
      .then((nextSession) => {
        if (!active) return;
        setSession(nextSession);
        setState(nextSession ? "signed_in" : "signed_out");
      })
      .catch(() => setState("error"));
    return () => {
      active = false;
      unsubscribe();
    };
  }, [local, publicDemo]);

  if (local) return <>{children}</>;

  if (publicDemo) {
    return (
      <>
        <div
          className="flex flex-col gap-1 rounded-xl border border-white/30 bg-white/70 p-4 text-sm shadow-sm backdrop-blur-sm"
          role="status"
        >
          <strong className="font-semibold text-foreground">Interactive static demo</strong>
          <span className="text-muted-foreground">
            Sample evidence is stored only in this browser session. No login, provider call, upload, or managed workflow is running.
          </span>
        </div>
        {children}
      </>
    );
  }

  if (state === "loading") {
    return (
      <AuthShell>
        <div
          className="w-full max-w-md rounded-2xl border border-white/30 bg-white/70 p-8 shadow-xl shadow-primary/5 backdrop-blur-xl"
          role="status"
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Secure workspace
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            Restoring your session…
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Supabase is refreshing the browser session before any protected API request is sent.
          </p>
        </div>
      </AuthShell>
    );
  }

  if (state === "misconfigured") {
    return (
      <AuthShell>
        <div className="w-full max-w-md">
          <StateNotice
            state={{
              title: "Authentication is not configured",
              detail:
                "Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY for this deployment. The app will not fall back to a development identity.",
              kind: "provider",
            }}
          />
        </div>
      </AuthShell>
    );
  }

  if (state === "error") {
    return (
      <AuthShell>
        <div className="w-full max-w-md">
          <StateNotice
            state={{
              title: "Session recovery failed",
              detail:
                "Supabase Auth could not restore this browser session. Reload the page or sign in again after the provider recovers.",
              kind: "provider",
            }}
            action={
              <Button
                type="button"
                variant="outline"
                className="rounded-lg"
                onClick={() => window.location.reload()}
              >
                Reload
              </Button>
            }
          />
        </div>
      </AuthShell>
    );
  }

  if (state === "signed_out") return <SignInPanel />;

  return (
    <>
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-white/30 bg-white/70 px-4 py-2.5 text-sm shadow-sm backdrop-blur-sm"
        role="status"
      >
        <span className="min-w-0 truncate text-muted-foreground">
          Signed in as{" "}
          <strong className="font-medium text-foreground">
            {session?.user?.email ?? "verified Supabase user"}
          </strong>
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="shrink-0 rounded-lg"
          onClick={() => void signOut().catch(() => undefined)}
        >
          Sign out
        </Button>
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
      setMessage({
        title: "GitHub sign-in is unavailable",
        detail:
          "Retry after checking the GitHub provider and production redirect configuration in Supabase.",
        kind: "provider",
      });
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <div className="flex w-full max-w-md flex-col items-center gap-6">
        <section className="flex w-full flex-col gap-6 rounded-2xl border border-white/30 bg-white/70 p-8 shadow-xl shadow-primary/5 backdrop-blur-xl">
          <div>
            <BrandLogo withName />
          </div>
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Your research workspace
            </p>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Welcome back</h1>
            <p className="text-sm text-muted-foreground">
              Continue your projects, conversations, sources, and quizzes with your GitHub account.
            </p>
          </div>
          {message && <StateNotice state={message} />}
          <Button
            type="button"
            size="lg"
            className="w-full rounded-lg"
            onClick={submitGitHub}
            disabled={busy}
          >
            {busy ? (
              <Loader2 strokeWidth={1.5} className="animate-spin" />
            ) : (
              <GitBranch strokeWidth={1.5} />
            )}
            {busy ? "Opening GitHub…" : "Continue with GitHub"}
          </Button>
        </section>
        <a
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          href="https://github.com/LeviLian126/researchMate"
        >
          GitHub ↗
        </a>
      </div>
    </AuthShell>
  );
}
