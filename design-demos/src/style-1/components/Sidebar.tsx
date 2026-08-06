import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FolderPlus,
  Github,
  MessageSquare,
  Plus,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  mockConversations,
  mockPersonalProjectId,
  mockProjects,
} from "@/lib/mock-data";
import { BrandLogo } from "./BrandLogo";

interface SidebarProps {
  activeConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  activeProjectId?: string | null;
  onSelectProject?: (id: string) => void;
  onNewChat?: () => void;
  onNewProject?: () => void;
  className?: string;
}

export function Sidebar({
  activeConversationId,
  onSelectConversation,
  activeProjectId,
  onSelectProject,
  onNewChat,
  onNewProject,
  className,
}: SidebarProps) {
  const [projectsExpanded, setProjectsExpanded] = useState(true);
  const personalConvos = mockConversations.filter(
    (c) => c.project_id === mockPersonalProjectId,
  );

  return (
    <div
      className={cn(
        "flex h-full flex-col border-r border-white/30 bg-white/70 backdrop-blur-xl",
        className,
      )}
    >
      {/* Brand */}
      <div className="px-4 pb-3 pt-4">
        <BrandLogo />
      </div>

      {/* Action buttons */}
      <div className="space-y-1.5 px-3">
        <Button
          onClick={onNewChat}
          className="w-full justify-start gap-2 rounded-lg"
        >
          <Plus className="h-4 w-4" strokeWidth={1.5} />
          New chat
        </Button>
        <Button
          variant="ghost"
          onClick={onNewProject}
          className="w-full justify-start gap-2 rounded-lg text-muted-foreground hover:text-foreground"
        >
          <FolderPlus className="h-4 w-4" strokeWidth={1.5} />
          New project
        </Button>
      </div>

      <Separator className="my-3 bg-border/50" />

      {/* Scrollable nav */}
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-2">
        {/* Projects */}
        <div className="px-1">
          <button
            onClick={() => setProjectsExpanded((v) => !v)}
            className="flex w-full items-center gap-1 px-2 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
          >
            {projectsExpanded ? (
              <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" strokeWidth={1.5} />
            )}
            Projects
          </button>
          {projectsExpanded && (
            <div className="mt-0.5 space-y-0.5">
              {mockProjects.map((project) => (
                <button
                  key={project.id}
                  onClick={() => onSelectProject?.(project.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-all",
                    activeProjectId === project.id
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                  )}
                >
                  <Sparkles className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                  <span className="truncate">{project.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="my-3" />

        {/* Recents */}
        <div className="px-1">
          <p className="flex w-full items-center gap-1 px-2 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Recents
          </p>
          <div className="mt-0.5 space-y-0.5">
            {personalConvos.map((convo) => (
              <button
                key={convo.id}
                onClick={() => onSelectConversation?.(convo.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-all",
                  activeConversationId === convo.id
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                <span className="truncate">{convo.title}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-white/30 p-3">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
        >
          <Github className="h-4 w-4" strokeWidth={1.5} />
          GitHub
        </a>
      </div>
    </div>
  );
}
