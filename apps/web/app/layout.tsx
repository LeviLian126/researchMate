import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "ResearchMate",
  description: "Local-first AI research workspace with traceable sources.",
};

// 渲染全局页面壳层。
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

