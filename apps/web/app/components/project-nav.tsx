// Renders project-local navigation and resolves the current project label.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, FileText, HelpCircle, MessageSquare } from "lucide-react";
import { apiFetch, ProjectRecord } from "../lib/api";
import { cn } from "@/lib/utils";

/** Presents links for the active project's primary user and developer surfaces. */
export function ProjectNav({
  projectId,
  current,
}: {
  projectId: string;
  current: "chat" | "library" | "research" | "quiz" | "labs";
}) {
  const [project, setProject] = useState<ProjectRecord | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<ProjectRecord>(`/projects/${projectId}`)
      .then((record) => { if (active) setProject(record); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [projectId]);

  const links = [
    { href: `/app/projects/${projectId}/chat`, label: "Chat", icon: MessageSquare, key: "chat" as const },
    { href: `/app/projects/${projectId}/library`, label: "Sources", icon: BookOpen, key: "library" as const },
    { href: `/app/projects/${projectId}/chat?quiz=1`, label: "Quiz", icon: HelpCircle, key: "quiz" as const },
    { href: `/app/projects/${projectId}/research`, label: "Research report", icon: FileText, key: "research" as const },
  ];

  return (
    <header className="border-b border-white/30 bg-white/40 backdrop-blur-md px-6 py-3">
      <div className="flex items-center justify-between gap-4">
        <span className="text-lg font-semibold tracking-tight text-foreground">
          {project?.name ?? "Project"}
        </span>
        <nav aria-label="Project navigation" className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon, key }) => {
            const isActive = current === key;
            return (
              <Link
                key={key}
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-all",
                  isActive
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <Icon strokeWidth={1.5} className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
