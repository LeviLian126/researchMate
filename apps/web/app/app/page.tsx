// Presents the personal ResearchMate chat within a route-level suspense boundary.
"use client";

import { Suspense } from "react";
import { ChatWorkspace } from "../components/chat-workspace";

/** Renders the personal chat route while search parameters become available. */
export default function PersonalChatPage() {
  return (
    <Suspense
      fallback={
        <main className="grid min-h-[100dvh] place-items-center">
          <div className="text-sm text-muted-foreground">Starting chat</div>
        </main>
      }
    >
      <ChatWorkspace />
    </Suspense>
  );
}
