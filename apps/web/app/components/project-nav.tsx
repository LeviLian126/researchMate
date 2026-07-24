// Provides the persistent project workspace navigation shared by every authenticated product surface.
"use client";

import Link from "next/link";

type ProjectSurface = "chat" | "evidence" | "library" | "quiz" | "labs";

interface ProjectNavProps {
  projectId: string;
  current: ProjectSurface;
}

/** Renders the desktop project rail and its compact mobile navigation fallback. */
export function ProjectNav({ projectId, current }: ProjectNavProps) {
  const links = [
    { key: "chat", label: "Research", symbol: "01", href: `/app/projects/${projectId}/chat` },
    { key: "library", label: "Library", symbol: "02", href: `/app/projects/${projectId}/library` },
    { key: "evidence", label: "Review", symbol: "03", href: `/app/projects/${projectId}` },
    { key: "quiz", label: "Quiz", symbol: "04", href: `/app/projects/${projectId}/quiz` },
    { key: "labs", label: "Labs", symbol: "05", href: `/app/projects/${projectId}/labs` },
  ] as const;

  return (
    <aside className="project-sidebar" aria-label="Project workspace">
      <Link className="project-brand" href="/" aria-label="ResearchMate home">
        <span className="project-brand__mark" aria-hidden="true">R</span>
        <span>Research<br />Mate</span>
      </Link>

      <div className="project-sidebar__context">
        <span className="project-sidebar__label">Project record</span>
        <Link className="project-sidebar__project" href="/app">
          <span aria-hidden="true">←</span>
          All projects
        </Link>
      </div>

      <nav className="project-sidebar__nav" aria-label="Project navigation">
        {links.map((link) => (
          <Link key={link.key} href={link.href} aria-current={current === link.key ? "page" : undefined}>
            <span className="project-sidebar__icon" aria-hidden="true">{link.symbol}</span>
            {link.label}
          </Link>
        ))}
      </nav>

      <div className="project-sidebar__footer">
        <a href="https://github.com/LeviLian126/researchMate/tree/main/docs">Documentation</a>
        <a href="https://github.com/LeviLian126/researchMate">Source code</a>
      </div>
    </aside>
  );
}
