// Verifies browser session restoration, Supabase request boundaries, and sign-out cleanup.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const configuredEnvironment = {
  NODE_ENV: "production",
  NEXT_PUBLIC_APP_ENV: "production",
  NEXT_PUBLIC_DEMO_MODE: "false",
  NEXT_PUBLIC_SUPABASE_URL: "https://auth.example.test/",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon-key",
};

async function loadConfiguredModule() {
  for (const [name, value] of Object.entries(configuredEnvironment)) vi.stubEnv(name, value);
  vi.resetModules();
  return import("./supabase");
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("Supabase configuration", () => {
  it("disables managed authentication in local development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("NEXT_PUBLIC_APP_ENV", "local");
    vi.resetModules();
    const auth = await import("./supabase");

    expect(auth.isLocalDevelopment()).toBe(true);
    expect(auth.isSupabaseConfigured()).toBe(false);
    await expect(auth.getSupabaseSession()).resolves.toBeNull();
  });

  it("requires both the Supabase URL and anonymous key", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://auth.example.test");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    vi.resetModules();
    const auth = await import("./supabase");
    expect(auth.isSupabaseConfigured()).toBe(false);
  });

  it("rejects a non-HTTPS managed authentication endpoint", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_APP_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://auth.example.test");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon-key");
    vi.resetModules();
    const auth = await import("./supabase");

    expect(auth.isSupabaseConfigured()).toBe(false);
  });
});

describe("managed browser sessions", () => {
  it("restores a magic-link or OAuth session and removes tokens from the address", async () => {
    vi.useFakeTimers();
    const auth = await loadConfiguredModule();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    window.history.replaceState(
      null,
      "",
      "/callback#access_token=access-1&refresh_token=refresh-1&expires_in=120",
    );

    await expect(auth.getSupabaseSession()).resolves.toMatchObject({
      access_token: "access-1",
      refresh_token: "refresh-1",
    });
    expect(window.location.hash).toBe("");
  });

  it("builds a GitHub authorization URL with a same-origin app callback", async () => {
    const auth = await loadConfiguredModule();
    window.history.replaceState(null, "", "/app");

    const callback = `${window.location.origin}/app`;
    const authorize = new URL(auth.getGitHubOAuthUrl(callback));

    expect(authorize.origin).toBe("https://auth.example.test");
    expect(authorize.pathname).toBe("/auth/v1/authorize");
    expect(authorize.searchParams.get("provider")).toBe("github");
    expect(authorize.searchParams.get("redirect_to")).toBe(callback);
  });

  it("rejects cross-origin and non-workspace GitHub callbacks", async () => {
    const auth = await loadConfiguredModule();

    expect(() => auth.getGitHubOAuthUrl("https://attacker.example/app"))
      .toThrow("redirect must remain inside");
    expect(() => auth.getGitHubOAuthUrl(`${window.location.origin}/application`))
      .toThrow("redirect must remain inside");
  });

  it("refreshes an expired stored session", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const auth = await loadConfiguredModule();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/auth/session/get") {
        return new Response(JSON.stringify({
          session: {
            access_token: "expired-access",
            refresh_token: "refresh-1",
            expires_at: Date.now() - 1,
            user: null,
          },
        }), { status: 200 });
      }
      if (url === "/api/auth/session") {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return new Response(JSON.stringify({
        access_token: "renewed-access",
        refresh_token: "refresh-2",
        expires_in: 600,
      }), { status: 200 });
    });

    await expect(auth.getSupabaseSession()).resolves.toMatchObject({
      access_token: "renewed-access",
      refresh_token: "refresh-2",
    });
    // The expired stored session must have triggered the refresh path.
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/token?grant_type=refresh_token")))
      .toBe(true);
  });

  it("clears local state even when remote sign-out fails", async () => {
    vi.useFakeTimers();
    const auth = await loadConfiguredModule();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/auth/session" || url === "/api/auth/session/get") {
        // Cookie route always succeeds; the provider outage must not block local cleanup.
        return url === "/api/auth/session"
          ? new Response(JSON.stringify({ ok: true }), { status: 200 })
          : new Response(JSON.stringify({ session: null }), { status: 200 });
      }
      // Simulate the Supabase logout provider outage.
      throw new Error("provider unavailable");
    });
    // Establish a session via the GitHub OAuth redirect-hash path, mirroring the only
    // real auth entrypoint. The provider outage applies to the logout call below.
    window.history.replaceState(
      null,
      "",
      "/callback#access_token=access-1&refresh_token=refresh-1&expires_in=3600",
    );
    await auth.getSupabaseSession();

    await expect(auth.signOut()).rejects.toThrow("provider unavailable");
    // SEC-3: cleanup must hit the cookie route with a null body to delete it.
    const clearCall = [...fetchMock.mock.calls]
      .reverse()
      .find(([url, init]) => url === "/api/auth/session" && init?.method === "POST");
    expect(clearCall).toBeDefined();
    expect(String(clearCall?.[1]?.body)).toBe("null");
    await expect(auth.getSupabaseSession()).resolves.toBeNull();
  });
});
