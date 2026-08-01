// Renders project-local navigation and resolves the current project label.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ProjectRecord } from "../lib/api";

/** Presents links for the active project's primary user and developer surfaces. */
export function ProjectNav({
  projectId,
  current,
}: {
  projectId: string;
  current: "chat" | "library" | "evidence" | "quiz" | "labs";
}) {
  const [project, setProject] = useState<ProjectRecord | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<ProjectRecord>(`/projects/${projectId}`)
      .then((record) => { if (active) setProject(record); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [projectId]);

  return (
    <header className="project-workspace-header">
      <div className="project-workspace-header__title">
        <span aria-hidden="true">□</span>
        <strong>{project?.name ?? "Project"}</strong>
      </div>
      <nav aria-label="Project navigation">
        <Link
          href={`/app/projects/${projectId}/chat`}
          aria-current={current === "chat" ? "page" : undefined}
        >
          Chats
        </Link>
        <Link
          href={`/app/projects/${projectId}/library`}
          aria-current={current === "library" ? "page" : undefined}
        >
          Sources
        </Link>
        <Link href={`/app/projects/${projectId}/chat?quiz=1`}>Quiz</Link>
      </nav>
    </header>
  );
}
