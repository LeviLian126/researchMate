import { useState } from "react";
import type { DemoView } from "@/lib/types";
import { cn } from "@/lib/utils";
import { mockProjects } from "@/lib/mock-data";
import { AuthView } from "./components/AuthView";
import { ChatView } from "./components/ChatView";
import { WorkspaceView } from "./components/WorkspaceView";

const views: { id: DemoView; label: string }[] = [
  { id: "auth", label: "Auth" },
  { id: "chat", label: "Chat" },
  { id: "workspace", label: "Workspace" },
];

export default function StyleDemo() {
  const [view, setView] = useState<DemoView>("auth");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    null,
  );
  const [activeProjectId, setActiveProjectId] = useState<string>(
    mockProjects[0].id,
  );

  const handleNewChat = () => {
    setActiveConversationId(null);
    setView("chat");
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    setView("chat");
  };

  const handleSelectProject = (id: string) => {
    setActiveProjectId(id);
    setView("workspace");
  };

  return (
    <>
      {/* Floating glass view switcher */}
      <div className="fixed right-4 top-4 z-50 flex items-center gap-1 rounded-full border border-white/30 bg-white/70 p-1 shadow-lg shadow-primary/5 backdrop-blur-xl">
        {views.map((v) => (
          <button
            key={v.id}
            onClick={() => setView(v.id)}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-300",
              view === v.id
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Active view with fade-in transition */}
      <div key={view} className="animate-in fade-in-0 duration-300">
        {view === "auth" && <AuthView onDemo={() => setView("chat")} />}
        {view === "chat" && (
          <ChatView
            activeConversationId={activeConversationId}
            onSelectConversation={handleSelectConversation}
            onNewChat={handleNewChat}
            onNewProject={() => setView("workspace")}
            onSelectProject={handleSelectProject}
          />
        )}
        {view === "workspace" && (
          <WorkspaceView
            activeProjectId={activeProjectId}
            onSelectConversation={handleSelectConversation}
            onNewChat={handleNewChat}
            onNewProject={() => setView("workspace")}
            onSelectProject={handleSelectProject}
          />
        )}
      </div>
    </>
  );
}
