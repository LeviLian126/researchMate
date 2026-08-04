// Verifies that the signed-out workspace exposes GitHub as its only login path.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  getSupabaseSession: vi.fn().mockResolvedValue(null),
  onAuthStateChange: vi.fn().mockReturnValue(() => undefined),
  signInWithGitHub: vi.fn(),
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

describe("AuthGate GitHub login", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root.render(<AuthGate><div>Protected</div></AuthGate>));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("shows only GitHub OAuth and starts it with the workspace callback", () => {
    expect(container.querySelector("#auth-email")).toBeNull();
    expect(container.querySelector("#auth-password")).toBeNull();
    expect(container.textContent).not.toContain("Sign up");
    expect(container.textContent).not.toContain("magic link");

    const githubButton = [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Continue with GitHub");
    expect(githubButton).toBeTruthy();

    act(() => githubButton?.click());

    expect(authMocks.signInWithGitHub)
      .toHaveBeenCalledWith(`${window.location.origin}/app`);
    expect(container.textContent).toContain("Opening GitHub…");
  });

  it("keeps the page recoverable when GitHub OAuth cannot start", () => {
    authMocks.signInWithGitHub.mockImplementationOnce(() => {
      throw new Error("provider unavailable");
    });
    const githubButton = [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Continue with GitHub");

    act(() => githubButton?.click());

    expect(container.textContent).toContain("GitHub sign-in is unavailable");
    expect(githubButton?.hasAttribute("disabled")).toBe(false);
  });
});
