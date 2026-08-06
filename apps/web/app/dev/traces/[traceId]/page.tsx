// Presents a sanitized developer trace obtained through the role-protected API.
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { apiFetch, DeveloperTrace } from "../../../lib/api";
import { Button } from "@/components/ui/button";

const jsonBlock = "max-h-[360px] overflow-auto rounded-lg border border-border/60 bg-secondary/30 p-4 font-mono text-sm";
const glassPanel = "rounded-2xl border border-white/30 bg-white/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-xl";

/** Loads and displays the requested execution trace or a safe access failure. */
export default function TracePage() {
  const params = useParams<{ traceId: string }>();
  const traceId = params.traceId;
  const [trace, setTrace] = useState<DeveloperTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    /** Loads the canonical trace whenever its route identifier changes. */
    async function loadTrace() {
      try {
        setTrace(await apiFetch<DeveloperTrace>(`/dev/traces/${traceId}`));
      } catch (err) {
        setError(err instanceof Error ? err.message : "The trace does not exist or this identity cannot access it.");
      }
    }
    void loadTrace();
  }, [traceId]);

  return (
    <main className="min-h-[100dvh] bg-gradient-to-br from-accent via-background to-background px-6 py-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className={glassPanel}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Developer Trace</p>
              <h1 className="mt-1 text-xl font-bold tracking-tight text-foreground">Sanitized execution trace</h1>
              <p className="mt-2 max-w-xl text-sm text-muted-foreground">
                A regular user cannot access this route. API keys, OAuth tokens, signed URLs, and raw private payloads are excluded.
              </p>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/app">
                <ArrowLeft strokeWidth={1.5} className="size-4" />
                Return to projects
              </Link>
            </Button>
          </div>
        </header>

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive" role="alert">
            {error}
          </div>
        )}

        {trace && (
          <section className="grid gap-6 md:grid-cols-2">
            <article className={glassPanel}>
              <div className="space-y-4">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Plan</h2>
                <pre className={jsonBlock}>{JSON.stringify(trace.execution_plan, null, 2)}</pre>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Validation</h2>
                <pre className={jsonBlock}>{JSON.stringify(trace.validation_result, null, 2)}</pre>
              </div>
            </article>
            <article className={glassPanel}>
              <div className="space-y-4">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Retrieved chunks</h2>
                <pre className={jsonBlock}>{JSON.stringify(trace.retrieved_chunks, null, 2)}</pre>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Tool calls</h2>
                <pre className={jsonBlock}>{JSON.stringify(trace.tool_calls, null, 2)}</pre>
              </div>
            </article>
          </section>
        )}
      </div>
    </main>
  );
}
