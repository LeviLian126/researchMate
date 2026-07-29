// Defines the root HTML document, metadata, and global frontend design-system boundary.
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "ResearchMate · Research workspace",
  description: "Private conversations, shared project sources, cited answers, and project quizzes.",
};

/** Supplies document metadata and the shared ResearchMate visual system. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
