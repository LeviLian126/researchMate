import { Suspense, type ReactNode } from "react";
import { AuthGate } from "../components/auth-gate";
import { AppSidebar } from "../components/app-sidebar";

export default function ProtectedAppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <div className="authenticated-shell">
        <Suspense fallback={<aside className="app-sidebar" aria-label="Loading workspace navigation" />}>
          <AppSidebar />
        </Suspense>
        <div className="authenticated-content">{children}</div>
      </div>
    </AuthGate>
  );
}
