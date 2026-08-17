// Provides the project-scoped entry point for the resumable evidence research workflow.
"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice, type NoticeState } from "../../../../components/state-notice";
import {
  apiFetch,
  DocumentRecord,
  idempotencyKey,
  PipelineVersionSummary,
  ReportSummary,
  ResearchRunAccepted,
  RunEvent,
  streamRunEvents,
  WorkflowRun,
} from "../../../../lib/api";
import { Button } from "@/components/ui/button";

const panelClass = "rounded-2xl border border-white/30 bg-white/70 p-6 shadow-lg shadow-primary/5 backdrop-blur-xl";

/** Starts and monitors one owner-scoped research report run. */
export default function ResearchReportPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [goal, setGoal] = useState("");
  const [allowWeb, setAllowWeb] = useState(false);
  const [reviewPolicy, setReviewPolicy] = useState<"strict" | "balanced">("strict");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [pipelines, setPipelines] = useState<PipelineVersionSummary[]>([]);
  const [pipelineVersionId, setPipelineVersionId] = useState("");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const loadReports = useCallback(async () => {
    const response = await apiFetch<{ items: ReportSummary[] }>(`/projects/${projectId}/reports`);
    setReports(response.items);
  }, [projectId]);

  useEffect(() => {
    void Promise.all([
      apiFetch<DocumentRecord[]>(`/projects/${projectId}/documents`),
      apiFetch<{ items: PipelineVersionSummary[] }>("/pipeline-versions"),
      loadReports(),
    ]).then(([sourceResult, pipelineResult]) => {
      setDocuments(sourceResult.filter((item) => item.status === "ready"));
      setPipelines(pipelineResult.items);
      setPipelineVersionId(pipelineResult.items[0]?.pipeline_version_id ?? "");
    }).catch((error) => {
      setNotice({ title: "Research setup unavailable", detail: error instanceof Error ? error.message : "Project research data could not be loaded.", kind: "error" });
    });
  }, [loadReports, projectId]);

  useEffect(() => {
    if (!run || ["succeeded", "failed", "cancelled"].includes(run.status)) return;
    const timer = window.setTimeout(() => {
      void apiFetch<WorkflowRun>(`/runs/${run.run_id}`).then(setRun).catch(() => undefined);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [run]);

  useEffect(() => {
    if (run?.status === "succeeded") void loadReports();
  }, [loadReports, run?.status]);

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) => current.includes(documentId)
      ? current.filter((value) => value !== documentId)
      : [...current, documentId]);
  }

  async function startResearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (goal.trim().length < 20) {
      setNotice({ title: "Research goal is too short", detail: "Describe a research goal in at least 20 characters so the planner can split it into evidence questions.", kind: "validation" });
      return;
    }
    if (!pipelineVersionId) {
      setNotice({ title: "No pipeline version available", detail: "An accepted pipeline version is required before a report can run.", kind: "validation" });
      return;
    }
    setBusy(true);
    setNotice(null);
    setEvents([]);
    try {
      const accepted = await apiFetch<ResearchRunAccepted>("/research-runs", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("research") },
        body: JSON.stringify({
          project_id: projectId,
          research_goal: goal.trim(),
          source_scope: { document_ids: selectedDocumentIds, allow_web: allowWeb },
          pipeline_version_id: pipelineVersionId,
          review_policy: reviewPolicy,
        }),
      });
      setRun(await apiFetch<WorkflowRun>(`/runs/${accepted.run_id}`));
      void streamRunEvents(
        accepted.run_id,
        -1,
        (event) => setEvents((current) => current.some((item) => item.event_id === event.event_id) ? current : [...current, event]),
        new AbortController().signal,
      ).catch(() => undefined);
      setNotice({ title: "Research run accepted", detail: "The workflow will plan questions, gather evidence, and publish a cited report when validation passes.", kind: "success" });
    } catch (error) {
      setNotice({ title: "Research run failed to start", detail: error instanceof Error ? error.message : "The research workflow could not be started.", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function submitDecision(decision: "approve" | "reject") {
    if (!run) return;
    try {
      await apiFetch(`/runs/${run.run_id}/decisions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("research-decision") },
        body: JSON.stringify({ interrupt_key: "evidence-review-v1", decision }),
      });
      setRun(await apiFetch<WorkflowRun>(`/runs/${run.run_id}`));
    } catch (error) {
      setNotice({ title: "Decision could not be submitted", detail: error instanceof Error ? error.message : "The workflow decision failed.", kind: "error" });
    }
  }

  return (
    <main className="min-h-0 flex-1 overflow-y-auto bg-gradient-to-br from-accent via-background to-background">
      <ProjectNav projectId={projectId} current="research" />
      <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        {notice && <StateNotice state={notice} />}
        <header className={panelClass}>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Study tool</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">Research report</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Turn a project question into a structured, citation-backed report. The workflow decomposes the goal, retrieves evidence in parallel, pauses for risk-based review, and commits only validated claims.</p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <form className={`${panelClass} space-y-4`} onSubmit={startResearch}>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Research goal</span>
              <textarea value={goal} onChange={(event) => setGoal(event.target.value)} minLength={20} rows={6} required className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Compare the strongest claims in these materials and identify assumptions that need verification." />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Pipeline version</span>
              <select value={pipelineVersionId} onChange={(event) => setPipelineVersionId(event.target.value)} required className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm">
                <option value="">No accepted pipeline available</option>
                {pipelines.map((pipeline) => <option key={pipeline.pipeline_version_id} value={pipeline.pipeline_version_id}>{pipeline.name} · v{pipeline.version}</option>)}
              </select>
            </label>
            {!!documents.length && <fieldset className="space-y-2"><legend className="text-sm font-medium text-foreground">Source scope</legend>{documents.map((document) => <label key={document.id} className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={selectedDocumentIds.includes(document.id)} onChange={() => toggleDocument(document.id)} className="size-4 accent-primary" />{document.filename}</label>)}</fieldset>}
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground"><label className="flex items-center gap-2"><input type="checkbox" checked={allowWeb} onChange={(event) => setAllowWeb(event.target.checked)} className="size-4 accent-primary" />Allow Web evidence</label><label className="flex items-center gap-2">Review policy<select value={reviewPolicy} onChange={(event) => setReviewPolicy(event.target.value as "strict" | "balanced")} className="rounded-md border border-input bg-transparent px-2 py-1"><option value="strict">Strict</option><option value="balanced">Balanced</option></select></label></div>
            <Button type="submit" disabled={busy}>{busy ? "Starting research…" : "Start research"}</Button>
          </form>

          <section className={`${panelClass} space-y-4`} aria-labelledby="run-heading">
            <div className="flex items-center justify-between gap-3"><div><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Current run</p><h2 id="run-heading" className="text-lg font-semibold text-foreground">Workflow status</h2></div>{run && <span className="rounded-md border border-border/60 px-2 py-1 text-xs font-medium text-muted-foreground">{run.status}</span>}</div>
            {run ? <div className="space-y-3 text-sm text-muted-foreground"><p>{run.current_node ?? "queued"} · {run.progress}%</p>{run.review_required && <div className="flex gap-2"><Button type="button" size="sm" onClick={() => void submitDecision("approve")}>Approve</Button><Button type="button" size="sm" variant="outline" onClick={() => void submitDecision("reject")}>Reject flagged claims</Button></div>}<p className="break-all text-xs">Run ID: {run.run_id}</p></div> : <p className="text-sm text-muted-foreground">No research run yet.</p>}
            {!!events.length && <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-border/50 bg-secondary/20 p-3 text-xs">{events.map((event) => <p key={event.event_id}>{event.node_key} · {event.event_type} · {event.status}</p>)}</div>}
            <div className="border-t border-border/50 pt-4"><div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-semibold text-foreground">Reports</h2><Button type="button" variant="ghost" size="icon" onClick={() => void loadReports()} aria-label="Refresh reports"><RefreshCw strokeWidth={1.5} /></Button></div>{reports.length ? <div className="space-y-2">{reports.map((item) => <Link key={item.report_id} href={`/app/projects/${projectId}/research/reports/${item.report_id}`} className="block w-full rounded-lg border border-border/50 p-3 text-left hover:bg-secondary/30"><span className="font-medium text-foreground">{item.title}</span><span className="ml-2 text-xs text-muted-foreground">{item.status} · revision {item.revision}</span><span className="mt-1 block text-xs text-primary">Open report reader →</span></Link>)}</div> : <p className="text-sm text-muted-foreground">Completed reports will appear here.</p>}</div>
          </section>
        </section>
      </div>
    </main>
  );
}
