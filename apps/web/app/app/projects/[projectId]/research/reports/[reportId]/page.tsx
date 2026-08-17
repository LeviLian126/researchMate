// Provides a focused, scrollable reader for one published research report.
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProjectNav } from "../../../../../../components/project-nav";
import { StateNotice, type NoticeState } from "../../../../../../components/state-notice";
import { apiFetch, ReportDetail } from "../../../../../../lib/api";

const panelClass = "rounded-2xl border border-white/30 bg-white/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-xl";

/** Loads one owner-scoped report and presents its complete section content. */
export default function ReportReaderPage() {
  const { projectId, reportId } = useParams<{ projectId: string; reportId: string }>();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  useEffect(() => {
    void apiFetch<ReportDetail>(`/reports/${reportId}`)
      .then(setReport)
      .catch((error) => setNotice({
        title: "Report unavailable",
        detail: error instanceof Error ? error.message : "The report could not be loaded.",
        kind: "error",
      }));
  }, [reportId]);

  return (
    <main className="min-h-0 flex-1 overflow-y-auto bg-gradient-to-br from-accent via-background to-background">
      <ProjectNav projectId={projectId} current="research" />
      <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        {notice && <StateNotice state={notice} />}
        <Link href={`/app/projects/${projectId}/research`} className="inline-flex text-sm text-primary hover:underline">← Back to research workflow</Link>
        {report && <article className={`${panelClass} space-y-6`}>
          <header className="border-b border-border/50 pb-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Published report</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-foreground">{report.title}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{report.status} · revision {report.revision}</p>
          </header>
          {report.sections.map((section) => <section key={section.section_id} className="border-b border-border/50 pb-6 last:border-b-0 last:pb-0">
            <h2 className="text-xl font-semibold text-foreground">{section.heading}</h2>
            <div className="prose prose-sm mt-3 max-w-none whitespace-pre-wrap text-muted-foreground">{section.body_markdown}</div>
          </section>)}
        </article>}
      </div>
    </main>
  );
}
