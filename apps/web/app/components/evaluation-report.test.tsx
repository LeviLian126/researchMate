// Verifies the evaluation report exposes real metrics and baseline decisions.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EvaluationReport } from "./evaluation-report";

describe("EvaluationReport", () => {
  it("renders retrieval metrics, modes, and a non-regression signal", () => {
    const markup = renderToStaticMarkup(
      <EvaluationReport summary={{
        execution_succeeded: true,
        quality_passed: true,
        regression_detected: false,
        pipeline: { retrieval_mode: "hybrid" },
        baseline_pipeline: { retrieval_mode: "dense_only" },
        metric_summary: {
          evidence_recall: { mean_value: 0.9, pass_rate: 1 },
          retrieval_mrr: { mean_value: 0.75, pass_rate: 0.8 },
          retrieval_ndcg: { mean_value: 0.85, pass_rate: 0.9 },
        },
        baseline_comparison: {
          evidence_recall: { mean_delta: 0.1, pass_rate_delta: 0.2 },
        },
      }} />,
    );

    expect(markup).toContain("Recall@K");
    expect(markup).toContain("MRR");
    expect(markup).toContain("NDCG@K");
    expect(markup).toContain("hybrid");
    expect(markup).toContain("dense_only");
    expect(markup).toContain("No regression detected");
    expect(markup).toContain("+10.0 pp");
  });

  it("does not show a green release signal when absolute quality failed", () => {
    const markup = renderToStaticMarkup(
      <EvaluationReport summary={{
        execution_succeeded: true,
        quality_passed: false,
        regression_detected: false,
        metric_summary: {},
      }} />,
    );

    expect(markup).toContain("Quality thresholds failed");
    expect(markup).not.toContain("No regression detected");
  });
});
