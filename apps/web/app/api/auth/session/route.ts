// Sets or clears the Supabase session inside an HttpOnly cookie so that
// client-side JavaScript cannot read the access or refresh tokens.
import { type NextRequest, NextResponse } from "next/server";

// Mirrors BrowserAuthSession in app/lib/supabase.ts without importing a
// client component from a server route.
interface SessionCookiePayload {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: { email?: string; role?: string } | null;
}

const COOKIE_NAME = "researchmate_supabase_session";
// 30 days mirrors the previous localStorage retention ceiling.
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

/** Validates the inbound JSON body and normalizes it into the cookie payload. */
function normalizePayload(value: unknown): SessionCookiePayload | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (
    typeof record.access_token !== "string" ||
    typeof record.refresh_token !== "string" ||
    typeof record.expires_at !== "number"
  ) {
    return null;
  }
  const user = record.user && typeof record.user === "object" ? record.user as SessionCookiePayload["user"] : null;
  return {
    access_token: record.access_token,
    refresh_token: record.refresh_token,
    expires_at: record.expires_at,
    user,
  };
}

/** Persists or clears the session cookie on the response. */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const body = await request.json().catch(() => null);
  // An explicit `null` payload clears the cookie on sign-out.
  if (body === null) {
    const cleared = NextResponse.json({ ok: true });
    cleared.cookies.delete(COOKIE_NAME);
    return cleared;
  }
  const payload = normalizePayload(body);
  if (!payload) {
    return NextResponse.json({ error: "invalid_session_payload" }, { status: 400 });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: COOKIE_NAME,
    value: JSON.stringify(payload),
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  return response;
}
