// Presents role-restricted evaluation, reliability, and fault-exercise developer tools.
"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { ProjectNav } from "../../../../components/project-nav";
import { EvaluationReport } from "../../../../components/evaluation-report";
import { FeedbackReviewQueue } from "../../../../components/feedback-review-queue";
import { NoticeState, StateNotice } from "../../../../components/state-notice";
import {
  apiFetch,
  describeApiError,
  EvaluationRun,
  EvaluationRunAccepted,
  EvaluationDatasetSummary,
  FeedbackPromotionResult,
  idempotencyKey,
  ReliabilityMetrics,
  PipelineVersionSummary,
} from "../../../../lib/api";
import { getSupabaseSession, isLocalDevelopment } from "../../../../lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}";
const metricOptions = [
  "schema_valid",
  "citation_precision",
  "evidence_recall",
  "retrieval_mrr",
  "retrieval_ndcg",
  "faithfulness",
] as const;
const selectClass =
  "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1";
const glassPanel = "rounded-2xl border border-border/60 bg-white/50 p-6 backdrop-blur-sm";
const emptyNote = "rounded-lg border border-border/50 bg-secondary/30 px-4 py-3 text-sm text-muted-foreground";

/** Prevents ordinary users from rendering developer controls before backend enforcement. */
export default function EngineeringLabsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [access, setAccess] = useState<"loading" | "allowed" | "denied">(
    isLocalDevelopment() ? "allowed" : "loading",
  );

  useEffect(() => {
    if (isLocalDevelopment()) return;
    void getSupabaseSession().then((session) => {
      setAccess(["developer", "admin"].includes(session?.user?.role ?? "") ? "allowed" : "denied");
    }).catch(() => setAccess("denied"));
  }, []);

  if (access !== "allowed") {
    return (
      <main className="min-h-[100dvh] bg-background">
        <ProjectNav projectId={projectId} current="labs" />
        <div className="mx-auto max-w-2xl px-6 py-16">
          {access === "loading" ? (
            <div className="rounded-2xl border border-border/60 bg-card p-6 text-center text-sm text-muted-foreground shadow-sm" role="status">
              Checking Engineering access…
            </div>
          ) : (
            <div className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
              <StateNotice state={{ title: "Developer access required", detail: "Evaluation, reliability, and fault controls are not part of the normal project workspace.", kind: "permission" }} />
            </div>
          )}
        </div>
      </main>
    );
  }
  return <EngineeringLabsWorkspace />;
}

/** Runs the role-restricted evaluation, reliability, and fault-control workspace. */
function EngineeringLabsWorkspace() {
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

  /** Reloads reliability metrics for the selected time window. */
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

  /** Loads one evaluation and optionally suppresses transient polling failures. */
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

  /** Refreshes immutable datasets and accepted candidate pipeline versions. */
  const loadCatalog = useCallback(async () => {
    const [datasetResult, pipelineResult] = await Promise.all([
      apiFetch<{ items: EvaluationDatasetSummary[] }>(`/evaluation-datasets?project_id=${projectId}`),
      apiFetch<{ items: PipelineVersionSummary[] }>("/pipeline-versions"),
    ]);
    setDatasets(datasetResult.items);
    setPipelines(pipelineResult.items);
    setDatasetId((current) => current || datasetResult.items[0]?.dataset_id || "");
    setPipelineVersionId((current) => current || pipelineResult.items[0]?.pipeline_version_id || "");
  }, [projectId]);

  useEffect(() => {
    void loadCatalog().catch((error) => setNotice(describeApiError(error)));
    const saved = window.localStorage.getItem("researchmate_evaluation_run");
    if (saved) void loadEvaluation(saved, true);
  }, [loadCatalog, loadEvaluation]);

  /** Makes a newly promoted frozen dataset immediately selectable for evaluation. */
  function handleDatasetCreated(result: FeedbackPromotionResult) {
    setDatasetId(result.dataset_id);
    setNotice({
      title: "Regression dataset created",
      detail: `Frozen dataset version ${result.dataset_version} now includes the reviewed Bad Case.`,
      kind: "success",
    });
    void loadCatalog().catch((error) => setNotice(describeApiError(error)));
  }

  useEffect(() => {
    if (!evaluation || ["succeeded", "failed", "cancelled"].includes(evaluation.status)) return;
    const timer = window.setTimeout(() => void loadEvaluation(evaluation.evaluation_run_id, true), 5000);
    return () => window.clearTimeout(timer);
  }, [evaluation, loadEvaluation]);

  /** Adds or removes one evaluation metric from the requested run. */
  function toggleMetric(metric: string) {
    setMetrics((current) => current.includes(metric) ? current.filter((item) => item !== metric) : [...current, metric]);
  }

  /** Creates an idempotent evaluation run from the selected dataset and pipeline. */
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

  /** Runs an explicitly selected local fault exercise for developer validation. */
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
    <main className="min-h-[100dvh] bg-background">
      <ProjectNav projectId={projectId} current="labs" />
      <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div className={glassPanel}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Engineering evidence</p>
              <h1 className="mt-1 text-xl font-bold tracking-tight text-foreground">Evaluation &amp; reliability labs</h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Compare a frozen dataset against an accepted pipeline version, then inspect operational evidence. These controls require a developer or admin identity.</p>
            </div>
            <Badge variant="outline" className="shrink-0 border-primary/30 text-primary">developer only</Badge>
          </div>
        </div>

        {notice && (
          <StateNotice state={notice} action={<Button type="button" variant="outline" size="sm" onClick={() => setNotice(null)}>Dismiss</Button>} />
        )}

        <section className="grid gap-6 md:grid-cols-2">
          <form className={`${glassPanel} space-y-4`} onSubmit={createEvaluation}>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evaluation lab</p>
              <h2 className="mt-1 text-lg font-semibold text-foreground">Run a versioned comparison</h2>
            </div>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Frozen evaluation dataset</span>
              <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)} required className={selectClass}>
                <option value="">No frozen dataset provisioned</option>
                {datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name} · v{dataset.version} · {dataset.case_count} cases</option>)}
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Accepted pipeline version</span>
              <select value={pipelineVersionId} onChange={(event) => setPipelineVersionId(event.target.value)} required className={selectClass}>
                <option value="">No accepted pipeline provisioned</option>
                {pipelines.map((pipeline) => <option key={pipeline.pipeline_version_id} value={pipeline.pipeline_version_id}>{pipeline.name} · v{pipeline.version}</option>)}
              </select>
            </label>
            {(!datasets.length || !pipelines.length) && <p className={emptyNote}>Ingest a ready document, then run the guarded server-side catalog bootstrap. The UI no longer requires copying internal UUIDs.</p>}
            <fieldset className="space-y-3">
              <legend className="text-sm font-medium text-foreground">Metrics</legend>
              <div className="grid grid-cols-2 gap-2">
                {metricOptions.map((metric) => (
                  <label key={metric} className="flex cursor-pointer items-center gap-2 rounded-lg border border-border/50 bg-white/40 px-3 py-2 text-sm transition-all hover:bg-white/70">
                    <input type="checkbox" checked={metrics.includes(metric)} onChange={() => toggleMetric(metric)} className="size-4 accent-primary" />
                    <span className="text-muted-foreground">{metric.replaceAll("_", " ")}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="grid grid-cols-2 gap-3">
              <label className="block space-y-1.5">
                <span className="text-sm font-medium text-foreground">Maximum parallel cases</span>
                <Input type="number" min="1" max="20" value={parallelism} onChange={(event) => setParallelism(Number(event.target.value))} />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium text-foreground">Maximum cost (USD)</span>
                <Input type="number" min="0.01" max="25" step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} />
              </label>
            </div>
            <Button type="submit" disabled={busy !== null} className="w-full">
              {busy === "evaluation-create" ? "Committing evaluation…" : "Start evaluation"}
            </Button>
            <p className="text-xs text-muted-foreground">Faithfulness calls the configured server-side judge. Other metrics remain deterministic; no model key enters the browser.</p>
          </form>

          <section className={`${glassPanel} space-y-4`} aria-labelledby="evaluation-result-heading">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Run result</p>
                <h2 id="evaluation-result-heading" className="mt-1 text-lg font-semibold text-foreground">Evaluation status</h2>
              </div>
              {evaluation && (
                <Badge variant={evaluation.status === "succeeded" ? "success" : evaluation.status === "failed" || evaluation.status === "cancelled" ? "destructive" : "warning"}>
                  {evaluation.status}
                </Badge>
              )}
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Evaluation run ID</label>
              <div className="flex gap-2">
                <Input value={evaluationId} pattern={UUID_PATTERN} onChange={(event) => setEvaluationId(event.target.value)} placeholder="Paste an owned evaluation ID" />
                <Button type="button" onClick={() => void loadEvaluation(evaluationId)} disabled={!evaluationId || busy !== null}>Load</Button>
              </div>
            </div>
            {evaluation ? (
              <>
                <div className="grid gap-3 sm:grid-cols-4">
                  <div className="rounded-lg border border-border/50 bg-white/40 p-4 sm:col-span-2">
                    <span className="text-sm text-muted-foreground">Progress</span>
                    <p className="text-2xl font-semibold text-foreground">{evaluation.progress}%</p>
                  </div>
                  <div className="rounded-lg border border-border/50 bg-white/40 p-3">
                    <span className="text-sm text-muted-foreground">Scores</span>
                    <p className="text-lg font-semibold text-foreground">{evaluation.scores.length}</p>
                  </div>
                  <div className="rounded-lg border border-border/50 bg-white/40 p-3">
                    <span className="text-sm text-muted-foreground">State</span>
                    <p className="text-lg font-semibold text-foreground">{evaluation.status}</p>
                  </div>
                </div>
                <progress max="100" value={evaluation.progress} className="h-2 w-full accent-primary" />
                {evaluation.summary ? (
                  <EvaluationReport summary={evaluation.summary} />
                ) : (
                  <p className={emptyNote}>No aggregate summary yet. Pending may mean the worker, RAGAS runtime, provider, or frozen dataset is not configured.</p>
                )}
              </>
            ) : (
              <p className={emptyNote}>Start an evaluation or load a previous run. The UI does not manufacture benchmark scores.</p>
            )}
          </section>

          <section className={`${glassPanel} space-y-4`} aria-labelledby="reliability-heading">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reliability lab</p>
                <h2 id="reliability-heading" className="mt-1 text-lg font-semibold text-foreground">Operational window</h2>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => void loadReliability()} disabled={busy !== null}>
                <RefreshCw strokeWidth={1.5} className="size-4" />
                {busy === "reliability" ? "Loading…" : "Refresh"}
              </Button>
            </div>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Window (hours)</span>
              <select value={windowHours} onChange={(event) => setWindowHours(Number(event.target.value))} className={selectClass}>
                <option value="1">1 hour</option>
                <option value="24">24 hours</option>
                <option value="72">72 hours</option>
                <option value="168">7 days</option>
              </select>
            </label>
            {reliability ? (
              <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border/50 sm:grid-cols-4">
                <div className="border-b border-r border-border/50 p-4">
                  <span className="text-sm text-muted-foreground">Runs</span>
                  <p className="text-lg font-semibold text-foreground">{reliability.run_count}</p>
                </div>
                <div className="border-b border-r border-border/50 p-6 sm:col-span-2 sm:row-span-1">
                  <span className="text-sm text-muted-foreground">Success</span>
                  <p className="text-2xl font-semibold text-foreground">{Math.round(reliability.success_rate * 100)}%</p>
                </div>
                <div className="border-b border-border/50 p-4 sm:border-b">
                  <span className="text-sm text-muted-foreground">Errors</span>
                  <p className="text-lg font-semibold text-foreground">{Math.round(reliability.error_rate * 100)}%</p>
                </div>
                <div className="border-b border-r border-border/50 p-4">
                  <span className="text-sm text-muted-foreground">Retries</span>
                  <p className="text-lg font-semibold text-foreground">{reliability.retry_count}</p>
                </div>
                <div className="border-b border-r border-border/50 p-4 sm:border-b-0">
                  <span className="text-sm text-muted-foreground">P95</span>
                  <p className="text-lg font-semibold text-foreground">{reliability.p95_latency_ms == null ? "not sampled" : `${reliability.p95_latency_ms} ms`}</p>
                </div>
                <div className="p-4">
                  <span className="text-sm text-muted-foreground">Cost</span>
                  <p className="text-lg font-semibold text-foreground">${Number(reliability.cost_usd).toFixed(4)}</p>
                </div>
              </div>
            ) : (
              <p className={emptyNote}>Metrics are loaded on demand. Zero traffic is a valid empty window, not a reliability claim.</p>
            )}
          </section>

          <form className={`${glassPanel} space-y-4`} onSubmit={runFaultExercise}>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recovery proof</p>
              <h2 className="mt-1 text-lg font-semibold text-foreground">Exercise one bounded failure</h2>
            </div>
            <p className="text-sm text-muted-foreground">This endpoint is hidden in production and available only in local, test, or preview. It records an expiring exercise rather than exposing arbitrary fault injection.</p>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-foreground">Scenario</span>
              <select value={faultScenario} onChange={(event) => setFaultScenario(event.target.value)} className={selectClass}>
                <option value="llm_timeout">LLM timeout</option>
                <option value="qdrant_unavailable">Qdrant unavailable</option>
                <option value="worker_interrupt">Worker interrupt</option>
                <option value="r2_failure">R2 failure</option>
              </select>
            </label>
            <Button type="submit" disabled={busy !== null} className="w-full">
              <AlertTriangle strokeWidth={1.5} className="size-4" />
              {busy === "fault" ? "Scheduling…" : "Run 10-second exercise"}
            </Button>
            <p className="text-xs text-muted-foreground">Use a disposable preview environment. Existing canonical business state remains in PostgreSQL.</p>
          </form>

          <section className={`${glassPanel} md:col-span-2`}>
            <FeedbackReviewQueue
              projectId={projectId}
              onDatasetCreated={handleDatasetCreated}
            />
          </section>
        </section>
      </div>
    </main>
  );
}
