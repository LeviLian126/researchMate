// Provides the compact project header and its chat, source, quiz, and review actions.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ProjectRecord } from "../lib/api";

type ProjectSurface = "chat" | "evidence" | "library" | "quiz" | "labs";

interface ProjectNavProps {
  projectId: string;
  current: ProjectSurface;
}

/** Renders project context without exposing internal engineering tools as user navigation. */
export function ProjectNav({ projectId, current }: ProjectNavProps) {
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const links = [
    { key: "chat", label: "Chats", href: `/app/projects/${projectId}/chat` },
    { key: "library", label: "Sources", href: `/app/projects/${projectId}/library` },
    { key: "evidence", label: "Review", href: `/app/projects/${projectId}` },
  ] as const;

  useEffect(() => {
    let current = true;
    setProject(null);
    void apiFetch<ProjectRecord>(`/projects/${projectId}`)
      .then((record) => {
        if (current) setProject(record);
      })
      .catch(() => undefined);
    return () => { current = false; };
  }, [projectId]);

  return (
    <header className="project-workspace-header">
      <div className="project-workspace-header__title">
        <span aria-hidden="true">□</span>
        <h1>{project?.name ?? "Project"}</h1>
      </div>
      <div className="project-workspace-header__actions">
        <Link href={`/app/projects/${projectId}/chat?new=1`}>＋ New chat</Link>
        <Link href={`/app/projects/${projectId}/quiz?new=1`}>＋ Quiz</Link>
      </div>
      <nav className="project-workspace-tabs" aria-label="Project navigation">
        {links.map((link) => (
          <Link key={link.key} href={link.href} aria-current={current === link.key ? "page" : undefined}>
            {link.label}
          </Link>
        ))}
        {current === "quiz" && <Link href={`/app/projects/${projectId}/quiz`} aria-current="page">Quiz</Link>}
        {current === "labs" && <span aria-current="page">Engineering</span>}
      </nav>
    </header>
  );
}
