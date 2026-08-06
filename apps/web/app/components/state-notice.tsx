// Presents consistent, accessible status and recovery notices across frontend features.
import type { ReactNode } from "react";

export interface NoticeState {
  title: string;
  detail: string;
  kind?: string;
}

/** Renders a categorized notice with an optional recovery action. */
export function StateNotice({ state, action }: { state: NoticeState; action?: ReactNode }) {
  return (
    <div
      className={`state-notice state-notice--${state.kind ?? "info"} flex items-start justify-between gap-3 rounded-xl border border-white/30 bg-white/70 p-4 shadow-sm backdrop-blur-sm`}
      role={state.kind === "error" || state.kind === "provider" ? "alert" : "status"}
    >
      <div className="min-w-0 flex-1">
        <strong className="text-sm font-semibold text-foreground">{state.title}</strong>
        <p className="mt-0.5 text-sm text-muted-foreground">{state.detail}</p>
      </div>
      {action}
    </div>
  );
}
