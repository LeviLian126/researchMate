import type { ReactNode } from "react";
import { AuthGate } from "../components/auth-gate";

export default function ProtectedDeveloperLayout({ children }: { children: ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
