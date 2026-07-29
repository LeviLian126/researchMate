"use client";

import { Suspense } from "react";
import { ChatWorkspace } from "../components/chat-workspace";

export default function PersonalChatPage() {
  return (
    <Suspense fallback={<main className="conversation-shell"><div className="message-skeleton">Starting chat</div></main>}>
      <ChatWorkspace />
    </Suspense>
  );
}
