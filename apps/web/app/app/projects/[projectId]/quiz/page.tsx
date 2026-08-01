// Redirects legacy project quiz routes to the chat-owned quiz drawer.
import { redirect } from "next/navigation";

/** Opens the canonical project chat route with its quiz drawer requested. */
export default async function ProjectQuizRedirect({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/app/projects/${projectId}/chat?quiz=1`);
}
