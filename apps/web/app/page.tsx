// Presents authentication as the product entry point and redirects restored sessions.
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AuthGate } from "./components/auth-gate";

/** Sends an already authenticated visitor directly into the project workspace. */
function AuthenticatedRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/app");
  }, [router]);
  return <main className="auth-shell"><p role="status">Opening your workspace…</p></main>;
}

/** Uses the same verified auth boundary as the protected application. */
export default function HomePage() {
  return <AuthGate><AuthenticatedRedirect /></AuthGate>;
}
