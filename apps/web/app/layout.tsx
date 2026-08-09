// Defines the root HTML document, metadata, and global frontend design-system boundary.
import "./globals.css";
import type { ReactNode } from "react";
import { headers } from "next/headers";
import { NONCE_CONTEXT_DEFAULT, SessionNonceProvider } from "./nonce-context";

export const metadata = {
  title: "ResearchMate · Research workspace",
  description: "Private conversations, shared project sources, cited answers, and project quizzes.",
};

// SEC-5: the nonce is generated per-request by middleware.ts and forwarded
// via the x-researchmate-nonce request header. Inline first-party scripts that
// need to execute must read the nonce from this context and pass it to
// next/script's `nonce` prop or set <script nonce={...}> on raw elements.
async function readRequestNonce(): Promise<string> {
  const list = await headers();
  return list.get("x-researchmate-nonce") ?? NONCE_CONTEXT_DEFAULT;
}

/** Supplies document metadata and the shared ResearchMate visual system. */
export default async function RootLayout({ children }: { children: ReactNode }) {
  const nonce = await readRequestNonce();
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <SessionNonceProvider value={nonce}>{children}</SessionNonceProvider>
      </body>
    </html>
  );
}
