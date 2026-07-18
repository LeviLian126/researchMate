"use client";

import Link from "next/link";

export function ProjectNav({ projectId, current }: { projectId: string; current: "evidence" | "library" | "quiz" | "labs" }) {
  const links = [
    { key: "evidence", label: "Evidence review", href: `/app/projects/${projectId}` },
    { key: "library", label: "Source library", href: `/app/projects/${projectId}/library` },
    { key: "quiz", label: "Grounded quiz", href: `/app/projects/${projectId}/quiz` },
    { key: "labs", label: "Engineering labs", href: `/app/projects/${projectId}/labs` },
  ] as const;
  return (
    <nav className="project-nav" aria-label="Project navigation">
      <Link className="project-nav__back" href="/app">← Projects</Link>
      <div className="project-nav__links">
        {links.map((link) => (
          <Link key={link.key} href={link.href} aria-current={current === link.key ? "page" : undefined}>
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
