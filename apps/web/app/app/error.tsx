// Top-level error boundary for the authenticated application surface.
"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Surfaces an unexpected runtime failure with a deterministic recovery path. */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Only logging path; no telemetry call that could itself throw at the edge.
    console.error("app_error_boundary", error.message, error.digest ?? null);
  }, [error]);

  return (
    <main
      role="alert"
      className="grid min-h-[100dvh] place-items-center bg-background p-6"
    >
      <section className="w-full max-w-md space-y-4 rounded-2xl border border-border bg-card p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <AlertTriangle strokeWidth={1.5} className="size-6 text-destructive" />
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Something went wrong
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          The workspace hit an unexpected error. Try the action again. If it keeps
          failing, reload the page.
        </p>
        {error.digest && (
          <p className="text-xs text-muted-foreground">
            Reference: {error.digest}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={reset}>
            Try again
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => window.location.reload()}
          >
            Reload
          </Button>
        </div>
      </section>
    </main>
  );
}
