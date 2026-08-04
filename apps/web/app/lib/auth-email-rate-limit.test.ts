// Verifies the resend cooldown at its start, boundary, and expired states.
import { describe, expect, it } from "vitest";
import { AUTH_EMAIL_COOLDOWN_MS, nextEmailCooldown, remainingEmailCooldown } from "./auth-email-rate-limit";

describe("authentication email cooldown", () => {
  it("allows one resend only after the provider-aligned 60-second window", () => {
    const now = Date.parse("2026-08-04T00:00:00Z");
    const deadline = nextEmailCooldown(now);

    expect(deadline).toBe(now + AUTH_EMAIL_COOLDOWN_MS);
    expect(remainingEmailCooldown(deadline, now)).toBe(60);
    expect(remainingEmailCooldown(deadline, deadline - 1)).toBe(1);
    expect(remainingEmailCooldown(deadline, deadline)).toBe(0);
  });
});
