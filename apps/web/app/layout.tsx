// Defines the root HTML document, metadata, and global frontend design-system boundary.
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "ResearchMate · Inspectable evidence",
  description: "A production-oriented Agentic RAG engineering demo for multi-source evidence review.",
};

/** Supplies document metadata and the shared Cobalt Studio visual system. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
