import { redirect } from "next/navigation";

export default async function ProjectQuizRedirect({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/app/projects/${projectId}/chat?quiz=1`);
}
