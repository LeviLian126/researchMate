// Configures Next.js security headers and local-development connection allowances.
import type { NextConfig } from "next";
import { buildStaticCsp } from "./app/lib/csp-origins";

// Resolves the backend origin for same-origin rewrites. Corporate or ISP
// proxies sometimes intercept direct browser requests to *.onrender.com and
// return an HTML warning page instead of JSON. Routing /api/v1/* through the
// Vercel server side-steps that: the browser sees same-origin, while Vercel
// reaches the Render backend server-to-server without the corporate proxy.
const backendApiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const backendOrigin = backendApiBase.replace(/\/api\/v1\/?$/, "");

// SEC-5: script-src no longer carries a static 'unsafe-inline'. Per-request
// nonces are injected by middleware.ts using buildNonceCsp(); the static CSP
// below acts as a defense-in-depth fallback for any asset path middleware does
// not run on (static images, _next/static).
const staticContentSecurityPolicy = buildStaticCsp();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: staticContentSecurityPolicy },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
  async rewrites() {
    // In local development the frontend talks directly to the local API server.
    if (process.env.NODE_ENV === "development") return [];
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
