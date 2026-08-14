// Project-scoped error boundary isolating failures from the rest of the workspace.
"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Keeps project-route runtime failures from surfacing outside the project surface. */
export default function ProjectError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("project_error_boundary", error.message, error.digest ?? null);
  }, [error]);

  return (
    <main
      role="alert"
      className="mx-auto max-w-3xl space-y-4 px-6 py-16"
    >
      <section className="space-y-4 rounded-2xl border border-border bg-card p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <AlertTriangle strokeWidth={1.5} className="size-6 text-destructive" />
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            This project view failed to load
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          The project surface hit an unexpected error. Retry to reload just this view.
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
            Reload page
          </Button>
        </div>
      </section>
    </main>
  );
}
