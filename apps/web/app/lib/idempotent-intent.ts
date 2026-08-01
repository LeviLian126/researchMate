// Tracks one retryable user intent so failed HTTP attempts reuse their idempotency key.
import { idempotencyKey } from "./api";

export interface IntentKeyState {
  fingerprint: string;
  key: string;
}

/** Returns the existing key for an unchanged intent or creates one for a new intent. */
export function resolveIntentKey(
  current: IntentKeyState | null,
  prefix: string,
  fingerprint: string,
  createKey: (prefix: string) => string = idempotencyKey,
): IntentKeyState {
  if (current?.fingerprint === fingerprint) return current;
  return { fingerprint, key: createKey(prefix) };
}

/** Clears only the intent whose successful request used the supplied key. */
export function clearCompletedIntent(
  current: IntentKeyState | null,
  completedKey: string,
): IntentKeyState | null {
  return current?.key === completedKey ? null : current;
}
