// Exercises the visible signup, confirmation, cooldown, and resend sequence as one module flow.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  getSupabaseSession: vi.fn().mockResolvedValue(null),
  onAuthStateChange: vi.fn().mockReturnValue(() => undefined),
  resendSignupConfirmation: vi.fn().mockResolvedValue(undefined),
  sendMagicLink: vi.fn().mockResolvedValue(undefined),
  signInWithGitHub: vi.fn(),
  signInWithPassword: vi.fn().mockResolvedValue(undefined),
  signUpWithPassword: vi.fn().mockResolvedValue("confirmation_required"),
  signOut: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../lib/supabase", () => ({
  ...authMocks,
  isLocalDevelopment: () => false,
  isSupabaseConfigured: () => true,
}));
vi.mock("../lib/demo", () => ({ isPublicDemo: () => false }));
vi.mock("../lib/api", () => ({ warmApi: vi.fn().mockResolvedValue(undefined) }));
vi.mock("./brand-logo", () => ({ BrandLogo: () => <span>ResearchMate</span> }));

import { AuthGate } from "./auth-gate";

function setInput(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("AuthGate email confirmation flow", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-04T00:00:00Z"));
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root.render(<AuthGate><div>Protected</div></AuthGate>));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("runs signup through confirmation and permits resend only after 60 seconds", async () => {
    const signupTab = [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Sign up");
    expect(signupTab).toBeTruthy();
    act(() => signupTab?.click());

    const email = container.querySelector<HTMLInputElement>("#auth-email");
    const password = container.querySelector<HTMLInputElement>("#auth-password");
    expect(password?.minLength).toBe(8);
    act(() => {
      setInput(email!, "New@Example.TEST");
      setInput(password!, "strong-password");
    });

    await act(async () => {
      container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(authMocks.signUpWithPassword).toHaveBeenCalledWith("New@Example.TEST", "strong-password");
    expect(container.textContent).toContain("If this address is eligible for confirmation");
    expect(container.textContent).toContain("Resend in 60s");

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    const resend = [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Resend confirmation");
    expect(resend).toBeTruthy();
    await act(async () => resend?.click());

    expect(authMocks.resendSignupConfirmation)
      .toHaveBeenCalledWith("new@example.test", `${window.location.origin}/app`);
    expect(container.textContent).toContain("Confirmation resent");
  });
});
