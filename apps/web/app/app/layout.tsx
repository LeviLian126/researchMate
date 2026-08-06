// Composes authentication and shared navigation around all product workspace routes.
import { Suspense, type ReactNode } from "react";
import { AuthGate } from "../components/auth-gate";
import { AppSidebar } from "../components/app-sidebar";

/** Provides the protected application shell and sidebar loading boundary. */
export default function ProtectedAppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <div className="flex h-[100dvh] bg-gradient-to-br from-accent via-background to-background">
        <Suspense
          fallback={
            <aside
              className="hidden h-full w-[260px] shrink-0 md:block"
              aria-label="Loading workspace navigation"
            />
          }
        >
          <AppSidebar />
        </Suspense>
        <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
      </div>
    </AuthGate>
  );
}
