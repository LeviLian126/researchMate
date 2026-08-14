// Renders versioned retrieval metrics and baseline deltas without inventing missing scores.

/** Pipeline identity captured for a single evaluation run. */
interface EvaluationPipeline {
  retrieval_mode?: string;
}

/** Per-metric aggregate surfaced by the evaluation summary. */
interface EvaluationMetric {
  mean_value?: number;
  pass_rate?: number;
}

/** Per-metric baseline delta used to surface regression direction. */
interface EvaluationBaselineComparison {
  mean_delta?: number;
  pass_rate_delta?: number;
}

/** Durable summary record authored by the worker after a run completes. */
interface EvaluationSummary {
  execution_succeeded?: boolean;
  quality_passed?: boolean;
  regression_detected?: boolean;
  pipeline?: EvaluationPipeline;
  baseline_pipeline?: EvaluationPipeline;
  metric_summary?: Record<string, EvaluationMetric>;
  baseline_comparison?: Record<string, EvaluationBaselineComparison>;
}

interface EvaluationReportProps {
  summary: EvaluationSummary;
}

interface MetricRow {
  name: string;
  mean: number | null;
  passRate: number | null;
  meanDelta: number | null;
  passRateDelta: number | null;
}

const METRIC_LABELS: Record<string, string> = {
  schema_valid: "Schema validity",
  citation_precision: "Citation precision",
  evidence_recall: "Recall@K",
  retrieval_mrr: "MRR",
  retrieval_ndcg: "NDCG@K",
  faithfulness: "Faithfulness",
};

function finiteNumber(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function metricRows(summary: EvaluationSummary): MetricRow[] {
  const metrics = summary.metric_summary ?? {};
  const comparisons = summary.baseline_comparison ?? {};
  return Object.entries(metrics).map(([name, metric]) => {
    // Baseline comparisons are optional per metric; defend against missing entries.
    const comparison = comparisons[name] ?? {};
    return {
      name,
      mean: finiteNumber(metric.mean_value),
      passRate: finiteNumber(metric.pass_rate),
      meanDelta: finiteNumber(comparison.mean_delta),
      passRateDelta: finiteNumber(comparison.pass_rate_delta),
    };
  });
}

function percent(value: number | null): string {
  return value == null ? "Not scored" : `${(value * 100).toFixed(1)}%`;
}

function delta(value: number | null): string {
  if (value == null) return "No baseline";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${(value * 100).toFixed(1)} pp`;
}

/** Turns the durable run summary into a comparison table used for release decisions. */
export function EvaluationReport({ summary }: EvaluationReportProps) {
  const rows = metricRows(summary);
  const pipeline = summary.pipeline;
  const baselinePipeline = summary.baseline_pipeline;
  const regression = summary.regression_detected === true;
  const executionSucceeded = summary.execution_succeeded === true;
  const qualityPassed = summary.quality_passed === true;
  const releaseReady = executionSucceeded && qualityPassed && !regression;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border/60 bg-background/60 p-3">
          <span className="text-sm text-muted-foreground">Candidate mode</span>
          <p className="font-semibold text-foreground">
            {pipeline?.retrieval_mode ?? "Not recorded"}
          </p>
        </div>
        <div className="rounded-lg border border-border/60 bg-background/60 p-3">
          <span className="text-sm text-muted-foreground">Baseline mode</span>
          <p className="font-semibold text-foreground">
            {baselinePipeline?.retrieval_mode ?? "No baseline"}
          </p>
        </div>
        <div className="rounded-lg border border-border/60 bg-background/60 p-3">
          <span className="text-sm text-muted-foreground">Release signal</span>
          <p className={`font-semibold ${releaseReady ? "text-emerald-700" : "text-destructive"}`}>
            {!executionSucceeded
              ? "Execution failed"
              : !qualityPassed
                ? "Quality thresholds failed"
                : regression
                  ? "Regression detected"
                  : "No regression detected"}
          </p>
        </div>
      </div>

      {rows.length ? (
        <div className="overflow-x-auto rounded-lg border border-border/60">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="bg-secondary/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Metric</th>
                <th scope="col" className="px-3 py-2 font-medium">Mean</th>
                <th scope="col" className="px-3 py-2 font-medium">Pass rate</th>
                <th scope="col" className="px-3 py-2 font-medium">Mean delta</th>
                <th scope="col" className="px-3 py-2 font-medium">Pass-rate delta</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name} className="border-t border-border/50">
                  <th scope="row" className="px-3 py-3 font-medium text-foreground">
                    {METRIC_LABELS[row.name] ?? row.name.replaceAll("_", " ")}
                  </th>
                  <td className="px-3 py-3 text-muted-foreground">{percent(row.mean)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{percent(row.passRate)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{delta(row.meanDelta)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{delta(row.passRateDelta)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No metric aggregate is available yet.</p>
      )}
    </div>
  );
}
