// Presents the personal ResearchMate chat within a route-level suspense boundary.
"use client";

import { Suspense } from "react";
import { ChatWorkspace } from "../components/chat-workspace";

/** Renders the personal chat route while search parameters become available. */
export default function PersonalChatPage() {
  return (
    <Suspense fallback={<main className="conversation-shell"><div className="message-skeleton">Starting chat</div></main>}>
      <ChatWorkspace />
    </Suspense>
  );
}
