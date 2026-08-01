// Applies the shared authentication boundary to every developer-only route.
import type { ReactNode } from "react";
import { AuthGate } from "../components/auth-gate";

/** Wraps developer pages in session verification before route content renders. */
export default function ProtectedDeveloperLayout({ children }: { children: ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
