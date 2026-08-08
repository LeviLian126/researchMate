// Reads the Supabase session from the HttpOnly cookie and returns it to the
// browser so supabase.ts can restore an in-memory session without localStorage.
import { type NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "researchmate_supabase_session";

interface SessionCookiePayload {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: { email?: string; role?: string } | null;
}

/** Returns the parsed cookie or null when absent or structurally invalid. */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const cookieValue = request.cookies.get(COOKIE_NAME)?.value;
  if (!cookieValue) return NextResponse.json({ session: null });
  try {
    const parsed = JSON.parse(cookieValue) as Partial<SessionCookiePayload>;
    if (
      typeof parsed.access_token !== "string" ||
      typeof parsed.refresh_token !== "string" ||
      typeof parsed.expires_at !== "number"
    ) {
      return NextResponse.json({ session: null });
    }
    return NextResponse.json({ session: parsed });
  } catch {
    return NextResponse.json({ session: null });
  }
}
