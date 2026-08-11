// Renders versioned retrieval metrics and baseline deltas without inventing missing scores.

interface EvaluationReportProps {
  summary: Record<string, unknown>;
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

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function metricRows(summary: Record<string, unknown>): MetricRow[] {
  const metrics = objectValue(summary.metric_summary) ?? {};
  const comparisons = objectValue(summary.baseline_comparison) ?? {};
  return Object.entries(metrics).map(([name, raw]) => {
    const metric = objectValue(raw) ?? {};
    const comparison = objectValue(comparisons[name]) ?? {};
    return {
      name,
      mean: numberValue(metric.mean_value),
      passRate: numberValue(metric.pass_rate),
      meanDelta: numberValue(comparison.mean_delta),
      passRateDelta: numberValue(comparison.pass_rate_delta),
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
  const pipeline = objectValue(summary.pipeline);
  const baselinePipeline = objectValue(summary.baseline_pipeline);
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
            {typeof pipeline?.retrieval_mode === "string" ? pipeline.retrieval_mode : "Not recorded"}
          </p>
        </div>
        <div className="rounded-lg border border-border/60 bg-background/60 p-3">
          <span className="text-sm text-muted-foreground">Baseline mode</span>
          <p className="font-semibold text-foreground">
            {typeof baselinePipeline?.retrieval_mode === "string"
              ? baselinePipeline.retrieval_mode
              : "No baseline"}
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
