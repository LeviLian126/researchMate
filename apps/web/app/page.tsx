// Presents authentication as the product entry point and redirects restored sessions.
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { AuthGate } from "./components/auth-gate";

/** Sends an already authenticated visitor directly into the project workspace. */
function AuthenticatedRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/app");
  }, [router]);
  return (
    <main className="auth-shell grid min-h-[100dvh] place-items-center bg-gradient-to-br from-accent via-background to-background p-6">
      <div
        className="flex items-center gap-3 rounded-2xl border border-white/30 bg-white/70 px-6 py-4 shadow-xl shadow-primary/5 backdrop-blur-xl"
        role="status"
      >
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Opening your workspace…</p>
      </div>
    </main>
  );
}

/** Uses the same verified auth boundary as the protected application. */
export default function HomePage() {
  return (
    <AuthGate>
      <AuthenticatedRedirect />
    </AuthGate>
  );
}
