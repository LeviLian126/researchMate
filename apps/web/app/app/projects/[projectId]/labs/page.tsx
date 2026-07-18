"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ProjectNav } from "../../../../components/project-nav";
import { NoticeState, StateNotice } from "../../../../components/state-notice";
import {
  apiFetch,
  describeApiError,
  EvaluationRun,
  EvaluationRunAccepted,
  EvaluationDatasetSummary,
  idempotencyKey,
  ReliabilityMetrics,
  PipelineVersionSummary,
} from "../../../../lib/api";

const UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}";
const metricOptions = ["schema_valid", "citation_precision", "evidence_recall", "faithfulness"] as const;

export default function EngineeringLabsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [datasetId, setDatasetId] = useState("");
  const [pipelineVersionId, setPipelineVersionId] = useState("");
  const [datasets, setDatasets] = useState<EvaluationDatasetSummary[]>([]);
  const [pipelines, setPipelines] = useState<PipelineVersionSummary[]>([]);
  const [metrics, setMetrics] = useState<string[]>(["schema_valid", "citation_precision", "evidence_recall"]);
  const [parallelism, setParallelism] = useState(4);
  const [budget, setBudget] = useState("1.00");
  const [evaluationId, setEvaluationId] = useState("");
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [reliability, setReliability] = useState<ReliabilityMetrics | null>(null);
  const [windowHours, setWindowHours] = useState(24);
  const [faultScenario, setFaultScenario] = useState("llm_timeout");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const loadReliability = useCallback(async () => {
    setBusy("reliability");
    try {
      setReliability(await apiFetch<ReliabilityMetrics>(`/dev/reliability?window_hours=${windowHours}`));
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }, [windowHours]);

  const loadEvaluation = useCallback(async (id: string, quiet = false) => {
    if (!id) return;
    if (!quiet) setBusy("evaluation-status");
    try {
      setEvaluation(await apiFetch<EvaluationRun>(`/evaluation-runs/${id}`));
      setEvaluationId(id);
      window.localStorage.setItem("researchmate_evaluation_run", id);
    } catch (error) {
      if (!quiet) setNotice(describeApiError(error));
    } finally {
      if (!quiet) setBusy(null);
    }
  }, []);

  useEffect(() => {
    void Promise.all([
      apiFetch<{ items: EvaluationDatasetSummary[] }>(`/evaluation-datasets?project_id=${projectId}`),
      apiFetch<{ items: PipelineVersionSummary[] }>("/pipeline-versions"),
    ]).then(([datasetResult, pipelineResult]) => {
      setDatasets(datasetResult.items);
      setPipelines(pipelineResult.items);
      setDatasetId((current) => current || datasetResult.items[0]?.dataset_id || "");
      setPipelineVersionId((current) => current || pipelineResult.items[0]?.pipeline_version_id || "");
    }).catch((error) => setNotice(describeApiError(error)));
    const saved = window.localStorage.getItem("researchmate_evaluation_run");
    if (saved) void loadEvaluation(saved, true);
  }, [loadEvaluation, projectId]);

  useEffect(() => {
    if (!evaluation || ["succeeded", "failed", "cancelled"].includes(evaluation.status)) return;
    const timer = window.setTimeout(() => void loadEvaluation(evaluation.evaluation_run_id, true), 5000);
    return () => window.clearTimeout(timer);
  }, [evaluation, loadEvaluation]);

  function toggleMetric(metric: string) {
    setMetrics((current) => current.includes(metric) ? current.filter((item) => item !== metric) : [...current, metric]);
  }

  async function createEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (metrics.length === 0) {
      setNotice({ title: "Select at least one metric", detail: "Evaluation was not submitted. Choose a deterministic metric or faithfulness.", kind: "validation" });
      return;
    }
    setBusy("evaluation-create");
    setNotice(null);
    try {
      const accepted = await apiFetch<EvaluationRunAccepted>("/evaluation-runs", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("evaluation") },
        body: JSON.stringify({ dataset_id: datasetId, pipeline_version_id: pipelineVersionId, metrics, max_parallelism: parallelism, max_cost_usd: Number(budget), labels: ["portfolio-demo"] }),
      });
      setEvaluationId(accepted.evaluation_run_id);
      setNotice({ title: "Evaluation accepted", detail: `${accepted.case_count} frozen case(s) are queued with a ${accepted.estimated_budget_boundary ?? budget} USD boundary. A zero-case result means the selected dataset is empty.`, kind: accepted.case_count === 0 ? "partial" : "success" });
      await loadEvaluation(accepted.evaluation_run_id, true);
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function runFaultExercise(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("fault");
    setNotice(null);
    try {
      const accepted = await apiFetch<{ exercise_id: string; expected_recovery_state: string; expires_at: string }>("/dev/fault-scenarios", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("fault") },
        body: JSON.stringify({ scenario: faultScenario, target_run_id: null, duration_seconds: 10 }),
      });
      setNotice({ title: "Bounded fault exercise accepted", detail: `Exercise ${accepted.exercise_id} expires at ${new Date(accepted.expires_at).toLocaleTimeString()}; expected state: ${accepted.expected_recovery_state}. Refresh reliability after expiry.`, kind: "success" });
    } catch (error) {
      setNotice(describeApiError(error));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="app-shell">
      <ProjectNav projectId={projectId} current="labs" />
      <header className="workspace-header glass-panel">
        <div><p className="eyebrow">Engineering evidence</p><h1>Evaluation & reliability labs</h1><p className="lead">Compare a frozen dataset against an accepted pipeline version, then inspect operational evidence. These controls require a developer or admin identity.</p></div>
        <span className="status-badge status-badge--developer">developer only</span>
      </header>
      {notice && <StateNotice state={notice} action={<button type="button" onClick={() => setNotice(null)}>Dismiss</button>} />}

      <section className="content-grid two-columns">
        <form className="glass-panel form-panel stack" onSubmit={createEvaluation}>
          <p className="eyebrow">Evaluation lab</p><h2>Run a versioned comparison</h2>
          <label>Frozen evaluation dataset<select value={datasetId} onChange={(event) => setDatasetId(event.target.value)} required><option value="">No frozen dataset provisioned</option>{datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name} · v{dataset.version} · {dataset.case_count} cases</option>)}</select></label>
          <label>Accepted pipeline version<select value={pipelineVersionId} onChange={(event) => setPipelineVersionId(event.target.value)} required><option value="">No accepted pipeline provisioned</option>{pipelines.map((pipeline) => <option key={pipeline.pipeline_version_id} value={pipeline.pipeline_version_id}>{pipeline.name} · v{pipeline.version}</option>)}</select></label>
          {(!datasets.length || !pipelines.length) && <div className="empty-state">Ingest a ready document, then run the guarded server-side catalog bootstrap. The UI no longer requires copying internal UUIDs.</div>}
          <fieldset><legend>Metrics</legend><div className="choice-grid">{metricOptions.map((metric) => <label className="check-row" key={metric}><input type="checkbox" checked={metrics.includes(metric)} onChange={() => toggleMetric(metric)} /> {metric.replaceAll("_", " ")}</label>)}</div></fieldset>
          <div className="field-grid"><label>Maximum parallel cases<input type="number" min="1" max="20" value={parallelism} onChange={(event) => setParallelism(Number(event.target.value))} /></label><label>Maximum cost (USD)<input type="number" min="0.01" max="25" step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} /></label></div>
          <button className="primary-button" type="submit" disabled={busy !== null}>{busy === "evaluation-create" ? "Committing evaluation…" : "Start evaluation"}</button>
          <small>Faithfulness calls the configured server-side judge. Other metrics remain deterministic; no model key enters the browser.</small>
        </form>

        <section className="glass-panel result-panel stack" aria-labelledby="evaluation-result-heading">
          <div className="section-heading"><div><p className="eyebrow">Run result</p><h2 id="evaluation-result-heading">Evaluation status</h2></div>{evaluation && <span className={`status-badge status-badge--${evaluation.status}`}>{evaluation.status}</span>}</div>
          <label>Evaluation run ID<div className="inline-control"><input value={evaluationId} pattern={UUID_PATTERN} onChange={(event) => setEvaluationId(event.target.value)} placeholder="Paste an owned evaluation ID" /><button type="button" onClick={() => void loadEvaluation(evaluationId)} disabled={!evaluationId || busy !== null}>Load</button></div></label>
          {evaluation ? <><div className="run-summary"><div><span>Progress</span><strong>{evaluation.progress}%</strong></div><div><span>Scores</span><strong>{evaluation.scores.length}</strong></div><div><span>State</span><strong>{evaluation.status}</strong></div><progress max="100" value={evaluation.progress} /></div>{evaluation.summary ? <pre className="json-result">{JSON.stringify(evaluation.summary, null, 2)}</pre> : <div className="empty-state">No aggregate summary yet. Pending may mean the worker, RAGAS runtime, provider, or frozen dataset is not configured.</div>}</> : <div className="empty-state">Start an evaluation or load a previous run. The UI does not manufacture benchmark scores.</div>}
        </section>

        <section className="glass-panel result-panel stack" aria-labelledby="reliability-heading">
          <div className="section-heading"><div><p className="eyebrow">Reliability lab</p><h2 id="reliability-heading">Operational window</h2></div><button type="button" onClick={() => void loadReliability()} disabled={busy !== null}>{busy === "reliability" ? "Loading…" : "Refresh metrics"}</button></div>
          <label>Window (hours)<select value={windowHours} onChange={(event) => setWindowHours(Number(event.target.value))}><option value="1">1 hour</option><option value="24">24 hours</option><option value="72">72 hours</option><option value="168">7 days</option></select></label>
          {reliability ? <div className="metrics-grid"><article><span>Runs</span><strong>{reliability.run_count}</strong></article><article><span>Success</span><strong>{Math.round(reliability.success_rate * 100)}%</strong></article><article><span>Errors</span><strong>{Math.round(reliability.error_rate * 100)}%</strong></article><article><span>Retries</span><strong>{reliability.retry_count}</strong></article><article><span>P95</span><strong>{reliability.p95_latency_ms == null ? "not sampled" : `${reliability.p95_latency_ms} ms`}</strong></article><article><span>Cost</span><strong>${Number(reliability.cost_usd).toFixed(4)}</strong></article></div> : <div className="empty-state">Metrics are loaded on demand. Zero traffic is a valid empty window, not a reliability claim.</div>}
        </section>

        <form className="glass-panel form-panel stack attention-panel" onSubmit={runFaultExercise}>
          <p className="eyebrow">Recovery proof</p><h2>Exercise one bounded failure</h2>
          <p>This endpoint is hidden in production and available only in local, test, or preview. It records an expiring exercise rather than exposing arbitrary fault injection.</p>
          <label>Scenario<select value={faultScenario} onChange={(event) => setFaultScenario(event.target.value)}><option value="llm_timeout">LLM timeout</option><option value="qdrant_unavailable">Qdrant unavailable</option><option value="worker_interrupt">Worker interrupt</option><option value="r2_failure">R2 failure</option></select></label>
          <button type="submit" disabled={busy !== null}>{busy === "fault" ? "Scheduling…" : "Run 10-second exercise"}</button>
          <small>Use a disposable preview environment. Existing canonical business state remains in PostgreSQL.</small>
        </form>
      </section>
    </main>
  );
}
