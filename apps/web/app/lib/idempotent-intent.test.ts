// Verifies stable retry keys, intent rotation, and success-only cleanup semantics.
import { describe, expect, it, vi } from "vitest";
import { clearCompletedIntent, resolveIntentKey } from "./idempotent-intent";

describe("idempotent user intents", () => {
  it("reuses the same key for an unchanged failed request", () => {
    const createKey = vi.fn(() => "ask-stable-key");
    const first = resolveIntentKey(null, "ask", "same-request", createKey);
    const retry = resolveIntentKey(first, "ask", "same-request", createKey);

    expect(retry).toBe(first);
    expect(retry.key).toBe("ask-stable-key");
    expect(createKey).toHaveBeenCalledOnce();
  });

  it("rotates the key when the user intent changes", () => {
    const createKey = vi.fn()
      .mockReturnValueOnce("quiz-first-key")
      .mockReturnValueOnce("quiz-second-key");
    const first = resolveIntentKey(null, "quiz", "first-topic", createKey);
    const changed = resolveIntentKey(first, "quiz", "second-topic", createKey);

    expect(changed.key).toBe("quiz-second-key");
    expect(changed.fingerprint).toBe("second-topic");
  });

  it("clears only the key acknowledged by a successful response", () => {
    const current = { fingerprint: "request", key: "ask-current-key" };

    expect(clearCompletedIntent(current, "stale-key")).toBe(current);
    expect(clearCompletedIntent(current, "ask-current-key")).toBeNull();
  });
});
