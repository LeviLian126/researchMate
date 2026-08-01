// Redirects the project root to its canonical chat surface.
import { redirect } from "next/navigation";

/** Preserves a single canonical entry route for each project. */
export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/app/projects/${projectId}/chat`);
}
