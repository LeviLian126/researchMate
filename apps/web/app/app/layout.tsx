import type { ReactNode } from "react";
import { AuthGate } from "../components/auth-gate";

export default function ProtectedAppLayout({ children }: { children: ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
