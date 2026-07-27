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
});

describe("managed browser sessions", () => {
  it("signs in, persists the normalized session, and notifies listeners", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const auth = await loadConfiguredModule();
    const listener = vi.fn();
    const unsubscribe = auth.onAuthStateChange(listener);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: "header.payload.signature",
      refresh_token: "refresh-1",
      expires_in: 3600,
      user: { email: "reader@example.test" },
    }), { status: 200 }));

    const session = await auth.signInWithPassword("reader@example.test", "secret");

    expect(session).toMatchObject({
      access_token: "header.payload.signature",
      refresh_token: "refresh-1",
      user: { email: "reader@example.test" },
    });
    expect(listener).toHaveBeenCalledWith(session);
    expect(JSON.parse(window.localStorage.getItem("researchmate_supabase_session") ?? "{}"))
      .toMatchObject({ access_token: "header.payload.signature" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://auth.example.test/auth/v1/token?grant_type=password");
    expect(new Headers(init?.headers).get("apikey")).toBe("anon-key");
    unsubscribe();
  });

  it("restores a magic-link session and removes tokens from the address", async () => {
    vi.useFakeTimers();
    const auth = await loadConfiguredModule();
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

  it("refreshes an expired stored session", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    window.localStorage.setItem("researchmate_supabase_session", JSON.stringify({
      access_token: "expired-access",
      refresh_token: "refresh-1",
      expires_at: Date.now() - 1,
      user: null,
    }));
    const auth = await loadConfiguredModule();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      access_token: "renewed-access",
      refresh_token: "refresh-2",
      expires_in: 600,
    }), { status: 200 }));

    await expect(auth.getSupabaseSession()).resolves.toMatchObject({
      access_token: "renewed-access",
      refresh_token: "refresh-2",
    });
  });

  it("clears local state even when remote sign-out fails", async () => {
    vi.useFakeTimers();
    const auth = await loadConfiguredModule();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        access_token: "access-1",
        refresh_token: "refresh-1",
        expires_in: 3600,
      }), { status: 200 }))
      .mockRejectedValueOnce(new Error("provider unavailable"));
    await auth.signInWithPassword("reader@example.test", "secret");

    await expect(auth.signOut()).rejects.toThrow("provider unavailable");
    expect(window.localStorage.getItem("researchmate_supabase_session")).toBeNull();
    await expect(auth.getSupabaseSession()).resolves.toBeNull();
  });

  it("sends passwordless sign-in requests with a safe encoded redirect", async () => {
    const auth = await loadConfiguredModule();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );

    await auth.sendMagicLink("reader@example.test", "https://app.example.test/callback?a=1");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://auth.example.test/auth/v1/otp?redirect_to=https%3A%2F%2Fapp.example.test%2Fcallback%3Fa%3D1",
    );
  });

  it("surfaces provider messages and invalid session payloads", async () => {
    const auth = await loadConfiguredModule();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ msg: "Invalid credentials" }), {
        status: 400,
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "missing-refresh" }), {
        status: 200,
      }));

    await expect(auth.signInWithPassword("reader@example.test", "bad"))
      .rejects.toThrow("Invalid credentials");
    await expect(auth.signInWithPassword("reader@example.test", "bad"))
      .rejects.toThrow("invalid session payload");
  });
});
