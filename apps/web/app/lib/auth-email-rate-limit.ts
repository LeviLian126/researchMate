// Defines the browser-side guard that mirrors Supabase's per-user email cooldown.
export const AUTH_EMAIL_COOLDOWN_MS = 60_000;

/** Returns the whole seconds remaining before another email request is allowed. */
export function remainingEmailCooldown(cooldownUntil: number, now = Date.now()): number {
  return Math.max(0, Math.ceil((cooldownUntil - now) / 1000));
}

/** Starts a new cooldown window after a provider-accepted email request. */
export function nextEmailCooldown(now = Date.now()): number {
  return now + AUTH_EMAIL_COOLDOWN_MS;
}
