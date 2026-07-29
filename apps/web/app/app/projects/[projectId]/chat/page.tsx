"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ChatWorkspace } from "../../../../components/chat-workspace";
import { apiFetch, ProjectRecord } from "../../../../lib/api";

export default function ProjectChatPage() {
  return (
    <Suspense fallback={<main className="conversation-shell"><div className="message-skeleton">Loading project</div></main>}>
      <ProjectChat />
    </Suspense>
  );
}
function ProjectChat() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectRecord | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<ProjectRecord>(`/projects/${projectId}`)
      .then((record) => { if (active) setProject(record); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [projectId]);

  return (
    <ChatWorkspace
      projectId={projectId}
      projectName={project?.name}
      projectMode
    />
  );
}
