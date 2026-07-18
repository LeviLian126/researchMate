"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProjectNav } from "../../../components/project-nav";
import { NoticeState, StateNotice } from "../../../components/state-notice";
import {
  apiFetch,
  AskResponse,
  DocumentRecord,
  ClaimRelationSummary,
  ClaimSummary,
  describeApiError,
  idempotencyKey,
  ReportSummary,
  ReportDetail,
  PipelineVersionSummary,
  ResearchRunAccepted,
  RunEvent,
  streamRunEvents,
  WorkflowRun,
} from "../../../lib/api";

const UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}";

function StatusBadge({ value }: { value: string }) {
  return <span className={`status-badge status-badge--${value}`}>{value.replaceAll("_", " ")}</span>;
}

function safeString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export default function EvidenceReviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [goal, setGoal] = useState("Compare the strongest evidence for and against retrieval-augmented generation improving factual reliability.");
  const [pipelineVersionId, setPipelineVersionId] = useState("");
  const [pipelines, setPipelines] = useState<PipelineVersionSummary[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [reviewPolicy, setReviewPolicy] = useState<"strict" | "balanced">("strict");
  const [allowWeb, setAllowWeb] = useState(false);
  const [maxCost, setMaxCost] = useState("2.00");
  const [runIdDraft, setRunIdDraft] = useState("");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [relations, setRelations] = useState<ClaimRelationSummary[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [reportDetail, setReportDetail] = useState<ReportDetail | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const streamController = useRef<AbortController | null>(null);

  const [decision, setDecision] = useState<"approve" | "edit" | "reject">("approve");
  const [interruptKey, setInterruptKey] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [editedPayload, setEditedPayload] = useState("{}");
  const [refreshSections, setRefreshSections] = useState("executive-summary");

  const [askMessage, setAskMessage] = useState("Summarize the strongest supported conclusion in the current project.");
  const [askAnswer, setAskAnswer] = useState<AskResponse | null>(null);

  const activeInterrupt = useMemo(() => {
    for (const event of [...events].reverse()) {
      const key = safeString(event.safe_payload.interrupt_key);
      if (key) return key;
    }
    return "";
  }, [events]);

  const refreshArtifacts = useCallback(async () => {
    try {
      const [claimResult, relationResult, reportResult, documentResult, pipelineResult] = await Promise.all([
        apiFetch<{ items: ClaimSummary[] }>(`/projects/${projectId}/claims`),
        apiFetch<{ items: ClaimRelationSummary[] }>(`/projects/${projectId}/claim-relations`),
        apiFetch<{ items: ReportSummary[] }>(`/projects/${projectId}/reports`),
        apiFetch<DocumentRecord[]>(`/projects/${projectId}/documents`),
        apiFetch<{ items: PipelineVersionSummary[] }>("/pipeline-versions"),
      ]);
      setClaims(claimResult.items);
      setRelations(relationResult.items);
      setReports(reportResult.items);
      const readyDocuments = documentResult.filter((item) => item.status === "ready");
      setDocuments(readyDocuments);
      setPipelines(pipelineResult.items);
      setPipelineVersionId((current) => current || pipelineResult.items[0]?.pipeline_version_id || "");
    } catch (error) {
      setNotice(describeApiError(error));
    }
  }, [projectId]);

  const loadRun = useCallback(async (targetRunId: string, quiet = false) => {
    if (!targetRunId) return;
    if (!quiet) setBusy("run");
    try {
      const next = await apiFetch<WorkflowRun>(`/runs/${targetRunId}`);
      setRun(next);
      setRunIdDraft(next.run_id);
      window.localStorage.setItem(`researchmate_run_${projectId}`, next.run_id);
      if (next.status === "succeeded") await refreshArtifacts();
      if (next.status === "failed") {
        setNotice({ title: "Run failed safely", detail: `The workflow stopped with ${next.error_code ?? "an unspecified error"}. Evidence already committed remains available; retry with a new run after correcting the provider or input.`, kind: "error" });
      }
    } catch (error) {
      if (!quiet) setNotice(describeApiError(error));
    } finally {
      if (!quiet) setBusy(null);
    }
  }, [projectId, refreshArtifacts]);

  useEffect(() => {
    void refreshArtifacts();
    const saved = window.localStorage.getItem(`researchmate_run_${projectId}`);
    if (saved) void loadRun(saved, true);
    return () => streamController.current?.abort();
  }, [loadRun, projectId, refreshArtifacts]);

  useEffect(() => {
    if (!run || ["succeeded", "failed", "cancelled", "waiting_human"].includes(run.status)) return;
    const timer = window.setTimeout(() => void loadRun(run.run_id, true), 4000);
    return () => window.clearTimeout(timer);
  }, [loadRun, run]);

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setNotice(null);
    setEvents([]);
    try {
      const accepted = await apiFetch<ResearchRunAccepted>("/research-runs", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("research-run") },
        body: JSON.stringify({
          project_id: projectId,
          research_goal: goal,
          source_scope: { document_ids: selectedDocumentIds, allow_web: allowWeb },
          pipeline_version_id: pipelineVersionId,
          review_policy: reviewPolicy,
          max_cost_usd: maxCost ? Number(maxCost) : null,
        }),
      });
      setRunIdDraft(accepted.run_id);
      setNotice({ title: "Research run accepted", detail: "The API committed the run and outbox event. Background execution may remain pending until the worker and managed providers are configured.", kind: "success" });
      await loadRun(accepted.run_id, true);
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) => current.includes(documentId)
      ? current.filter((item) => item !== documentId)
      : [...current, documentId]);
  }

  async function loadReportDetail(reportId: string) {
    setBusy(`detail-${reportId}`);
    try {
      setReportDetail(await apiFetch<ReportDetail>(`/reports/${reportId}`));
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function connectEvents() {
    if (!runIdDraft) return;
    streamController.current?.abort();
    const controller = new AbortController();
    streamController.current = controller;
    setBusy("events");
    setNotice({ title: "Listening for durable events", detail: "The authenticated stream replays events after the last sequence and emits heartbeats while the worker is idle.", kind: "info" });
    try {
      const cursor = events.length ? Math.max(...events.map((item) => item.sequence)) : -1;
      await streamRunEvents(runIdDraft, cursor, (event) => {
        setEvents((current) => current.some((item) => item.sequence === event.sequence) ? current : [...current, event].sort((a, b) => a.sequence - b.sequence));
        const key = safeString(event.safe_payload.interrupt_key);
        if (key) setInterruptKey(key);
      }, controller.signal);
      await loadRun(runIdDraft, true);
    } catch (error) {
      if (!controller.signal.aborted) setNotice(describeApiError(error));
    } finally {
      if (!controller.signal.aborted) setBusy(null);
    }
  }

  async function submitDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("decision");
    setNotice(null);
    try {
      let parsed: Record<string, unknown> | undefined;
      if (decision === "edit") parsed = JSON.parse(editedPayload) as Record<string, unknown>;
      await apiFetch(`/runs/${run?.run_id}/decisions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("human-decision") },
        body: JSON.stringify({ interrupt_key: interruptKey || activeInterrupt, decision, edited_payload: parsed, reason: decisionReason || null }),
      });
      setNotice({ title: "Decision accepted", detail: "The decision was stored once and the workflow resume request was written to the durable outbox.", kind: "success" });
      if (run) await loadRun(run.run_id, true);
    } catch (error) {
      setNotice(error instanceof SyntaxError
        ? { title: "Edited payload is not valid JSON", detail: "Correct the JSON object; your decision has not been submitted.", kind: "validation" }
        : describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function refreshReport(report: ReportSummary) {
    setBusy(`report-${report.report_id}`);
    setNotice(null);
    try {
      const forceSections = refreshSections.split(",").map((value) => value.trim()).filter(Boolean);
      const accepted = await apiFetch<{ run_id: string; impacted_section_keys: string[] }>(`/reports/${report.report_id}/refresh`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("report-refresh") },
        body: JSON.stringify({ changed_document_ids: [], force_sections: forceSections, pipeline_version_id: pipelineVersionId || run?.pipeline_version_id }),
      });
      setNotice({ title: "Incremental refresh accepted", detail: `${accepted.impacted_section_keys.length} section(s) are scheduled; unchanged sections keep their previous revision.`, kind: "success" });
      await loadRun(accepted.run_id, true);
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function submitAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("ask");
    setNotice(null);
    try {
      setAskAnswer(await apiFetch<AskResponse>("/ask", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, message: askMessage, selected_mode: "local_only" }),
      }));
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="app-shell">
      <ProjectNav projectId={projectId} current="evidence" />
      <header className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Multi-source evidence review</p>
          <h1>Build a defensible research report</h1>
          <p className="lead">This personal engineering demo decomposes a research goal, reconciles claims across sources, pauses for human review, and commits a citation-backed report.</p>
        </div>
        <Link className="secondary-button" href={`/app/projects/${projectId}/library`}>Manage sources</Link>
      </header>

      {notice && <StateNotice state={notice} action={<button type="button" onClick={() => setNotice(null)}>Dismiss</button>} />}

      <section className="evidence-layout" aria-label="Evidence workflow">
        <div className="stack">
          <form className="glass-panel form-panel stack" onSubmit={createRun}>
            <div className="section-heading">
              <div><p className="eyebrow">01 · Configure</p><h2>Start an evidence review</h2></div>
              <span className="status-badge status-badge--bounded">budget bounded</span>
            </div>
            <label htmlFor="research-goal">Research goal</label>
            <textarea id="research-goal" value={goal} minLength={20} maxLength={12000} rows={5} onChange={(event) => setGoal(event.target.value)} required />
            <label htmlFor="pipeline-version">Accepted pipeline version</label>
            <select id="pipeline-version" value={pipelineVersionId} onChange={(event) => setPipelineVersionId(event.target.value)} required aria-describedby="pipeline-help">
              <option value="">No accepted pipeline provisioned</option>
              {pipelines.map((pipeline) => <option key={pipeline.pipeline_version_id} value={pipeline.pipeline_version_id}>{pipeline.name} · v{pipeline.version}</option>)}
            </select>
            <small id="pipeline-help">The server catalog exposes only accepted versions. Run the guarded bootstrap after the first document is ingested if this list is empty.</small>
            <fieldset><legend>Ready document scope</legend><div className="choice-grid">
              {documents.length === 0 ? <small>No ready document is available. Ingest a source or enable web retrieval.</small> : documents.map((document) => <label className="check-row" key={document.id}><input type="checkbox" checked={selectedDocumentIds.includes(document.id)} onChange={() => toggleDocument(document.id)} /> {document.filename}</label>)}
            </div><small>With no box selected, the server searches all ready project documents. Explicit selections are ownership-validated.</small></fieldset>
            <div className="field-grid">
              <label>Review policy<select value={reviewPolicy} onChange={(event) => setReviewPolicy(event.target.value as "strict" | "balanced")}><option value="strict">Strict</option><option value="balanced">Balanced</option></select></label>
              <label>Maximum cost (USD)<input type="number" min="0.01" max="25" step="0.01" value={maxCost} onChange={(event) => setMaxCost(event.target.value)} /></label>
            </div>
            <label className="check-row"><input type="checkbox" checked={allowWeb} onChange={(event) => setAllowWeb(event.target.checked)} /> Allow approved web retrieval for this run</label>
            <button className="primary-button" type="submit" disabled={busy !== null}>{busy === "create" ? "Committing run…" : "Create research run"}</button>
          </form>

          <section className="glass-panel form-panel stack" aria-labelledby="run-heading">
            <div className="section-heading"><div><p className="eyebrow">02 · Observe</p><h2 id="run-heading">Durable run state</h2></div>{run && <StatusBadge value={run.status} />}</div>
            <label htmlFor="run-id">Run ID</label>
            <div className="inline-control"><input id="run-id" value={runIdDraft} pattern={UUID_PATTERN} onChange={(event) => setRunIdDraft(event.target.value)} placeholder="Paste a run ID to recover observation" /><button type="button" onClick={() => void loadRun(runIdDraft)} disabled={!runIdDraft || busy !== null}>Load</button></div>
            {run ? (
              <div className="run-summary">
                <div><span>Progress</span><strong>{run.progress}%</strong></div><div><span>Node</span><strong>{run.current_node ?? "queued"}</strong></div><div><span>Review</span><strong>{run.review_required ? "required" : "not requested"}</strong></div>
                <progress max="100" value={run.progress} aria-label={`Run progress ${run.progress}%`} />
              </div>
            ) : <div className="empty-state">Create a run or paste an owned Run ID. Run history is intentionally not invented because the current API exposes only direct lookup.</div>}
            <div className="row-actions"><button type="button" onClick={() => void connectEvents()} disabled={!runIdDraft || busy !== null}>{busy === "events" ? "Listening…" : "Replay live events"}</button><button type="button" onClick={() => void refreshArtifacts()} disabled={busy !== null}>Refresh evidence</button></div>
            <ol className="event-list" aria-live="polite">
              {events.length === 0 && <li className="empty-state">No replayed events yet. A pending run may be waiting for the worker or managed providers.</li>}
              {events.map((event) => <li key={event.sequence}><span>{event.sequence}</span><div><strong>{event.event_type.replaceAll("_", " ")}</strong><small>{event.node_key} · attempt {event.attempt} · {event.status}</small></div>{event.latency_ms != null && <small>{event.latency_ms} ms</small>}</li>)}
            </ol>
          </section>

          {(run?.status === "waiting_human" || run?.review_required) && (
            <form className="glass-panel form-panel stack attention-panel" onSubmit={submitDecision}>
              <p className="eyebrow">Human checkpoint</p><h2>Review before synthesis</h2>
              <p>The workflow paused because evidence confidence or source safety requires an explicit decision. Refresh the run after another reviewer acts to avoid a stale submission.</p>
              <label>Interrupt key<input value={interruptKey || activeInterrupt} onChange={(event) => setInterruptKey(event.target.value)} required /></label>
              <label>Decision<select value={decision} onChange={(event) => setDecision(event.target.value as typeof decision)}><option value="approve">Approve evidence</option><option value="edit">Edit safe payload</option><option value="reject">Reject conclusion</option></select></label>
              {decision === "edit" && <label>Edited JSON payload<textarea rows={5} value={editedPayload} onChange={(event) => setEditedPayload(event.target.value)} /></label>}
              <label>Reason (optional)<textarea rows={3} maxLength={2000} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} /></label>
              <button className="primary-button" type="submit" disabled={busy !== null}>Submit decision once</button>
            </form>
          )}
        </div>

        <div className="stack">
          <section className="glass-panel result-panel" aria-labelledby="claims-heading">
            <div className="section-heading"><div><p className="eyebrow">03 · Inspect</p><h2 id="claims-heading">Claims</h2></div><span>{claims.length}</span></div>
            {claims.length === 0 ? <div className="empty-state">No committed claims. This is expected before a workflow succeeds, and may also indicate a worker/provider configuration gap.</div> : <div className="card-list">{claims.map((claim) => <article className="claim-card" key={claim.claim_id}><div className="section-heading"><StatusBadge value={claim.review_status} /><strong>{Math.round(claim.confidence * 100)}% confidence</strong></div><p>{claim.text}</p><div className="metric-row"><span>{claim.evidence_count} evidence</span><span>{claim.support_count} support</span><span>{claim.contradiction_count} conflict</span><span>v{claim.source_version}</span></div></article>)}</div>}
          </section>

          <section className="glass-panel result-panel" aria-labelledby="relations-heading">
            <div className="section-heading"><h2 id="relations-heading">Claim relations</h2><span>{relations.length}</span></div>
            {relations.length === 0 ? <div className="empty-state">No support, contradiction, or duplicate relationships have been committed.</div> : <div className="relation-list">{relations.map((relation) => <article key={`${relation.source_claim_id}-${relation.target_claim_id}-${relation.relation}`}><StatusBadge value={relation.relation} /><p>{relation.source_text}</p><span aria-hidden="true">↓</span><p>{relation.target_text}</p><small>{Math.round(relation.confidence * 100)}% · {relation.rationale_summary ?? "No rationale summary"}</small></article>)}</div>}
          </section>

          <section className="glass-panel result-panel" aria-labelledby="reports-heading">
            <div className="section-heading"><div><p className="eyebrow">04 · Publish</p><h2 id="reports-heading">Reports</h2></div><span>{reports.length}</span></div>
            {reports.length === 0 ? <div className="empty-state">No report revision is available. A run must pass schema and citation validation before a report is committed.</div> : <div className="card-list">{reports.map((report) => <article className="report-card" key={report.report_id}><div><h3>{report.title}</h3><div className="metric-row"><StatusBadge value={report.status} /><StatusBadge value={report.validation_status} /><span>revision {report.revision}</span></div></div><div className="row-actions"><button type="button" onClick={() => void loadReportDetail(report.report_id)} disabled={busy !== null}>{busy === `detail-${report.report_id}` ? "Loading…" : "Read report"}</button></div><label>Forced section keys<input value={refreshSections} onChange={(event) => setRefreshSections(event.target.value)} /></label><button type="button" onClick={() => void refreshReport(report)} disabled={busy !== null || !(pipelineVersionId || run?.pipeline_version_id)}>{busy === `report-${report.report_id}` ? "Scheduling…" : "Refresh impacted sections"}</button></article>)}</div>}
            {reportDetail && <article className="answer-card"><div className="section-heading"><h3>{reportDetail.title} · revision {reportDetail.revision}</h3><button type="button" onClick={() => setReportDetail(null)}>Close</button></div>{reportDetail.sections.map((section) => <section key={section.section_id}><h4>{section.heading}</h4><pre>{section.body_markdown}</pre><small>{section.section_key} · {section.validation_status}</small></section>)}</article>}
          </section>

          <details className="glass-panel result-panel">
            <summary>Quick grounded query</summary>
            <form className="stack details-body" onSubmit={submitAsk}><p>This synchronous path is useful for a small source question; it does not replace the durable evidence workflow.</p><label>Question<textarea rows={3} value={askMessage} onChange={(event) => setAskMessage(event.target.value)} /></label><button type="submit" disabled={busy !== null}>{busy === "ask" ? "Generating…" : "Ask local sources"}</button>{askAnswer && <article className="answer-card"><pre>{askAnswer.answer}</pre><small>{askAnswer.citations.length} citation(s) · validation {askAnswer.validation_status}</small></article>}</form>
          </details>
        </div>
      </section>
    </main>
  );
}
