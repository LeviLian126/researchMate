import type { ReactNode } from "react";

export interface NoticeState {
  title: string;
  detail: string;
  kind?: string;
}

export function StateNotice({ state, action }: { state: NoticeState; action?: ReactNode }) {
  return (
    <div className={`state-notice state-notice--${state.kind ?? "info"}`} role={state.kind === "error" || state.kind === "provider" ? "alert" : "status"}>
      <div>
        <strong>{state.title}</strong>
        <p>{state.detail}</p>
      </div>
      {action}
    </div>
  );
}
