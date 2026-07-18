import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "ResearchMate · AI Engineering Portfolio",
  description: "A production-oriented Agentic RAG engineering demo for multi-source evidence review.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
